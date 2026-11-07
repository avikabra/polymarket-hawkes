"""Company mapping: one yes/no question per (article, company) pair.

Pairs come from exact whole-word name hits in the article. The model sees the company, its brands
that appear in the article, how often they appear, the headline and the text, and answers
{"answer": "yes" | "no"}: is the article primarily about the company.
"""
from __future__ import annotations

import json
import re

from src.ingest.companies import Company

OWN = (
    "You decide whether a news article is primarily about one company. "
    "The brands listed with the company belong to it, so an article about one of those brands is an article about the company, "
    "even when the text never mentions the company's own name. "
    "Answer yes if the company or anything it owns is a main subject of the article: its products, services, shows, games, "
    "subsidiaries, deals, staff moves, stock or earnings. There can be several main subjects. "
    "Answer no if it is only mentioned in passing: a place something was posted, sold or streamed while the story is about "
    "something else, one name in a long list, a person's past employer, or a different thing with the same name."
)
SYSTEM = OWN + (
    " Also answer no for shopping deal lists, roundups of many unrelated items, and stories about a person or a topic "
    "where the company's product is only the setting."
)
SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}},
    "required": ["answer"],
    "additionalProperties": False,
}
MIN_MENTIONS = 3  # a pair is asked if a name is in the headline or lede, or it appears this often in lede and body


def prompt_text() -> str:
    """Everything that shapes the answer, saved beside the results: system prompt, user template, schema."""
    return (SYSTEM + "\n\n--- user message ---\n" + user_message("<company>", ["<brand>"], 0, 0, "<headline>", "<text>")
            + "\n\n--- schema ---\n" + json.dumps(SCHEMA, indent=1) + "\n")


def _count(name: str, text: str) -> int:
    return len(re.findall(r"\b" + re.escape(name) + r"\b", text))


def scan_article(headline, lede, body, companies: list[Company]) -> list[dict]:
    """Every company with a name hit: its hit names, headline count, mention count, and whether a pair is asked.
    Names are whole words with exact capitalization; a context name counts only beside a plain `names` hit."""
    h, l, b = [(x if isinstance(x, str) else "").replace("’", "'") for x in (headline, lede, body)]  # parquet nulls can be NaN
    full = h + " " + l + " " + b
    out = []
    for c in companies:
        hit = lambda n: n.replace("\u2019", "'") in full and _count(n.replace("\u2019", "'"), full)
        ns = [n for n in c.names if hit(n)]
        if not ns:
            continue
        ns += [n for n in c.context_names if hit(n)]
        norm = [n.replace("\u2019", "'") for n in ns]
        in_lede = sum(_count(n, h + " " + l) for n in norm)
        mentions = sum(_count(n, l + " " + b) for n in norm)
        out.append(dict(company_id=c.id, company=c.name, names=ns, in_head=sum(_count(n, h) for n in norm),
                        mentions=mentions, asked=bool(in_lede or mentions >= MIN_MENTIONS)))
    return out


def article_text(lede, body) -> str:
    return (lede or "") + "\n" + (body or "")


def user_message(company, names, in_head, mentions, headline, text) -> str:
    head = f"Company: {company} (brands here: {', '.join(names[:4])})\n"
    head += f"Named in headline: {'yes' if in_head else 'no'}. Mentions in text: {mentions}.\n"
    return head + f"Headline: {headline}\nText: {text}\n\nIs this article primarily about {company}?"


def fit_message(p: dict, headline, text: str, tokenizer, max_tokens: int, cache: dict) -> tuple[str, bool]:
    """-> (user message, cut). Too long: the text keeps its start, cut to the token budget.
    p has company, names, in_head, mentions; cache holds the text tokens per article for one chunk."""
    args = (p["company"], p["names"], p["in_head"], p["mentions"], headline or "")
    head = len(tokenizer(user_message(*args, ""), add_special_tokens=False)["input_ids"])
    ids = cache.get(p["article_id"])
    if ids is None:
        ids = cache[p["article_id"]] = tokenizer(text, add_special_tokens=False)["input_ids"]
    allowed = max(0, max_tokens - head)
    if len(ids) <= allowed:
        return user_message(*args, text), False
    return user_message(*args, tokenizer.decode(ids[:allowed])), True


def parse_answer(raw: str) -> str:
    """"yes" or "no" from the model's JSON answer. Raises ValueError on anything off-schema."""
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"bad json: {e}") from e
    if not isinstance(out, dict) or set(out) != {"answer"} or out["answer"] not in ("yes", "no"):
        raise ValueError("not {'answer': 'yes'|'no'}")
    return out["answer"]

"""Company mapping: one question per article, answered by the model from the article's text.

Every article in which any study company's name appears (exact whole words) is asked; no count decides who is asked.
The model sees each company named in the article with the names found and how often they appear in the headline
and in the text, the headline, and the lede and body, and answers {"companies": [...]}: the named companies the
article is primarily about, or none. The answer can only use companies named in that article.
"""
from __future__ import annotations

import json
import re

from src.ingest.companies import Company

RULES = (
    "You decide which companies a news article is primarily about. The message lists the companies whose names appear "
    "in the article, with the names found and how often they appear in the headline and in the text; choose only from "
    "that list. A brand that belongs to a company counts as the company. "
    "A company counts only if it, or something it owns, is what the article is about: the headline or most of the text "
    "concerns its products, services, shows, games, subsidiaries, deals, staff moves, stock or earnings. There can be "
    "several such companies, or none. "
    "A company does not count when it is mentioned in passing in a story about something else: a place something was "
    "posted, sold or streamed, a source of a quote or a figure, one name in a list, a person's past or present employer, "
    "or a different thing with the same name (a town, a word, a person). Obituaries, local news, shopping deal lists, "
    "roundups of many unrelated items, and stories about a person or a topic where a company's product is only the "
    "setting count for no company. Use the counts as evidence: a company named once or twice in a story about "
    "something else is a passing mention. When in doubt, leave the company out. "
    "Answer with the company names exactly as listed; an empty list means none."
)


def system_prompt() -> str:
    return RULES


def schema(names: list[str]) -> dict:
    """Only the companies named in this article (never empty: every asked article names one) can be answered;
    an empty list (none) is always allowed."""
    return {
        "type": "object",
        "properties": {"companies": {"type": "array", "items": {"type": "string", "enum": names}}},
        "required": ["companies"],
        "additionalProperties": False,
    }


def prompt_text() -> str:
    """Everything that shapes the answer, saved beside the results: system prompt, user template, schema."""
    return (system_prompt() + "\n\n--- user message ---\n"
            + user_message([["<company>", ["<name>"], 0, 0]], "<headline>", "<text>")
            + "\n\n--- schema (per article: the companies named in it) ---\n" + json.dumps(schema(["<company>"]), indent=1) + "\n")


def _clean(x) -> str:
    return (x if isinstance(x, str) else "").replace("’", "'")  # parquet nulls can be NaN


def _count(name: str, text: str) -> int:
    return len(re.findall(r"\b" + re.escape(name) + r"\b", text))


def name_hits(headline, lede, body, companies: list[Company]) -> list[list]:
    """[company, names found, times in headline, times in lede and body] for every company with a name in the article.
    Names are whole words with exact capitalization; a context name counts only beside a plain `names` hit."""
    h, t = _clean(headline), _clean(lede) + " " + _clean(body)
    full = h + " " + t
    out = []
    for c in companies:
        ns = [n for n in c.names if _clean(n) in full and _count(_clean(n), full)]
        if not ns:
            continue
        ns += [n for n in c.context_names if _clean(n) in full and _count(_clean(n), full)]
        out.append([c.name, ns, sum(_count(_clean(n), h) for n in ns), sum(_count(_clean(n), t) for n in ns)])
    return out


def article_text(lede, body) -> str:
    return (lede or "") + "\n" + (body or "")


def user_message(hits: list[list], headline, text) -> str:
    rows = "\n".join(f"- {c} (as {', '.join(ns[:6])}): {nh} in the headline, {nt} in the text" for c, ns, nh, nt in hits)
    return (f"Company names in this article:\n{rows}\n" if rows else "") + (
        f"Headline: {headline}\nText: {text}\n\nWhich of the listed companies is this article primarily about, if any?")


def fit_message(hits, headline, text: str, tokenizer, max_tokens: int) -> tuple[str, bool]:
    """-> (user message, cut). Too long: the text keeps its start, cut to the token budget."""
    args = (hits, headline or "")
    head = len(tokenizer(user_message(*args, ""), add_special_tokens=False)["input_ids"])
    ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    allowed = max(0, max_tokens - head)
    if len(ids) <= allowed:
        return user_message(*args, text), False
    return user_message(*args, tokenizer.decode(ids[:allowed])), True


def parse_answer(raw: str, companies: list[Company], allowed: set[str]) -> list[str]:
    """Company ids from the model's JSON answer; allowed = the company names offered for this article.
    Raises ValueError on anything off-schema."""
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"bad json: {e}") from e
    by_name = {c.name: c.id for c in companies}
    if (not isinstance(out, dict) or set(out) != {"companies"} or not isinstance(out["companies"], list)
            or not set(out["companies"]) <= set(by_name) & allowed):
        raise ValueError("not {'companies': [listed names]}")
    return sorted({by_name[n] for n in out["companies"]})  # a repeated name counts once

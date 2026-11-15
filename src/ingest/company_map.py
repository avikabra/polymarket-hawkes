"""Company mapping: one question per article, answered by the model from the article's text (slide 8).

The candidates are the companies the GDELT pull tagged for the article, confirmed by name in its text (steps 16 and 18).
The model sees each candidate with the names found and how often they appear in the headline and in the text, the
headline, and the lede and body, and gives every candidate one verdict: "main subject", "one of the subjects" or
"passing". A company is matched when it is the main subject, or one of the subjects and named in the headline.
"""
from __future__ import annotations

import json
import re

from src.ingest.companies import Company

RULES = "You read a news article and judge each company named in it. The message lists those companies, with the names found (brands belong to their company) and how often each appears in the headline and in the text. For each company answer \"main subject\", \"one of the subjects\" or \"passing\". Use \"one of the subjects\" when the article is about several companies together, such as a deal, a rivalry, a comparison or several companies doing the same thing. \"main subject\" means the article is about that company: the company or one of its brands is the subject of the headline or of most of the text (its products, services, shows, films, games, subsidiaries, deals, executives, employees, lawsuits, stock or earnings). A show, film or game the company owns is its product: an article about that show, its cast or its plot is about the company, even when the company's own name barely appears. \"passing\" means the company is a side detail in a story about something else: where something was posted, sold or streamed; a social media link, button or quoted post; a source of a quote or a figure; one name in a list; someone's employer; a client, partner or example in another firm's press release or notice; a stock named once among a day's market movers; or a different thing with the same name. An article that recommends, rates or analyses a company's stock (for example, a list of stocks to buy) is \"main subject\" each company whose stock it discusses. When an article is about what several specific companies did (for example, several tech companies each selling bonds), each of them is \"main subject\"; when companies are only examples in a story about a wider topic (a law, a trend, a market), they are \"passing\". A story about a person's private life, health or crimes is \"passing\" for a company even if the person appears in its show. Obituaries, accidents and crimes, shopping deals, roundups and stories about a person or a topic are \"passing\" for every company unless the company itself is the story. A company named only once or twice in the text and not in the headline is usually \"passing\". A company named in the headline is usually \"main subject\", unless the headline names it only as a place, a source or one item in a list. Several companies can be \"main subject\", and often none is. When in doubt, answer \"passing\".\n\nExamples (invented):\n1. Headline: \"Local bakery wins state award\". Meta named once (\"the owner shared the news on Facebook\"). Meta: passing.\n2. Headline: \"Microsoft cuts 6,000 jobs as it pushes AI spending\". Microsoft named 14 times; Alphabet once (\"rivals such as Google\"). Microsoft: about. Alphabet: passing.\n3. Headline: \"Stocks close higher as oil falls\". Apple, Nvidia and Tesla each named once or twice among the day's movers. All passing.\n4. Headline: \"Smith & Co. announces class action against XYZ Corp\". Meta and Microsoft named once in the firm's boilerplate. Both passing.\n5. Headline: \"Amazon tells staff to return to the office five days a week\". Amazon named in the headline and twice in a short text. Amazon: about.\n6. Headline: \"'Wednesday' star teases season 3 twists\". Netflix named once, as the show's home. Netflix: about, because the show is a Netflix product.\n7. Headline: \"2 dividend stocks to buy and hold: Chevron and Pfizer\". Chevron named 8 times, Pfizer 7. Both about.\n9. Headline: \"Air fryer deal: this Amazon-exclusive model is 40% off for Prime members\". Amazon named 5 times. Amazon: passing, because a shopping deal is not news about the company.\n10. Headline: \"Verzenio trial cuts cancer recurrence by a third\". Eli Lilly named 6 times, Verzenio 9 times. Eli Lilly: main subject, because a company's drug and its trial results are its product.\n11. Headline: \"Google to open new office in Leeds\". Alphabet named (as Google) in the headline and 3 times in the text. Alphabet: main subject.\n12. Headline: \"Morning radio show: hosts rank their favourite summer songs\". Netflix and Meta each named once in passing. Both passing.\n13. Headline: \"Actor, 82, dies at home\". Netflix named twice (one of his old series streamed there). Netflix: passing."
LEVELS = ("main subject", "one of the subjects", "passing")
QUESTION = "For each listed company: main subject, one of the subjects, or passing?"


def system_prompt() -> str:
    return RULES


def schema(names: list[str]) -> dict:
    """One verdict for every candidate company of this article."""
    return {"type": "object", "properties": {n: {"type": "string", "enum": list(LEVELS)} for n in names},
            "required": names, "additionalProperties": False}


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
        f"Headline: {headline}\nText: {text}\n\n{QUESTION}")


def fit_message(hits, headline, text: str, tokenizer, max_tokens: int) -> tuple[str, bool]:
    """-> (user message, cut). Too long: the text keeps its start, cut to the token budget."""
    args = (hits, headline or "")
    head = len(tokenizer(user_message(*args, ""), add_special_tokens=False)["input_ids"])
    ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    allowed = max(0, max_tokens - head)
    if len(ids) <= allowed:
        return user_message(*args, text), False
    return user_message(*args, tokenizer.decode(ids[:allowed])), True


def parse_answer(raw: str, companies: list[Company], hits: list[list]) -> list[str]:
    """Company ids matched: a "main subject", or "one of the subjects" named in the headline (hits[i][2] > 0).
    Raises ValueError on anything off-schema."""
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"bad json: {e}") from e
    by_name = {c.name: c.id for c in companies}
    in_headline = {h[0]: h[2] > 0 for h in hits}
    if not isinstance(out, dict) or set(out) != set(in_headline) or not set(out.values()) <= set(LEVELS):
        raise ValueError("not one verdict per candidate company")
    return sorted(by_name[c] for c, v in out.items() if v == LEVELS[0] or (v == LEVELS[1] and in_headline[c]))

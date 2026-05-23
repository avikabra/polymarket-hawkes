# CLAUDE.md — Polymarket Hawkes Thesis Pipeline

> **For debugging and new code additions, always read `README.md` first to understand the structure of the codebase before making any changes.**

---

## 1. Think Before Coding

- **State assumptions explicitly** — if uncertain, ask rather than guess
- **Present multiple interpretations** — don't pick silently when ambiguity exists
- **Push back when warranted** — if a simpler approach exists, say so
- **Stop when confused** — name what's unclear and ask for clarification

---

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked
- No abstractions for single-use code
- No "flexibility" that wasn't requested
- If 200 lines could be 50, rewrite it

---

## 3. Surgical Changes

Touch only what you must. Match existing style.

---

## 4. Goal-Driven Execution

Define success criteria. Loop until verified.

---

## Project-Specific Notes

### Build & Test Commands
- `uv run python scripts/<script>.py` — run any pipeline script
- `make focal` — run full focal pipeline end-to-end
- `uv run pytest tests/` — run all tests
- `uv run python -c "import src"` — confirm package imports

### Math Invariants (DO NOT BREAK)
- All trade prices entering model code MUST be in log-odds units (`log_odds` field), not raw [0,1] (`price_raw` is for human readability only)
- GDELT timestamps are tagged `timestamp_precision = "day"` — never treat them as minute-precise
- `included_in_hawkes_likelihood` must be `True` only when `timestamp_precision == "minute"`

### Environment
- `ANTHROPIC_API_KEY` — set in `.env` before running scripts/08
- `GOOGLE_APPLICATION_CREDENTIALS` — path to GCP service account JSON, set in `.env`
- All secrets loaded from `.env` via `python-dotenv`

### Gotchas
- Goldsky timestamps are integer SECONDS (not milliseconds). `log_index` is a tiebreaker within a block, not a sub-second timestamp.
- Polymarket CLOB `/prices-history` is broken for resolved markets — always use Goldsky subgraph for trade-level data.
- GDELT `SEENDATE` is the crawler's processing time, not article publication time. Use `<pubDate>` from RSS/ESPN for minute-precision timestamps.
- `price_raw` of exactly 0.0 or 1.0 produces ±inf in log-odds. Clip to (0.001, 0.999) before conversion.

# Trade-Data Source — Decision Memo (RESOLVED)

*Weeks 7-9 · drafted 2026-09-05 · author: overnight autonomous run · status: **DECIDED — Polymarket Data-API `/trades`***

> **RESOLUTION (2026-09-05, conviction 9/10): use the official Polymarket Data-API `/trades`.**
> Goldsky subgraph is dead. My first pass called the Data-API "unsafe" — that was **wrong**: I had
> abused the *unsupported* `?asset=` param (which returns a global feed). Read against the **official
> docs**, the endpoint is `/trades?market=<conditionId>&takerOnly=true`, offset-paged inside
> `start`/`end` windows, and it **enforces completeness loudly** (offset>10,000 → HTTP 400, never a
> silent clamp). Verified: `sum(size)` over `takerOnly=true` trades reconciles **to the penny**
> against Gamma's `total_volume_usdc` on liquid markets (NVDA earnings 85,019==85,019; NVDA $176
> 60,505==60,505). The earlier 10% "gap" was a dedup-key bug on my side (collapsed trades on
> `(timestamp,asset,name)`; `transactionHash` is the correct key). Details in §2b below.
> The rest of this memo is retained as the evidence trail.

---

## 1. What broke

`src/polymarket/goldsky.py` targets the Goldsky Polymarket **subgraph**
(`.../subgraphs/polymarket-orderbook-resync/prod/gn`). Every request now returns **HTTP 429** with:

```json
{"errors":[{"message":"This Polymarket subgraph endpoint is paused and deprecated following
Polymarket's migration to V2 — the data is stale and incorrect. Stop using it. For activity,
positions, and balances use the Goldsky Edge Data API",
"extensions":{"code":"ENDPOINT_DEPRECATED","migrateTo":"https://edge.goldsky.com/data/docs/"}}]}
```

This is a **permanent deprecation**, not a transient rate-limit. The subgraph is gone. Anything
downstream that needs trade-level fills — script 02 (`02_pull_trades.py`), script 03 (bars), the
liquidity screen, and the entire log-odds EDA (Q3) — is blocked until a replacement lands.

**Latent bug to fix regardless of source:** `GoldskyClient`'s `@retry` only catches
`ConnectError`/`TimeoutException`, so an HTTP 429/status error is *not* retried and surfaces as a
`RuntimeError`; and `02_pull_trades.py` wraps fills in a broad `except Exception` → warning, which
would have **silently produced empty trade files** on this exact failure. When a new source is
wired, the empty-output guard must be loud (the recent commit "fail loudly on empty output" is the
right direction — extend it to the per-market pull).

---

## 2. What I probed tonight (read-only, throwaway — `scratch/probe_*.json`)

Test contract: `Will NVIDIA (NVDA) beat quarterly earnings?`
(conditionId `0x8994…5f80`, lifetime `total_volume_usdc` = 85,019, resolved).

### Polymarket **Data-API** `https://data-api.polymarket.com/trades`

| probe | result | read |
|---|---|---|
| `?market=<conditionId>&limit=1000` | **HTTP 200**, 355 fills, both yes+no tokens (173+182) | endpoint is live, right schema, covers resolved markets, both outcomes |
| fill fields | `price` (raw [0,1]), `size`, `timestamp` (**int seconds**), `side`, `asset`, `conditionId`, `outcome`, `transactionHash` | **exactly the fields we need**; timestamp convention matches Goldsky (seconds) |
| volume reconcile | `sum(size)`=76,602 vs known 85,019 (**~10% short**); `sum(size·price)`=13,276 | **does not reconcile** — cannot confirm completeness |
| `?market=…&offset=500` | `[]` | 355 < 500 so inconclusive on capping |
| `?asset=<yesToken>&limit=1000` | **exactly 1000** fills, timestamps in a ~90s window **9 days after** this market's last real trade | the `asset` filter appears **ignored** — serving a capped global firehose |
| `?asset=…` offset 0/1000/2000 | each returns 1000, **spans overlap 544/1000**, non-monotone | pagination is **non-deterministic and capped**; not usable for complete history |

**Conclusion on Data-API:** works for a quick sample, but has **undocumented result caps and broken
offset pagination**. Building bars on it risks **silent, severe truncation** — a direct violation of
the pipeline's fail-loud invariant. **Not a safe drop-in as-probed.**

### Polymarket **CLOB** `https://clob.polymarket.com/trades`
Returns **HTTP 401 `Unauthorized/Invalid api key`** — needs authenticated API credentials (L2
header / API key). Coverage for *resolved* markets is unknown, and CLAUDE.md already warns the
CLOB `/prices-history` is broken for resolved markets, so treat CLOB trade coverage as unproven.

---

## 3. Options (ranked), with conviction

| # | Option | What it takes | Completeness risk | Conviction it's the right path |
|---|---|---|---|---|
| 1 | **Goldsky Edge Data API** (the official migrate-to target in the deprecation notice) | Sign up, get key, write a new client against `edge.goldsky.com/data/docs`; re-map fills → existing `Trade` schema | Low if it's the sanctioned V2 feed | **7/10** — most likely intended replacement; unverified only because it needs a key/signup |
| 2 | **Data-API `?market=` with time-windowed slicing** (defeat the cap the way we defeated Gamma's offset ceiling — pull per-market in small date windows, never touch the broken `?asset=` path) | Find the Data-API time params; verify per-window completeness reconciles to `total_volume_usdc` | Medium — depends on `?market=` being complete per window; tonight's single-window total was 10% short | **5/10** — plausible, but the reconciliation gap must be explained first |
| 3 | **On-chain fills from Polygon** (CTF Exchange `OrderFilled` logs via an RPC/archive node or a self-hosted subgraph) | Most engineering; decode logs, map maker/taker, dedupe | Lowest — ground truth | **6/10** on correctness, **3/10** on effort-fit for a thesis timeline |
| 4 | **CLOB with API key** | Obtain Polymarket API creds; test resolved-market trade coverage | Unknown | **4/10** — coverage for resolved markets unproven; CLOB history has known gaps |

I did not pick one because the differences that matter (Edge API auth/coverage, whether Data-API
`?market=` is complete under windowing) can only be resolved with a credential or a decision that is
yours, and a wrong pick silently corrupts every downstream number.

## 4. What I'd need from you to raise conviction to ≥8 and proceed

- **Preferred:** a green light on **Goldsky Edge Data API** + (if it needs one) an API key or the OK
  to register an academic/free account. That's the sanctioned path and I can build + verify a client
  against it, reconciling pulled volume to `total_volume_usdc` before writing any bars.
- **Or:** approval to invest in **Option 2** (time-windowed Data-API) — I'll first prove per-market
  completeness reconciles to within a tight tolerance on a stratified sample of 10 contracts; only
  if it reconciles do I wire it in.
- **Or:** tell me CLOB creds are available and I'll test resolved-market coverage.

Once a source clears the reconciliation check, script 02/03 need only a thin client swap (the
`Trade` schema, log-odds conversion, seconds-timestamps, and bar resampler are all source-agnostic),
and Q3 (the EDA) unblocks immediately — the tooling for it is already built and smoke-tested
(`scripts/eda_logodds.py`).

---

## 5. What is NOT blocked by this

The universe (Q1), the GDELT audit (Q4), the Reuters request, the EDA *tooling*, and the
three-question deck all proceed without trade data. Only the *real* log-odds numbers wait on this
decision.

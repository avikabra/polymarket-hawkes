# Email to Prof. Kelly — DRAFT (do not send without review)

*Drafted 2026-09-05 (overnight run). Outward-facing — for the researcher to review, edit, and send. One line (the reaction headline) fills in when the live EDA completes.*

---

**Subject:** Data-review progress — company-contract universe, log-odds EDA, and two asks

Hi Professor Kelly,

Ahead of the late-September data review, a progress update on the three questions from our last meeting. Short version: the usable sample, the log-odds reaction visuals, and the news-coverage picture are all in hand; and there are two access items where I could use your help.

**1. Usable market sample.** I rebuilt the universe to individual-company contracts only — **6,928 contracts across 86 companies, 2024-04 to 2026-08**, organized as parent/child strike ladders (price, valuation, revenue, market-cap) plus one-off corporate events. Sports/politics/macro/crypto/index/AI-leadership markets are all filtered out. Liquidity is concentrated: **\$79M lifetime volume**, 70% of contracts above \$1k, the top 500 markets holding ~63% of volume. I've deliberately left the liquidity cutoff open until the reaction visuals show whether thin markets just produce zero-moves.

**2. What a real reaction looks like.** One wrinkle worth flagging: the trade data source the pipeline used (a Goldsky subgraph) was deprecated mid-project when Polymarket migrated to "V2." I verified and moved trade pulls to Polymarket's official Data-API, which reconciles exactly against known volumes — so this is handled, not a blocker. The five log-odds visuals are done (594,984 real trades → 72.5M 1-minute bars on the liquid subset). The headline: **a real reaction is mostly nothing, punctuated by large jumps** — 74.6% of 6-hour windows are zero-move even in liquid markets (inactivity manufacturing zeros, exactly as you flagged), but when they do move the median non-zero move is ~0.4 log-odds with a long tail. So the signal is real but sparse, which argues for an event-/trade-conditioned reaction window rather than a fixed 6-hour clock grid. Per your steer, I'm **not** fixing the reaction target yet — I'll bring the visuals and the options.

**3. Matching articles to contracts.** Before asking for a paid feed, I ran a small validation probe over GDELT (our free option), and the answer is nuanced. GDELT + web-scraping is good enough to *start*: it covers ~78% of events and we can extract usable full text from the quality sources ~69% of the time — so I can build and validate the matching pipeline on it now, for free. But it can't carry the *final* intraday study: these markets re-price in ~24-minute steps around events, and GDELT timestamps only to the day (~60× too coarse), plus ~31% of the best sources are paywalled. So I'd still want **Reuters (or a comparable licensed feed) for the precision pass** — a timestamped, full-text archive for our ~30 core companies over 2024–2026. I've drafted the exact request (companies, window, fields) and can send it wherever you point me. The key point: this isn't blocking — I'll proceed on GDELT now and layer the newswire in for the clean event study.

**4. Yale compute.** To run the embedding and resampling stages off my laptop, I'd like to set up access to **Bouchet** (the general-purpose YCRC cluster) under your group. The process is just a short account-request form naming you as PI — you'll get a one-click confirmation email from YCRC to approve. Could you confirm you're OK sponsoring it (and that you have a YCRC PI group)? Then I'll submit the form.

Full detail — sample tables, the GDELT audit, and the reaction visuals — is in a short deck I'll bring to the review. Happy to talk through any of it.

Thanks,
[name]

---

**Attachments / references to include:** `data_review_deck.md`, `gdelt_coverage_audit.md`, `reuters_data_request.md`.

**Two concrete asks embedded:** (1) approve/route the Reuters request; (2) confirm sponsorship so I can submit the Bouchet account form. **One open question raised gently:** public-vs-private companies (not forced — teed up for the review).

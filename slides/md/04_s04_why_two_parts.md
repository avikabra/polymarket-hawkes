---
marp: true
theme: default
paginate: true
style: |
  section { font-family: "Inter", sans-serif; padding: 44px 64px; color: #1b2430; }
  h1 { font-size: 44px; color: #14365d; margin: 0 0 16px 0; }
  h3 { font-size: 27px; font-weight: 500; line-height: 1.3; margin: 0 0 20px 0; }
  h4 { font-size: 22px; color: #14365d; margin: 14px 0 6px 0; text-transform: uppercase; letter-spacing: 0.04em; }
  p { font-size: 22px; margin: 6px 0; }
  table { font-size: 20px; width: 100%; border-collapse: collapse; }
  th { background: #14365d; color: #fff; text-align: left; padding: 7px 12px; }
  td { padding: 8px 12px; border-bottom: 1px solid #d9dee5; vertical-align: top; }
  td:first-child { width: 14%; white-space: nowrap; font-family: "Times New Roman", Georgia, serif; font-size: 24px; }
  .eq { font-family: "Times New Roman", Georgia, serif; font-size: 40px; text-align: center; background: #eef3f9; border-left: 6px solid #14365d; padding: 12px 10px; margin: 8px 0 12px 0; }
  .eq sub { font-size: 26px; }
  .frac { display: inline-block; vertical-align: middle; text-align: center; margin: 0 4px; }
  .frac > span { display: block; padding: 0 6px; }
  .frac > span:first-child { border-bottom: 2px solid #1b2430; }

  h1 { margin: 0 0 14px 0; }
  .two { display: flex; align-items: stretch; height: 556px; }
  .card { flex: 1; border: 2px solid #14365d; display: flex; flex-direction: column; }
  .card .top { background: #14365d; color: #fff; padding: 12px 26px 14px 26px; }
  .card .top .p { font-size: 32px; font-weight: 700; }
  .card .top .q { font-size: 22px; margin-top: 4px; opacity: 0.94; }
  .card .body { padding: 16px 26px 18px 26px; display: flex; flex-direction: column; gap: 14px; flex: 1; }
  .lab { font-size: 16px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: #5b6573; margin: 0 0 6px 0; }
  .txt { font-size: 24px; line-height: 1.36; color: #1b2430; }
  .grow { flex: 1; }
  .out { background: #eef3f9; border-left: 8px solid #14365d; padding: 10px 18px 12px 18px; }
  .out .txt { font-weight: 700; color: #14365d; font-size: 24px; }
  .arr { width: 52px; display: flex; align-items: center; justify-content: center; font-size: 44px; color: #14365d; flex: none; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 13px; }
  section::after { display: none; }
  section::before { content: "4"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# Why the question splits in two

<div class="two">
<div class="card"><div class="top"><div class="p">I. Matching</div><div class="q">Which articles are about which company?</div></div>
<div class="body">
<div class="grow"><div class="lab">Problem</div><div class="txt">GDELT lists articles that name a company, but a name alone does not make a story about it: "Apple" turns up in app reviews, film reviews, and profiles of former employees. For each pair, a language model picks which of the companies it names are main subjects.</div></div>
<div><div class="lab">Input</div><div class="txt">GDELT articles and company names</div></div>
<div class="out"><div class="lab">Output</div><div class="txt">Matched article-company pairs</div></div>
</div></div>
<div class="arr">→</div>
<div class="card"><div class="top"><div class="p">II. Prediction</div><div class="q">Does the news shock predict the reaction?</div></div>
<div class="body">
<div class="grow"><div class="lab">Problem</div><div class="txt">For each company and day, we build the news shock from that day's matched articles, and the reaction from the company's Polymarket contracts. We fit weights on training days and score the resulting strategy on test days. Both sides are averaged per company and day.</div></div>
<div><div class="lab">Input</div><div class="txt">Matched pairs, trades, stock prices</div></div>
<div class="out"><div class="lab">Output</div><div class="txt">Sharpe ratio on test days</div></div>
</div></div>
</div>

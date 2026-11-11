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

  .wrap { height: 600px; display: flex; flex-direction: column; justify-content: space-between; }
  .lab { font-size: 20px; font-weight: 700; letter-spacing: 0.08em; color: #5b6573; text-transform: uppercase; margin: 0 0 10px 0; }
  .q { font-size: 40px; font-weight: 700; color: #14365d; line-height: 1.22; border-left: 8px solid #14365d; padding-left: 26px; }
  .cards { display: flex; gap: 22px; }
  .card { flex: 1; background: #eef3f9; border-top: 6px solid #14365d; padding: 18px 22px 22px 22px; }
  .card .h { font-size: 26px; font-weight: 700; color: #14365d; margin: 0 0 10px 0; }
  .card .d { font-size: 22px; line-height: 1.35; color: #1b2430; }
  .fu { border-top: 2px solid #d9dee5; padding-top: 14px; font-size: 22px; color: #3a4452; line-height: 1.35; }
  .fu b { color: #14365d; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 15px; }
  section::after { display: none; }
  section::before { content: "3"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

<div class="wrap">
<div>
<div class="lab">Research question</div>
<div class="q">Does a company's daily news shock predict the average move of its Polymarket contracts over the next 24 hours?</div>
</div>

<div class="cards">
<div class="card"><div class="h">News shock</div><div class="d">Defined per company and day: the average embedding of the company's articles that day, minus the embedding its characteristics predict.</div></div>
<div class="card"><div class="h">Reaction</div><div class="d">Defined per company and day: the change in log-odds of the company's Polymarket contract prices over the next 24 hours, averaged across its contracts.</div></div>
<div class="card"><div class="h">Predict</div><div class="d">On test days not used in fitting, we measure the Sharpe ratio of a strategy weighted by the news shock and compare it with raw news and predictable news.</div></div>
</div>

<div class="fu"><b>Follow-ups.</b> Does Polymarket absorb news more slowly than the stock? In which markets (thin or busy), and by whom (small or large trades)?</div>
</div>

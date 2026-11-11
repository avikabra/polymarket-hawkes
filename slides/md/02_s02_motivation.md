---
marp: true
theme: default
paginate: true
style: |
    section { font-family: "Helvetica Neue", Arial, sans-serif; padding: 44px 64px; color: #1b2430; }
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

  h1 { margin: 0 0 18px 0; }
  .cols { display: flex; gap: 40px; align-items: stretch; height: 530px; }
  .left { flex: 1.45; display: flex; flex-direction: column; }
  .item { flex: 1; display: flex; gap: 22px; align-items: center; padding: 12px 0; border-bottom: 2px solid #d9dee5; }
  .item:last-child { border-bottom: none; }
  .num { flex: none; width: 54px; height: 54px; border-radius: 50%; background: #14365d; color: #fff; font-size: 30px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
  .hd { font-size: 28px; font-weight: 700; color: #14365d; line-height: 1.2; margin: 2px 0 8px 0; }
  .sb { font-size: 21px; color: #3a4452; line-height: 1.3; }
  .right { flex: 1; background: #eef3f9; border-left: 8px solid #14365d; padding: 22px 26px; display: flex; flex-direction: column; justify-content: space-evenly; }
  .right .t { font-size: 23px; font-weight: 700; color: #14365d; line-height: 1.25; }
  .bar .n { font-size: 22px; margin: 0 0 6px 0; }
  .bar .row { display: flex; align-items: center; }
  .bar .b { height: 46px; background: #9fb3cc; }
  .bar .b.hi { background: #14365d; }
  .bar .v { font-size: 32px; font-weight: 700; margin-left: 12px; }
  .src { font-size: 16px; color: #5b6573; line-height: 1.35; }
---

# Motivation

<div class="cols"><div class="left">
<div class="item"><div class="num">1</div><div><div class="hd">Firm characteristics explain only about 10% of what articles say.</div><div class="sb">The remaining 90% of the variation in article text embeddings is the residual: the news shock (Kelly&nbsp;et&nbsp;al.,&nbsp;2026).</div></div></div>
<div class="item"><div class="num">2</div><div><div class="hd">Stocks price the news shock with a delay.</div><div class="sb">It predicts stock returns up to 18 months ahead.</div></div></div>
<div class="item"><div class="num">3</div><div><div class="hd">Polymarket lists binary contracts on the same companies.</div><div class="sb">Each pays $1 if its event occurs, so its price is the market-implied probability. Does the news shock move these prices?</div></div></div>
</div>
<div class="right">
<div class="t">Stocks: annualized Sharpe ratio (return per unit of risk), 1996–2022</div>
<div class="bar"><div class="n">Raw article embeddings</div><div class="row"><div class="b" style="width:28%"></div><span class="v">1.1</span></div></div>
<div class="bar"><div class="n">Best standard anomaly factor</div><div class="row"><div class="b" style="width:35%"></div><span class="v">1.4</span></div></div>
<div class="bar"><div class="n">News shock</div><div class="row"><div class="b hi" style="width:78%"></div><span class="v">3.1</span></div></div>
</div></div>

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

  h1 { margin: 0 0 12px 0; }
  .lanes { display: flex; flex-direction: column; gap: 12px; height: 562px; }
  .lane { display: flex; border: 2px solid #14365d; }
  .l1 { height: 210px; } .l2 { height: 340px; }
  .tag { width: 84px; background: #14365d; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; flex: none; }
  .tag .n { font-size: 34px; font-weight: 700; }
  .tag .w { font-size: 16px; font-weight: 500; margin-top: 2px; }
  .flow { flex: 1; display: flex; align-items: center; padding: 10px 12px; }
  .stack { display: flex; flex-direction: column; gap: 8px; width: 252px; flex: none; }
  .box { background: #eef3f9; border-top: 4px solid #14365d; padding: 7px 11px 8px 11px; }
  .box.in { background: #fff; border: 2px solid #14365d; border-top-width: 2px; }
  .box.out { background: #14365d; color: #fff; }
  .box .t { font-size: 19px; font-weight: 700; color: #14365d; margin-bottom: 3px; }
  .box.out .t { color: #fff; }
  .box .d { font-size: 15.5px; line-height: 1.27; }
  .l2 .flow { padding: 4px 12px; }
  .a { width: 24px; text-align: center; font-size: 26px; color: #14365d; flex: none; }
  .s1 { flex: 1 1 0; min-width: 0; }
  .grid2 { flex: 1; display: grid; grid-template-columns: 200px 22px 250px 22px 1fr 30px 135px 22px 145px; grid-template-rows: repeat(3, 1fr); row-gap: 5px; align-items: center; height: 100%; }
  .grid2 .a { align-self: center; }
  .br { grid-row: 1 / 4; grid-column: 6; position: relative; align-self: stretch; }
  .br .ln { position: absolute; left: 0; right: 12px; top: 33.3%; bottom: 16.7%; border: 2px solid #14365d; border-left: none; }
  .br::after { content: '\25B6'; position: absolute; right: -1px; top: 58.3%; transform: translateY(-50%); font-size: 14px; color: #14365d; }
  .grid2 .span { grid-row: 1 / 4; align-self: center; }
  .grid2 .sp2 { grid-row: 1 / 3; align-self: center; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 11px; }
  section::after { display: none; }
  section::before { content: "5"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# Pipeline Flow

<div class="lanes">
<div class="lane l1"><div class="tag"><div class="n">I</div><div class="w">Matching</div></div><div class="flow">
<div class="stack">
<div class="box in"><div class="t">Companies</div><div class="d">61 companies and 4,428 names (brands, products, subsidiaries) from Wikidata.</div></div>
<div class="box in"><div class="t">GDELT</div><div class="d">News articles by URL, Sep 26, 2025 to Oct 29, 2026.</div></div>
</div>
<div class="a">→</div>
<div class="box s1"><div class="t">Name filter</div><div class="d">Keep the rows that name a company, as a whole word with exact capitalization: 4,296,455 distinct URLs.</div></div>
<div class="a">→</div>
<div class="box s1"><div class="t">Download text</div><div class="d">GDELT stores no text, so we fetch each page from its publisher: 3,446,368 articles with text.</div></div>
<div class="a">→</div>
<div class="box s1"><div class="t">Pick main subjects</div><div class="d">Qwen3.5-4B reads each article and writes which of the companies it names are main subjects.</div></div>
<div class="a">→</div>
<div class="box out s1"><div class="t">Matched pairs</div><div class="d" style="white-space:nowrap">Article-company<br>pairs, passed to Part<br>II.</div></div>
</div></div>
<div class="lane l2"><div class="tag"><div class="n">II</div><div class="w">Prediction</div></div><div class="flow"><div class="grid2">
<div class="box in" style="grid-row:1;grid-column:1"><div class="t">Matched pairs</div><div class="d">From Part I.</div></div>
<div class="a" style="grid-row:1;grid-column:2">→</div>
<div class="box" style="grid-row:1;grid-column:3"><div class="t">Daily average</div><div class="d">Each article becomes 2,560 numbers, averaged per company and day.</div></div>
<div class="a" style="grid-row:1;grid-column:4">→</div>
<div class="box sp2" style="grid-column:5"><div class="t">News shock</div><div class="d">The daily average minus what the 28 characteristics predict, fit each day on the previous month.</div></div>
<div class="box in" style="grid-row:2;grid-column:1"><div class="t">Stock data</div><div class="d">Yahoo Finance prices, volume, SPY, and statements.</div></div>
<div class="a" style="grid-row:2;grid-column:2">→</div>
<div class="box" style="grid-row:2;grid-column:3"><div class="t">Characteristics</div><div class="d">28 columns: 8 stock, 3 Polymarket, 16 industry, and a constant.</div></div>
<div class="a" style="grid-row:2;grid-column:4">→</div>
<div class="box in" style="grid-row:3;grid-column:1"><div class="t">Polymarket trades</div><div class="d">832,257 trades, $51.3M, in 22,563 contracts.</div></div>
<div class="a" style="grid-row:3;grid-column:2">→</div>
<div class="box" style="grid-row:3;grid-column:3"><div class="t">Reaction</div><div class="d">24-hour change in log-odds per contract, averaged by dollars traded.</div></div>
<div class="a" style="grid-row:3;grid-column:4">→</div>
<div class="box" style="grid-row:3;grid-column:5"><div class="t">Adjusted reaction</div><div class="d">Scaled for every contract, with stock prices used to split out the stock's part.</div></div>
<div class="br"><div class="ln"></div></div>
<div class="box span" style="grid-column:7"><div class="t">Fit</div><div class="d" style="white-space:nowrap">Weights that<br>maximize the<br>Sharpe ratio, fit<br>on Oct 26,<br>2025 to Aug<br>27, 2026.</div></div>
<div class="a span" style="grid-column:8">→</div>
<div class="box out span" style="grid-column:9"><div class="t">Sharpe ratio</div><div class="d">Average daily profit divided by its standard deviation, on test days Aug 28 to Oct 29, 2026.</div></div>
</div></div></div>
</div>

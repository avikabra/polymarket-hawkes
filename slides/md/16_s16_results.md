---
marp: true
theme: default
paginate: true
style: |
  @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap");
  section { font-family: Inter, "Helvetica Neue", Arial, sans-serif; padding: 44px 64px; color: #1b2430; }
  h1 { font-size: 44px; color: #14365d; margin: 0 0 6px 0; }
  math { font-family: "Latin Modern Math", "STIX Two Math", "Cambria Math", "Times New Roman", serif; font-size: 1.12em; }
  .sub { font-size: 20px; color: #2c3747; margin-bottom: 18px; }
  .cols { display: flex; gap: 26px; height: 496px; }
  .chart { flex: 1.05; border: 2px solid #14365d; display: flex; flex-direction: column; }
  .chart .eh { background: #14365d; color: #fff; padding: 9px 20px; font-size: 21px; font-weight: 700; }
  .chart .body { flex: 1; padding: 14px 22px 12px 22px; display: flex; flex-direction: column; }
  .lab { font-size: 15px; font-weight: 700; letter-spacing: 0.06em; color: #5b6573; text-transform: uppercase; margin-bottom: 8px; }
  .bars { flex: 1; display: flex; flex-direction: column; justify-content: space-around; border-left: 2px solid #8a95a3; }
  .bar { display: flex; align-items: center; gap: 12px; }
  .bar .nm { width: 176px; flex: none; text-align: right; padding-right: 14px; margin-left: -194px; }
  .bar .l1 { font-size: 19px; font-weight: 700; color: #14365d; line-height: 1.15; }
  .bar .l2 { font-size: 15px; color: #5b6573; }
  .bar .bf { height: 44px; width: 270px; border: 2px dashed #7f98ba; background: #f5f8fc; flex: none; }
  .bar .bv { font-size: 22px; font-weight: 700; color: #5b6573; }
  .plot { flex: 1; display: flex; padding-left: 194px; }
  .axis { font-size: 15px; color: #5b6573; padding-left: 194px; margin-top: 6px; }
  .pend { font-size: 15px; font-weight: 700; color: #14365d; background: #dbe6f3; padding: 3px 9px; margin-top: 10px; align-self: flex-start; }
  .steps { flex: 1; display: flex; flex-direction: column; }
  .st { flex: 1; display: flex; gap: 16px; align-items: center; border-bottom: 1px solid #d9dee5; padding: 4px 0; }
  .st:last-child { border-bottom: none; }
  .nb { width: 44px; height: 44px; border-radius: 50%; background: #14365d; color: #fff; font-size: 24px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex: none; }
  .st .t { font-size: 23px; font-weight: 700; color: #14365d; margin-bottom: 3px; }
  .st .d { font-size: 18px; line-height: 1.32; }
  table { font-size: 17px; border-collapse: collapse; margin-top: 6px; }
  th { background: #14365d; color: #fff; text-align: left; padding: 4px 12px; font-weight: 700; }
  td { padding: 4px 12px; border-bottom: 1px solid #d9dee5; color: #5b6573; }
  td:first-child { color: #1b2430; font-weight: 700; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
---

# Results

<div class="sub">Out-of-sample Sharpe ratio on the test days, Aug 28 to Oct 29, 2026, in the style of Kelly et al., Figure 4.</div>

<div class="cols">
<div class="chart"><div class="eh">Daily Sharpe ratio, in ξ</div><div class="body">
<div class="lab">Three portfolios, one fit</div>
<div class="plot"><div class="bars">
<div class="bar"><div class="nm"><div class="l1">News shock</div><div class="l2"><math><mi>u</mi></math></div></div><div class="bf"></div><div class="bv">—</div></div>
<div class="bar"><div class="nm"><div class="l1">Raw news</div><div class="l2"><math><mi>E</mi></math></div></div><div class="bf"></div><div class="bv">—</div></div>
<div class="bar"><div class="nm"><div class="l1">Predictable news</div><div class="l2"><math><mi>S</mi><mover accent="true"><mi>β</mi><mo>^</mo></mover></math></div></div><div class="bf"></div><div class="bv">—</div></div>
</div></div>
<div class="axis">0 = no edge. Bars to the right gain on average.</div>
<div class="pend">Filled once, on the single test run</div>
</div></div>

<div class="steps">
<div class="st"><div class="nb">1</div><div><div class="t">Same fit, three predictors</div><div class="d">Each portfolio is fit by MSRR (slide 15) on the training days. Only the predictor changes: the news shock <math><mi>u</mi></math>, raw news <math><mi>E</mi></math>, or predictable news <math><mi>S</mi><mover accent="true"><mi>β</mi><mo>^</mo></mover></math>.</div></div></div>
<div class="st"><div class="nb">2</div><div><div class="t">How to read it</div><div class="d">Because <math><mi>E</mi><mo>=</mo><mi>S</mi><mover accent="true"><mi>β</mi><mo>^</mo></mover><mo>+</mo><mi>u</mi></math>, the bars split the news into what was known and what was new. If the news shock has the highest Sharpe ratio, the new part of the news is what predicts the move.</div></div></div>
<div class="st"><div class="nb">3</div><div><div class="t">Units</div><div class="d">The chart is in ξ, the standardized reaction (slide 14). Money and log-odds are checks.
<table><tr><th></th><th>ξ</th><th>Money</th><th>Log-odds</th></tr>
<tr><td>News shock</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Raw news</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Predictable news</td><td>—</td><td>—</td><td>—</td></tr></table></div></div></div>
</div>
</div>

<div class="trk">Results &rsaquo; <b>Sharpe ratio</b></div>

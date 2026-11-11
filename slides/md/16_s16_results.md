---
marp: true
theme: default
paginate: false
style: |
  section { font-family: "Helvetica Neue", Arial, sans-serif; padding: 44px 64px; color: #1b2430; }
  h1 { font-size: 44px; color: #14365d; margin: 0 0 22px 0; }
  math { font-family: "Latin Modern Math", "STIX Two Math", "Cambria Math", "Times New Roman", serif; font-size: 1.12em; }
  .cols { display: flex; gap: 40px; height: 520px; }
  .chart { flex: 1.1; display: flex; flex-direction: column; }
  .ct { font-size: 22px; font-weight: 700; color: #14365d; margin-bottom: 10px; }
  .plot { flex: 1; display: flex; }
  .yl { width: 30px; margin-right: 30px; flex: none; display: flex; align-items: center; justify-content: center; }
  .yl span { transform: rotate(-90deg); white-space: nowrap; font-size: 17px; color: #2c3747; }
  .area { flex: 1; position: relative; border-left: 2px solid #8a95a3; }
  .zero { position: absolute; left: 0; right: 0; top: 62%; border-top: 2px solid #1b2430; }
  .z0 { position: absolute; left: -26px; top: calc(62% - 12px); font-size: 17px; color: #2c3747; }
  .cats { position: absolute; left: 0; right: 0; top: 62%; display: flex; justify-content: space-around; }
  .cat { width: 130px; text-align: center; }
  .cat .v { font-size: 24px; font-weight: 700; color: #5b6573; margin-top: -40px; height: 40px; }
  .xl { display: flex; justify-content: space-around; margin-left: 62px; padding-top: 10px; border-top: 1px solid #d9dee5; }
  .xl div { width: 150px; text-align: center; font-size: 18px; font-weight: 700; color: #14365d; line-height: 1.25; }
  .xl div span { display: block; font-weight: 400; color: #2c3747; }
  .xa { text-align: center; margin-left: 62px; font-size: 16px; color: #5b6573; margin-top: 8px; }
  .side { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  ul { margin: 0; padding-left: 24px; }
  li { font-size: 21px; line-height: 1.35; margin-bottom: 14px; }
  table { font-size: 18px; border-collapse: collapse; margin-top: 10px; }
  th { background: #14365d; color: #fff; text-align: left; padding: 5px 14px; }
  td { padding: 5px 14px; border-bottom: 1px solid #d9dee5; color: #5b6573; }
  td:first-child { color: #1b2430; font-weight: 700; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
  .pn { position: absolute; right: 40px; bottom: 26px; font-size: 16px; color: #8a95a3; }
---

# Results

<div class="cols">
<div class="chart">
<div class="ct">Daily Sharpe ratio in ξ</div>
<div class="plot"><div class="yl"><span>Sharpe ratio</span></div>
<div class="area"><div class="zero"></div><div class="z0">0</div>
<div class="cats"><div class="cat"><div class="v">—</div></div><div class="cat"><div class="v">—</div></div><div class="cat"><div class="v">—</div></div></div>
</div></div>
<div class="xl"><div>News shock<span><math><mi>u</mi></math></span></div><div>Raw news<span><math><mi>E</mi></math></span></div><div>Predictable news<span><math><mi>S</mi><mover accent="true"><mi>β</mi><mo>^</mo></mover></math></span></div></div>
<div class="xa">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<ul>
<li>Each bar is one portfolio fit on training days and scored on test days.</li>
<li>The portfolios differ only in the news they use.</li>
<li>Raw news is predictable news plus the shock: <math><mi>E</mi><mo>=</mo><mi>S</mi><mover accent="true"><mi>β</mi><mo>^</mo></mover><mo>+</mo><mi>u</mi></math>.</li>
</ul>
<table><tr><th>Sharpe ratio</th><th>ξ</th><th>Money</th><th>Log-odds</th></tr>
<tr><td>News shock</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Raw news</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>Predictable news</td><td>—</td><td>—</td><td>—</td></tr></table>
</div>
</div>

<div class="trk">Results &rsaquo; <b>Sharpe ratio</b></div>
<div class="pn">16</div>

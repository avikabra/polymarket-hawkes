---
marp: true
theme: default
paginate: true
style: |
  section { font-family: "Inter", sans-serif; padding: 44px 64px; color: #1b2430; }
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
  .xl div { width: 180px; text-align: center; font-size: 18px; font-weight: 700; color: #14365d; line-height: 1.25; }
  .xl div span { display: block; font-weight: 400; color: #2c3747; }
  .xa { text-align: center; margin-left: 62px; font-size: 16px; color: #5b6573; margin-top: 8px; }
  .side { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  ul { margin: 0; padding-left: 24px; }
  li { font-size: 19px; line-height: 1.32; margin-bottom: 10px; }
  table { font-size: 18px; border-collapse: collapse; margin-top: 10px; }
  th { background: #14365d; color: #fff; text-align: left; padding: 5px 14px; }
  td { padding: 5px 14px; border-bottom: 1px solid #d9dee5; color: #5b6573; }
  td:first-child { color: #1b2430; font-weight: 700; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
  svg text { font-family: "Inter", sans-serif; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 11px; }
  section::after { display: none; }
  section::before { content: "19"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
  .tb { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  .tb table { font-size: 19px; width: 100%; margin-top: 0; }
  .tb td, .tb th { padding: 7px 14px; }
  .tb td:nth-child(n+2), .tb th:nth-child(n+2) { text-align: right; }
  .side li { font-size: 20px; }
---

# The busiest markets

<div class="cols">
<div class="tb">
<table><tr><th>Company</th><th>Volume in the year</th><th>Typical test day</th></tr>
<tr><td>Nvidia</td><td>$8.2M</td><td>$2,700</td></tr>
<tr><td>Alphabet</td><td>$5.6M</td><td>$2,900</td></tr>
<tr><td>Tesla</td><td>$5.2M</td><td>$2,600</td></tr>
<tr><td>Meta</td><td>$5.1M</td><td>$3,600</td></tr>
<tr><td>Apple</td><td>$5.1M</td><td>$2,400</td></tr>
<tr><td>Netflix</td><td>$5.0M</td><td>$2,300</td></tr>
<tr><td>Amazon</td><td>$4.7M</td><td>$2,200</td></tr>
<tr><td>Microsoft</td><td>$4.3M</td><td>$3,000</td></tr>
<tr><td>Palantir</td><td>$3.1M</td><td>$2,400</td></tr></table>
<div class="xa" style="margin-left:0">Polymarket dollar volume from Sep 2025 to Oct 2026</div>
</div>

<div class="side">
<ul>
<li>These nine companies hold 46 of the 51 million dollars traded across all 61 companies.</li>
<li>The news-shock bets on these nine earn no more than on all 61. The Sharpe ratio in ξ is −0.12 against −0.09.</li>
<li>A contract the strategy holds trades about $1,100 a day. All 61 companies together trade about $50,000 a day.</li>
<li>Example: a 1% daily edge on 10% of volume needs $4&nbsp;million traded a day to earn $1&nbsp;million a year.</li>
</ul>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>The busiest markets</b></div>

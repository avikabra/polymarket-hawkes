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
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 11px; }
  section::after { display: none; }
  section::before { content: "16"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
  svg text { font-family: "Inter", sans-serif; }
  .iv { display: block; font-size: 14px; color: #8a95a3; font-weight: 400; }
  td { vertical-align: top; }
  .side li { font-size: 19px; }
  .side li { font-size: 18px; margin-bottom: 6px; }
  .side td, .side th { padding: 4px 12px; }
  .iv { font-size: 13px; }

  svg text { font-family: "Inter", sans-serif; }
  .side li { font-size: 20px; margin-bottom: 12px; }
  .tb { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  .tb table { font-size: 19px; width: 100%; margin-top: 0; }
  .tb td, .tb th { padding: 8px 14px; }
  .tb td.n, .tb th.n { text-align: right; }
  .tb td:first-child { white-space: nowrap; }
---

# How we test news against Polymarket moves

<div class="cols">
<div class="tb">
<table><tr><th>Score</th><th>Measures</th><th class="n">Example</th></tr>
<tr><td>Money</td><td>Dollars earned per dollar bet</td><td class="n">0.02</td></tr>
<tr><td>Log-odds</td><td>Change in the price's log-odds</td><td class="n">0.41</td></tr>
<tr><td>ξ</td><td>Price move in standard deviations of the stock</td><td class="n">1.00</td></tr></table>
</div>

<div class="side">
<ul>
<li>Each day from Aug 28 to Oct 29, 2026 we bet on every company with news that day.</li>
<li>Weights learned on earlier days set each bet's side and size. We hold each bet from midnight for 24 hours.</li>
<li>We set the bets three ways. The news shock is what company traits do not explain. Raw news is all of the articles. Predictable news is what company traits explain.</li>
<li>ξ is the main score. It puts every contract on one scale.</li>
</ul>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>How we test news against Polymarket moves</b></div>

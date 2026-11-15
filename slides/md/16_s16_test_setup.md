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
  .side li { font-size: 18px; margin-bottom: 9px; }
  .tb td:first-child { white-space: nowrap; }
  .tb td { vertical-align: top; }
---

# How we test news against Polymarket moves

<div class="cols">
<div class="tb">
<table><tr><th>Score</th><th>What it measures</th></tr>
<tr><td>ξ</td><td>The contract's price move divided by the move the stock's volatility predicts for its price and time left</td></tr>
<tr><td>Money</td><td>Dollars earned per dollar bet</td></tr>
<tr><td>Log-odds</td><td>The change in the log-odds of the contract's price</td></tr></table>
</div>

<div class="side">
<ul>
<li>Each day from Aug 28 to Oct 29, 2026 we bet on every company with news that day.</li>
<li>A bet bought the company's Polymarket contracts on the side its news pointed to. Good news bought contracts that pay if the company does well.</li>
<li>Weights turned each company's news into a bet size. We learned the weights on earlier days as the news patterns that best predicted price moves. We sold each bet 24 hours after midnight.</li>
<li>Raw news is the company's articles that day. Predictable news is the part of those articles that company traits predict. The news shock is the articles net of company traits.</li>
<li>We judged the bets in ξ. It lets a 5¢ contract and a 90¢ contract count equally.</li>
</ul>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>How we test news against Polymarket moves</b></div>

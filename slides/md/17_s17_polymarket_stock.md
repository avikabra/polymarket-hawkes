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
  section::before { content: "17"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# Polymarket and stock

<div class="cols">
<div class="chart">
<div class="ct">Daily Sharpe ratio of the news-shock portfolio</div>
<div class="plot"><div class="yl"><span>Sharpe ratio</span></div>
<div class="area"><div class="zero"></div><div class="z0">0</div>
<div class="cats"><div class="cat"><div class="v">…</div></div><div class="cat"><div class="v">…</div></div></div>
</div></div>
<div class="xl"><div>Polymarket<span>contracts</span></div><div>Stock<span>shares</span></div></div>
<div class="xa">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<ul>
<li>We run the portfolio from slide 16 on each company's stock, with the stock's return in place of the Polymarket reaction. This repeats the test of Kelly et al. on our news and days.</li>
<li>Both bars use the money return: dollars earned per dollar bet. Example: a $1 bet that gains 2 cents returns 0.02.</li>
<li>Polymarket bets run from midnight for 24 hours. Stock bets run from the news day's close to the next day's close.</li>
<li>A higher Sharpe ratio on Polymarket means Polymarket absorbs the same news more slowly than the stock.</li>
</ul>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>Polymarket and stock</b></div>

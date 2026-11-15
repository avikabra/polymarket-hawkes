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
  section::before { content: "20"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
  .lim { margin-top: 10px; }
  .lim table { width: 100%; }
  .lim th { padding: 8px 16px; font-size: 19px; }
  .lim td { padding: 9px 16px; vertical-align: top; color: #2c3747; font-weight: 400; font-size: 17px; line-height: 1.3; }
  .lim td:first-child { width: 62%; }
  .lim .h { font-weight: 700; color: #1b2430; font-size: 20px; margin-bottom: 2px; }
---

# Limitations of the test

<div class="lim">
<table><tr><th>Limitation</th><th>Effect on the results</th></tr>
<tr><td><div class="h">Stock bets open eight hours before Polymarket bets</div>Polymarket trades around the clock so its bet runs from midnight to midnight. Stocks trade 9:30am to 4pm so the stock bet runs from the 4pm close to the next close. A 6pm article falls inside the stock bet. Polymarket may price it before midnight.</td><td>The stock gets news that Polymarket has already priced. This favors the stock when we compare the two markets.</td></tr>
<tr><td><div class="h">Articles have a date but no time</div>GDELT records only the day each article appeared. Ideally each article would carry its publication time. Each bet could then start the minute the article came out.</td><td>A price move at 9am can come before a 3pm article on the same day. The bets may get credit for moves that came before the news.</td></tr>
<tr><td><div class="h">The test covers only 63 days</div>We test the bets once on Aug 28 to Oct 29, 2026. A Sharpe ratio from 63 daily returns is imprecise.</td><td>Bets that truly earn a little can show a 95% interval that includes zero. We would then fail to detect it.</td></tr>
<tr><td><div class="h">The stock comparison assumes a straight line</div>We fit Polymarket return = a + c × stock return. This assumes each extra cent of stock return adds the same amount on Polymarket. Large stock moves may carry over differently from small ones.</td><td>If the true link bends then a and c describe only an average of it.</td></tr></table>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>Limitations of the test</b></div>

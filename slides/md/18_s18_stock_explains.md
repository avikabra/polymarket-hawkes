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
  section::before { content: "18"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# What the stock explains

<div class="cols">
<div class="chart">
<div class="ct">Daily return of the same news-shock bets</div>
<svg width="560" height="440" viewBox="0 0 560 440">
<line x1="60" y1="210" x2="540" y2="210" stroke="#1b2430" stroke-width="2"/>
<line x1="300" y1="20" x2="300" y2="400" stroke="#1b2430" stroke-width="2"/>
<line x1="110" y1="400" x2="490" y2="20" stroke="#14365d" stroke-width="2" stroke-dasharray="8 6"/>
<text x="80" y="60" font-size="16" fill="#14365d">Dashed line: Polymarket</text>
<text x="80" y="82" font-size="16" fill="#14365d">mirrors the stock (c = 1)</text>
<text x="300" y="430" font-size="17" fill="#2c3747" text-anchor="middle">Stock return per $1 bet</text>
<text x="22" y="210" font-size="17" fill="#2c3747" text-anchor="middle" transform="rotate(-90 22 210)">Polymarket return per $1 bet</text>
<text x="308" y="230" font-size="15" fill="#5b6573">0</text>
</svg>
<div class="xa" style="margin-left:0">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<ul>
<li>Polymarket can profit just because the stock moved. The intercept a is the profit left over after the stock's part.</li>
<li>Each test day we place the bets from slide 16 on both markets. We fit Polymarket return = a + c × stock return across the test days.</li>
<li>c is the Polymarket return per dollar of stock return. Example: c = 0.5 means 2 cents per dollar on the stock bets adds 1 cent on Polymarket.</li>
<li>A positive a means Polymarket misprices the news in a way the stock does not.</li>
</ul>
<table><tr><th></th><th>Estimate</th><th>95% interval</th></tr>
<tr><td>a (per $1 per day)</td><td>…</td><td>…</td></tr>
<tr><td>c</td><td>…</td><td>…</td></tr>
<tr><td>R² (share explained)</td><td>…</td><td></td></tr></table>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>What the stock explains</b></div>

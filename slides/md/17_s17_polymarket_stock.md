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
  svg text { font-family: "Inter", sans-serif; }
  .iv { display: block; font-size: 14px; color: #8a95a3; font-weight: 400; }
  td { vertical-align: top; }
  .side li { font-size: 19px; }
---

# Polymarket and stock

<div class="cols">
<div class="chart">
<div class="ct">Daily Sharpe ratio in money</div>
<svg width="560" height="430" viewBox="0 0 560 430">
<line x1="70" y1="360" x2="540" y2="360" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="365" font-size="15" fill="#5b6573" text-anchor="end">−0.5</text>
<line x1="70" y1="275" x2="540" y2="275" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="280" font-size="15" fill="#5b6573" text-anchor="end">−0.25</text>
<line x1="70" y1="190" x2="540" y2="190" stroke="#1b2430" stroke-width="2"/>
<text x="62" y="195" font-size="15" fill="#5b6573" text-anchor="end">0</text>
<line x1="70" y1="105" x2="540" y2="105" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="110" font-size="15" fill="#5b6573" text-anchor="end">0.25</text>
<line x1="70" y1="20" x2="540" y2="20" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="25" font-size="15" fill="#5b6573" text-anchor="end">0.5</text>
<text x="18" y="190" font-size="17" fill="#2c3747" text-anchor="middle" transform="rotate(-90 18 190)">Daily Sharpe ratio in money</text>
<rect x="152" y="190.0" width="70" height="2.3" fill="#14365d"/>
<line x1="188" y1="91.4" x2="188" y2="305.6" stroke="#1b2430" stroke-width="1.5"/>
<line x1="178" y1="305.6" x2="198" y2="305.6" stroke="#1b2430" stroke-width="1.5"/>
<line x1="178" y1="91.4" x2="198" y2="91.4" stroke="#1b2430" stroke-width="1.5"/>
<text x="230" y="197" font-size="17" font-weight="700" fill="#1b2430">−0.01</text>
<text x="188" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Polymarket</text>
<text x="188" y="414" font-size="16" fill="#2c3747" text-anchor="middle">contracts</text>
<rect x="388" y="152.2" width="70" height="37.8" fill="#9fb3cc"/>
<line x1="422" y1="47.2" x2="422" y2="254.6" stroke="#1b2430" stroke-width="1.5"/>
<line x1="412" y1="254.6" x2="432" y2="254.6" stroke="#1b2430" stroke-width="1.5"/>
<line x1="412" y1="47.2" x2="432" y2="47.2" stroke="#1b2430" stroke-width="1.5"/>
<text x="464" y="152" font-size="17" font-weight="700" fill="#1b2430">0.11</text>
<text x="422" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Stock</text>
<text x="422" y="414" font-size="16" fill="#2c3747" text-anchor="middle">shares</text>
<text x="540" y="14" font-size="14" fill="#5b6573" text-anchor="end">Lines: 95% interval</text></svg>
<div class="xa" style="margin-left:0">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<ul>
<li>Both bars place the slide 16 bets on the same company-days. Money is dollars earned per dollar bet.</li>
<li>Polymarket bets run from midnight for 24 hours. Stock bets run from the news day's close to the next day's close.</li>
<li>Polymarket and the stock earn about the same on the same news. Both intervals include zero.</li>
<li>Quiet days have below-median Polymarket volume the day before. They do not differ from busy days.</li>
</ul>
<table><tr><th>Sharpe ratio</th><th>Daily</th><th>Yearly</th></tr>
<tr><td>Polymarket in money</td><td>−0.01<span class="iv">−0.34 to 0.29</span></td><td>−0.1<span class="iv">−5.4 to 4.6</span></td></tr>
<tr><td>Stock in money</td><td>0.11<span class="iv">−0.19 to 0.42</span></td><td>1.8<span class="iv">−3.0 to 6.7</span></td></tr>
<tr><td>Quiet minus busy days in ξ</td><td>−0.32<span class="iv">−0.84 to 0.26</span></td><td>−5.1<span class="iv">−13.4 to 4.2</span></td></tr></table>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>Polymarket and stock</b></div>

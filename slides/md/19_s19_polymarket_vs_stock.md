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
  section::before { content: "19"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
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
---

# Polymarket and stock Sharpe ratio in money

<div class="cols">
<div class="chart">
<div class="ct">Sharpe ratio in money</div>
<svg width="580" height="440" viewBox="0 0 580 440">
<line x1="70" y1="360" x2="510" y2="360" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="365" font-size="15" fill="#5b6573" text-anchor="end">−0.60</text>
<line x1="70" y1="275" x2="510" y2="275" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="280" font-size="15" fill="#5b6573" text-anchor="end">−0.30</text>
<line x1="70" y1="190" x2="510" y2="190" stroke="#1b2430" stroke-width="2"/>
<text x="62" y="195" font-size="15" fill="#5b6573" text-anchor="end">0.00</text>
<line x1="70" y1="105" x2="510" y2="105" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="110" font-size="15" fill="#5b6573" text-anchor="end">0.30</text>
<line x1="70" y1="20" x2="510" y2="20" stroke="#e3e7ec" stroke-width="1"/>
<text x="62" y="25" font-size="15" fill="#5b6573" text-anchor="end">0.60</text>
<text x="518" y="338" font-size="15" fill="#5b6573">−8.00</text>
<text x="518" y="266" font-size="15" fill="#5b6573">−4.00</text>
<text x="518" y="195" font-size="15" fill="#5b6573">0.00</text>
<text x="518" y="124" font-size="15" fill="#5b6573">4.00</text>
<text x="518" y="52" font-size="15" fill="#5b6573">8.00</text>
<text x="18" y="190" font-size="17" fill="#2c3747" text-anchor="middle" transform="rotate(-90 18 190)">Daily</text>
<text x="568" y="190" font-size="17" fill="#2c3747" text-anchor="middle" transform="rotate(90 568 190)">Yearly</text>
<rect x="148" y="190.0" width="64" height="2.0" fill="#14365d"/>
<line x1="180" y1="107.8" x2="180" y2="286.3" stroke="#1b2430" stroke-width="1.5"/>
<line x1="170" y1="286.3" x2="190" y2="286.3" stroke="#1b2430" stroke-width="1.5"/>
<line x1="170" y1="107.8" x2="190" y2="107.8" stroke="#1b2430" stroke-width="1.5"/>
<text x="180" y="78" font-size="16" font-weight="700" fill="#1b2430" text-anchor="middle">−0.01 daily</text>
<text x="180" y="97" font-size="15" fill="#5b6573" text-anchor="middle">−0.11 yearly</text>
<text x="180" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Polymarket</text>
<rect x="368" y="158.5" width="64" height="31.5" fill="#9fb3cc"/>
<line x1="400" y1="71.0" x2="400" y2="243.8" stroke="#1b2430" stroke-width="1.5"/>
<line x1="390" y1="243.8" x2="410" y2="243.8" stroke="#1b2430" stroke-width="1.5"/>
<line x1="390" y1="71.0" x2="410" y2="71.0" stroke="#1b2430" stroke-width="1.5"/>
<text x="400" y="41" font-size="16" font-weight="700" fill="#1b2430" text-anchor="middle">0.11 daily</text>
<text x="400" y="60" font-size="15" fill="#5b6573" text-anchor="middle">1.76 yearly</text>
<text x="400" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Stock</text>
<text x="510" y="414" font-size="14" fill="#5b6573" text-anchor="end">Lines: 95% interval</text></svg>
<div class="xa" style="margin-left:0">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<ul>
<li>On the same days and news we learn one set of weights for Polymarket returns and one for stock returns.</li>
<li>Polymarket bets run from midnight for 24 hours. Stock bets run from the 4pm close to the next close.</li>
<li>Neither market earns a reliable profit.</li>
</ul>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>Polymarket and stock Sharpe ratio in money</b></div>

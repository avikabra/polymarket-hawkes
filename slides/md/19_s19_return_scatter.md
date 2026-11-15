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
  .side li { font-size: 18px; margin-bottom: 9px; }
---

# Daily Polymarket return against stock return

<div class="cols">
<div class="chart">
<div class="ct">Daily return per $1 bet</div>
<svg width="560" height="440" viewBox="0 0 560 440">
<line x1="70" y1="250" x2="540" y2="250" stroke="#1b2430" stroke-width="2"/>
<line x1="305" y1="20" x2="305" y2="390" stroke="#1b2430" stroke-width="2"/>
<text x="117" y="270" font-size="14" fill="#5b6573" text-anchor="middle">−0.40%</text>
<text x="493" y="270" font-size="14" fill="#5b6573" text-anchor="middle">0.40%</text>
<text x="297" y="355" font-size="14" fill="#5b6573" text-anchor="end">−5.00%</text>
<text x="297" y="155" font-size="14" fill="#5b6573" text-anchor="end">5.00%</text>
<text x="297" y="55" font-size="14" fill="#5b6573" text-anchor="end">10.00%</text>
<line x1="70" y1="346" x2="540" y2="156" stroke="#14365d" stroke-width="2.5"/>
<line x1="70" y1="260" x2="540" y2="240" stroke="#14365d" stroke-width="2" stroke-dasharray="8 6"/>
<circle cx="329.9" cy="256.3" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="345.4" cy="301.2" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="372.7" cy="30.2" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="215.2" cy="257.2" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="256.1" cy="257.7" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="257.1" cy="298.4" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="265.5" cy="213.5" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="295.1" cy="312.0" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="255.2" cy="334.7" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="222.8" cy="270.4" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="330.4" cy="254.9" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="353.9" cy="326.7" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="145.2" cy="242.9" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="353.9" cy="223.2" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="314.9" cy="230.4" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="334.6" cy="189.4" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="242.0" cy="263.6" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="339.3" cy="257.4" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="289.5" cy="242.1" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="314.4" cy="288.3" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="318.6" cy="287.4" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="323.8" cy="222.2" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="307.4" cy="248.1" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="305.0" cy="250.0" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="313.0" cy="252.6" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="292.8" cy="335.8" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="334.1" cy="233.2" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="225.1" cy="254.1" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="328.5" cy="225.5" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="331.3" cy="215.8" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="509.4" cy="102.8" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="353.4" cy="203.3" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="302.6" cy="297.1" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<circle cx="373.6" cy="312.5" r="4.5" fill="#9fb3cc" stroke="#14365d" stroke-width="1"/>
<text x="80" y="40" font-size="15" fill="#14365d">Solid line: fit</text>
<text x="80" y="62" font-size="15" fill="#14365d">Dashed line: c = 1.00</text>
<text x="80" y="84" font-size="15" fill="#5b6573">Each dot is one test day</text>
<text x="305" y="428" font-size="17" fill="#2c3747" text-anchor="middle">Stock return per $1 bet</text>
<text x="20" y="205" font-size="17" fill="#2c3747" text-anchor="middle" transform="rotate(-90 20 205)">Polymarket return per $1 bet</text></svg>
<div class="xa" style="margin-left:0">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<ul>
<li>Each test day we placed the bets learned in ξ on both markets. We fit Polymarket return = a + c × stock return.</li>
<li>a was −0.03¢ per dollar per day. Polymarket earned nothing beyond what the stock explained.</li>
<li>c was 9.51 with an interval of −1.15 to 18.67. A contract pays $1 or nothing so its price can move many times the stock's percentage move.</li>
<li>From this fit the stock explained 17% of the daily swings in Polymarket's return.</li>
</ul>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>Daily Polymarket return against stock return</b></div>

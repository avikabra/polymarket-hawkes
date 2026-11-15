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
  .side li { font-size: 18px; margin-bottom: 6px; }
  .side td, .side th { padding: 4px 12px; }
  .iv { font-size: 13px; }

  svg text { font-family: "Inter", sans-serif; }
  .side li { font-size: 20px; margin-bottom: 12px; }
  .tb { flex: 1; display: flex; flex-direction: column; justify-content: center; }
  .tb table { font-size: 19px; width: 100%; margin-top: 0; }
  .tb td, .tb th { padding: 8px 14px; }
  .tb td.n, .tb th.n { text-align: right; }
  .chart { flex: 2.3; }
  .chart svg { height: 520px; width: auto; }
  .cols { height: 560px; }
  .big { font-size: 30px; font-weight: 700; color: #14365d; line-height: 1.3; border-left: 6px solid #14365d; padding-left: 20px; }
---

# Sharpe ratio in ξ of bets on each version of the news

<div class="cols">
<div class="chart">
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
<rect x="111" y="190.0" width="64" height="24.7" fill="#14365d"/>
<line x1="143" y1="113.5" x2="143" y2="303.3" stroke="#1b2430" stroke-width="1.5"/>
<line x1="133" y1="303.3" x2="153" y2="303.3" stroke="#1b2430" stroke-width="1.5"/>
<line x1="133" y1="113.5" x2="153" y2="113.5" stroke="#1b2430" stroke-width="1.5"/>
<text x="143" y="83" font-size="16" font-weight="700" fill="#1b2430" text-anchor="middle">−0.09 daily</text>
<text x="143" y="102" font-size="15" fill="#5b6573" text-anchor="middle">−1.39 yearly</text>
<text x="143" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">News shock</text>
<rect x="258" y="190.0" width="64" height="46.1" fill="#9fb3cc"/>
<line x1="290" y1="130.5" x2="290" y2="311.8" stroke="#1b2430" stroke-width="1.5"/>
<line x1="280" y1="311.8" x2="300" y2="311.8" stroke="#1b2430" stroke-width="1.5"/>
<line x1="280" y1="130.5" x2="300" y2="130.5" stroke="#1b2430" stroke-width="1.5"/>
<text x="290" y="100" font-size="16" font-weight="700" fill="#1b2430" text-anchor="middle">−0.16 daily</text>
<text x="290" y="120" font-size="15" fill="#5b6573" text-anchor="middle">−2.58 yearly</text>
<text x="290" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Raw news</text>
<rect x="405" y="190.0" width="64" height="28.6" fill="#9fb3cc"/>
<line x1="437" y1="102.2" x2="437" y2="297.7" stroke="#1b2430" stroke-width="1.5"/>
<line x1="427" y1="297.7" x2="447" y2="297.7" stroke="#1b2430" stroke-width="1.5"/>
<line x1="427" y1="102.2" x2="447" y2="102.2" stroke="#1b2430" stroke-width="1.5"/>
<text x="437" y="72" font-size="16" font-weight="700" fill="#1b2430" text-anchor="middle">−0.10 daily</text>
<text x="437" y="91" font-size="15" fill="#5b6573" text-anchor="middle">−1.60 yearly</text>
<text x="437" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Predictable news</text>
<text x="510" y="414" font-size="14" fill="#5b6573" text-anchor="end">Lines: 95% interval</text></svg>
<div class="xa" style="margin-left:0">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<div class="big">No version of the news earns a reliable profit. Every interval includes zero.</div>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>Sharpe ratio in ξ of bets on each version of the news</b></div>

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
---

# Results

<div class="cols">
<div class="chart">
<div class="ct">Daily Sharpe ratio in ξ</div>
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
<text x="18" y="190" font-size="17" fill="#2c3747" text-anchor="middle" transform="rotate(-90 18 190)">Daily Sharpe ratio in ξ</text>
<rect x="113" y="190.0" width="70" height="29.7" fill="#14365d"/>
<line x1="148" y1="98.2" x2="148" y2="326.0" stroke="#1b2430" stroke-width="1.5"/>
<line x1="138" y1="326.0" x2="158" y2="326.0" stroke="#1b2430" stroke-width="1.5"/>
<line x1="138" y1="98.2" x2="158" y2="98.2" stroke="#1b2430" stroke-width="1.5"/>
<text x="190" y="225" font-size="17" font-weight="700" fill="#1b2430">−0.09</text>
<text x="148" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">News shock</text>
<text x="148" y="414" font-size="16" fill="#2c3747" text-anchor="middle">u</text>
<rect x="270" y="190.0" width="70" height="55.3" fill="#9fb3cc"/>
<line x1="305" y1="118.6" x2="305" y2="336.2" stroke="#1b2430" stroke-width="1.5"/>
<line x1="295" y1="336.2" x2="315" y2="336.2" stroke="#1b2430" stroke-width="1.5"/>
<line x1="295" y1="118.6" x2="315" y2="118.6" stroke="#1b2430" stroke-width="1.5"/>
<text x="347" y="250" font-size="17" font-weight="700" fill="#1b2430">−0.16</text>
<text x="305" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Raw news</text>
<text x="305" y="414" font-size="16" fill="#2c3747" text-anchor="middle">E</text>
<rect x="427" y="190.0" width="70" height="34.3" fill="#9fb3cc"/>
<line x1="462" y1="84.6" x2="462" y2="319.2" stroke="#1b2430" stroke-width="1.5"/>
<line x1="452" y1="319.2" x2="472" y2="319.2" stroke="#1b2430" stroke-width="1.5"/>
<line x1="452" y1="84.6" x2="472" y2="84.6" stroke="#1b2430" stroke-width="1.5"/>
<text x="504" y="229" font-size="17" font-weight="700" fill="#1b2430">−0.10</text>
<text x="462" y="392" font-size="18" font-weight="700" fill="#14365d" text-anchor="middle">Predictable news</text>
<text x="462" y="414" font-size="16" fill="#2c3747" text-anchor="middle">Sβ̂</text>
<text x="540" y="14" font-size="14" fill="#5b6573" text-anchor="end">Lines: 95% interval</text></svg>
<div class="xa" style="margin-left:0">Test days: Aug 28 to Oct 29, 2026</div>
</div>

<div class="side">
<ul>
<li>No portfolio earns a reliable profit in ξ. Every interval includes zero.</li>
<li>In log-odds the news shock looks profitable. In money it loses. Log-odds counts a move from 1¢ to 2¢ as large.</li>
</ul>
<table><tr><th>Sharpe ratio</th><th>Daily</th><th>Yearly</th></tr>
<tr><td>News shock in ξ</td><td>−0.09<span class="iv">−0.40 to 0.27</span></td><td>−1.4<span class="iv">−6.3 to 4.3</span></td></tr>
<tr><td>Raw news in ξ</td><td>−0.16<span class="iv">−0.43 to 0.21</span></td><td>−2.6<span class="iv">−6.8 to 3.4</span></td></tr>
<tr><td>Predictable news in ξ</td><td>−0.10<span class="iv">−0.38 to 0.31</span></td><td>−1.6<span class="iv">−6.0 to 4.9</span></td></tr>
<tr><td>News shock in money</td><td>−0.14<span class="iv">−0.42 to 0.10</span></td><td>−2.2<span class="iv">−6.7 to 1.6</span></td></tr>
<tr><td>News shock in log-odds</td><td>0.28<span class="iv">0.05 to 0.51</span></td><td>4.5<span class="iv">0.7 to 8.2</span></td></tr></table>
</div>
</div>

<div class="trk">Part II: Prediction &rsaquo; <b>Results</b></div>

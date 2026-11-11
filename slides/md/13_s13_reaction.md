---
marp: true
theme: default
paginate: true
style: |
  section { font-family: "Inter", sans-serif; padding: 44px 64px; color: #1b2430; }
  h1 { font-size: 44px; color: #14365d; margin: 0 0 16px 0; }
  h3 { font-size: 27px; font-weight: 500; line-height: 1.3; margin: 0 0 20px 0; }
  h4 { font-size: 22px; color: #14365d; margin: 14px 0 6px 0; text-transform: uppercase; letter-spacing: 0.04em; }
  p { font-size: 22px; margin: 6px 0; }
  table { font-size: 20px; width: 100%; border-collapse: collapse; }
  th { background: #14365d; color: #fff; text-align: left; padding: 7px 12px; }
  td { padding: 8px 12px; border-bottom: 1px solid #d9dee5; vertical-align: top; }
  td:first-child { width: 14%; white-space: nowrap; font-family: "Times New Roman", Georgia, serif; font-size: 24px; }
  .eq { font-family: "Times New Roman", Georgia, serif; font-size: 40px; text-align: center; background: #eef3f9; border-left: 6px solid #14365d; padding: 12px 10px; margin: 8px 0 12px 0; }
  .eq sub { font-size: 26px; }
  .frac { display: inline-block; vertical-align: middle; text-align: center; margin: 0 4px; }
  .frac > span { display: block; padding: 0 6px; }
  .frac > span:first-child { border-bottom: 2px solid #1b2430; }

  h1 { margin: 0 0 12px 0; }
  .cols { display: flex; gap: 22px; height: 548px; }
  .steps { flex: 1; display: flex; flex-direction: column; }
  .st { flex: 1; display: flex; gap: 16px; align-items: center; border-bottom: 1px solid #d9dee5; padding: 4px 0; }
  .st:last-child { border-bottom: none; }
  .nb { width: 44px; height: 44px; border-radius: 50%; background: #14365d; color: #fff; font-size: 24px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex: none; }
  .st .t { font-size: 24px; font-weight: 700; color: #14365d; margin-bottom: 3px; }
  .st .d { font-size: 19px; line-height: 1.32; }
  .eq { font-family: "Times New Roman", Georgia, serif; font-size: 28px; background: #eef3f9; border-left: 5px solid #14365d; padding: 6px 14px; margin: 8px 0 2px 0; display: inline-block; }
  .frac { display: inline-block; vertical-align: middle; text-align: center; margin: 0 3px; }
  .frac > span { display: block; padding: 0 5px; line-height: 1.15; }
  .frac > span:first-child { border-bottom: 2px solid #1b2430; }
  .panel { flex: 0 0 560px; background: #eef3f9; border-left: 6px solid #14365d; padding: 16px 20px; display: flex; flex-direction: column; }
  .panel .pt { font-size: 22px; font-weight: 700; color: #14365d; line-height: 1.25; }
  .panel .ps { font-size: 17px; line-height: 1.3; color: #3a4658; margin: 3px 0 8px 0; }
  .rows { flex: 1; display: flex; flex-direction: column; justify-content: space-between; }
  .r { display: flex; align-items: center; gap: 12px; }
  .r .lb { width: 190px; flex: none; }
  .r .l1 { font-size: 18px; font-weight: 700; color: #14365d; line-height: 1.15; }
  .r .l2 { font-size: 15px; white-space: nowrap; color: #5b6573; margin-top: 1px; }
  .r .bw { flex: 1; display: flex; align-items: center; gap: 8px; }
  .r .bf { height: 30px; background: #7f98ba; flex: none; }
  .r .bv { font-size: 19px; font-weight: 700; color: #1b2430; }
  .pm { font-size: 14px; font-weight: 700; color: #14365d; background: #dbe6f3; padding: 1px 7px; margin: 2px 0 0 0; white-space: nowrap; display: inline-block; font-family: "Inter", sans-serif; }
  math { font-family: "Latin Modern Math", "STIX Two Math", "Cambria Math", "Times New Roman", serif; font-size: 1.12em; }
  .cr { display: flex; align-items: center; gap: 12px; }
  .cr .cn { width: 160px; flex: none; font-size: 19px; font-weight: 700; color: #14365d; }
  .cr .cf { font-size: 21px; line-height: 1.2; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .panel { flex: 0 0 520px !important; }
  .cr .cn { width: 138px !important; font-size: 18px !important; }
  .cr .cf { font-size: 20px !important; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .panel { flex: 0 0 530px !important; }
  .cr .cn { width: 152px !important; font-size: 17.5px !important; }
  .cr .cf { font-size: 20px !important; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .frow { display: flex; gap: 8px; align-items: stretch; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 530px !important; }
  .cr .cn { width: 152px !important; font-size: 17.5px !important; }
  .cr .cf { font-size: 20px !important; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .frow { display: flex; gap: 8px; align-items: stretch; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .frow { display: flex; gap: 8px; align-items: stretch; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .frow { display: flex; gap: 8px; align-items: stretch; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .g { align-items: stretch; }
  .frow { display: flex; gap: 8px; align-items: stretch; flex: 1; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .g { align-items: stretch; }
  .frow { display: flex; gap: 8px; align-items: stretch; flex: 1; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .g { align-items: stretch; }
  .frow { display: flex; gap: 8px; align-items: stretch; flex: 1; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .g { align-items: stretch; }
  .frow { display: flex; gap: 8px; align-items: stretch; flex: 1; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .flow { flex: 1; display: flex; flex-direction: column; height: 548px; }
  .g { align-items: stretch; }
  .frow { display: flex; gap: 8px; align-items: stretch; flex: 1; }
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .g { flex: 1; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
  .sp2 { grid-column: span 2; } .sp3 { grid-column: span 3; } .sp4 { grid-column: span 4; }
  .fb { flex: 1; border: 1.5px solid #14365d; background: #fff; padding: 6px 10px 7px 10px; box-sizing: border-box; }
  .fb .h { font-size: 16px; font-weight: 700; color: #14365d; margin-bottom: 2px; }
  .fb .t { font-size: 14.5px; line-height: 1.34; }
  .fb math { font-size: 1.12em; }
  .fb.dk { background: #14365d; border-color: #14365d; }
  .fb.dk .h, .fb.dk .t { color: #fff; }
  .fb.lt { background: #eef3f9; }
  .panel { flex: 0 0 478px !important; }
  .cr .cn { width: 128px !important; font-size: 16.5px !important; }
  .cr .cf { font-size: 19px !important; }
  .eqline { font-size: 17px; margin: 3px 0 4px 0; }
  .fb { overflow-wrap: anywhere; }
  .ar { padding-left: 38px; text-align: center; color: #14365d; font-size: 20px; line-height: 22px; font-weight: 700; }
  .fb .eqs { font-size: 18px; margin-top: 3px; }
  .cr .cg { font-size: 14px; color: #5b6573; margin-top: 1px; }
  .idx { font-size: 17px; padding: 0 4px 6px 4px; color: #2c3747; }
  .row { display: flex; gap: 12px; height: 236px; align-items: stretch; }
  .row .sn { align-self: center; margin: 0; }
  .lt { flex: 1; display: flex; flex-direction: column; justify-content: center; min-width: 0; }
  .lt .tt { font-size: 27px; font-weight: 700; color: #14365d; margin-bottom: 4px; }
  .lt .dd { font-size: 20px; line-height: 1.3; }
  .cr2 { display: flex; flex-direction: column; gap: 5px; margin-top: 8px; }
  .cr2 div { font-size: 19px; line-height: 1.25; border: 1.5px solid #14365d; background: #fff; padding: 4px 10px; align-self: flex-start; }
  .rt { flex: 1.1; background: #eef3f9; border-left: 5px solid #14365d; padding: 10px 18px; display: flex; flex-direction: column; justify-content: center; min-width: 0; }
  .rt .e { font-size: 36px; }
  .rt .n { font-size: 20px; line-height: 1.35; color: #2c3747; margin-top: 8px; }
  .ar { margin-left: 0; width: 30px; text-align: center; color: #14365d; font-size: 18px; line-height: 20px; height: 20px; font-weight: 700; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 11px; }
  section::after { display: none; }
  section::before { content: "13"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# Polymarket reaction

<div class="idx">Indices: <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>k</mi></mrow></math></span> is a company, <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>c</mi></mrow></math></span> is a contract, <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span> is a day, and <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>m</mi><mi>d</mi></msub></mrow></math></span> is the midnight after day <span style="white-space:nowrap"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>.</span></div>

<div class="row"><div class="sn">1</div>
<div class="lt"><div class="tt">Contract reaction</div><div class="dd">The change in a contract's log-odds over the 24 hours after day <span style="white-space:nowrap"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>.</span> The sign flips if YES pays when the stock falls.</div></div>
<div class="rt"><div class="e"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>y</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>=</mo><msub><mi mathvariant="normal">ℓ</mi><mi>c</mi></msub><mo stretchy="false">(</mo><msub><mi>m</mi><mi>d</mi></msub><mo>+</mo><mn>24</mn><mtext> </mtext><mi mathvariant="normal">h</mi><mo stretchy="false">)</mo><mo>−</mo><msub><mi mathvariant="normal">ℓ</mi><mi>c</mi></msub><mo stretchy="false">(</mo><msub><mi>m</mi><mi>d</mi></msub><mo stretchy="false">)</mo></mrow></math></span></div><div class="n"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi mathvariant="normal">ℓ</mi><mi>c</mi></msub><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo></mrow></math></span> is the log-odds of contract <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>c</mi></mrow></math></span>'s last trade before time <span style="white-space:nowrap"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>t</mi></mrow></math></span>.</span> <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>y</mi><mo>&gt;</mo><mn>0</mn></mrow></math></span> means good news for the stock. A contract that resolves inside the 24 hours uses its last trade before resolution.</div></div></div>
<div class="ar">&darr;</div>
<div class="row"><div class="sn">2</div>
<div class="lt"><div class="tt">Company reaction</div><div class="dd">The dollar-weighted average of the company's contract reactions. A contract is included when it meets three criteria:</div>
<div class="cr2"><div>Open at <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>m</mi><mi>d</mi></msub></mrow></math></span></div><div>$1,000 traded through day <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span></div><div>Trades in the 24 hours</div></div></div>
<div class="rt"><div class="e"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>y</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>=</mo><mstyle scriptlevel="0" displaystyle="true"><mfrac><mrow><munder><mo>∑</mo><mrow><mi>c</mi><mo>∈</mo><mi>k</mi></mrow></munder><msub><mi>w</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mtext> </mtext><msub><mi>y</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow><mrow><munder><mo>∑</mo><mrow><mi>c</mi><mo>∈</mo><mi>k</mi></mrow></munder><msub><mi>w</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></mfrac></mstyle></mrow></math></span></div><div class="n"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>w</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span> is the dollars traded in contract <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>c</mi></mrow></math></span> on day <span style="white-space:nowrap"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>.</span></div></div></div>
<div class="trk">Part II: Prediction &rsaquo; <b>Polymarket reaction</b></div>

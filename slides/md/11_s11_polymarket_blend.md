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
  .sn { flex: none; width: 30px; height: 30px; border-radius: 50%; background: #14365d; color: #fff; font-weight: 700; font-size: 17px; display: flex; align-items: center; justify-content: center; margin-top: 4px; }
  .nr { display: flex; gap: 8px; }
  .nr > .rb { flex: 1; min-width: 0; }
  .ar { padding-left: 38px; text-align: center; color: #14365d; font-size: 17px; line-height: 20px; height: 20px; font-weight: 700; }
  .idx { font-size: 16px; padding: 2px 4px 6px 4px; color: #2c3747; }
  .r1 { display: flex; gap: 10px; height: 156px; }
  .b1 { background: #eef3f9; border-left: 5px solid #14365d; padding: 7px 12px; display: flex; flex-direction: column; box-sizing: border-box; }
  .lab { font-size: 13.5px; font-weight: 700; color: #5b6573; text-transform: uppercase; letter-spacing: 0.05em; }
  .b1 .e { font-size: 21px; padding: 4px 0 3px 0; }
  .b1 .n { font-size: 14.5px; line-height: 1.3; color: #2c3747; }
  .r2 { display: flex; gap: 12px; margin-top: 0; height: 200px; }
  .card { flex: 1; border: 1.5px solid #14365d; display: flex; flex-direction: column; }
  .card .ch { background: #14365d; color: #fff; font-size: 21px; font-weight: 700; padding: 5px 14px; }
  .card .ce { font-size: 23px; padding: 6px 12px; text-align: center; background: #f6f9fc; border-bottom: 1px solid #c3cfde; min-height: 60px; display: flex; align-items: center; justify-content: center; }
  .card .cdv { font-size: 16.5px; line-height: 1.3; padding: 6px 14px; }
  .r3 { display: flex; gap: 20px; margin-top: 0; height: 140px; background: #eef3f9; border-left: 6px solid #14365d; padding: 8px 18px; box-sizing: border-box; }
  .r3 .l { flex: 0.9; display: flex; flex-direction: column; justify-content: center; }
  .r3 .t { font-size: 22px; font-weight: 700; color: #14365d; margin-bottom: 2px; }
  .r3 .q { font-size: 20px; line-height: 1.5; }
  .r3 .rg { flex: 1.35; display: flex; flex-direction: column; justify-content: center; border-left: 1px solid #c3cfde; padding-left: 18px; }
  .r3 .rg .q { margin-bottom: 3px; }
  .lg { display: grid; grid-template-columns: 60px 1fr; row-gap: 1px; font-size: 15px; line-height: 1.28; align-items: center; }
  .lg > div:nth-child(odd) { font-size: 16px; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 11px; }
  section::after { display: none; }
  section::before { content: "11"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# Polymarket characteristics

<div class="idx">Indices: <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>k</mi></mrow></math></span> is a company, <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>c</mi></mrow></math></span> is one of its contracts, <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span> is a day, and <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>t</mi></mrow></math></span> is a month.</div>

<div class="nr"><div class="sn">1</div><div class="rb">
<div class="r1">
<div class="b1" style="flex:0.8"><div class="lab">Log-odds</div><div class="e"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi mathvariant="normal">ℓ</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>=</mo><mi>ln</mi><mo>⁡</mo><mstyle scriptlevel="0" displaystyle="true"><mfrac><msub><mi>p</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mrow><mn>1</mn><mo>−</mo><msub><mi>p</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></mfrac></mstyle></mrow></math></span></div><div class="n"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>p</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span> is the contract's YES price.</div></div>
<div class="b1" style="flex:1.35"><div class="lab">Contract change</div><div class="e"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi mathvariant="normal">Δ</mi><msub><mi mathvariant="normal">ℓ</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>=</mo><msubsup><mi mathvariant="normal">ℓ</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">l</mi><mi mathvariant="normal">a</mi><mi mathvariant="normal">s</mi><mi mathvariant="normal">t</mi></mrow></msubsup><mo>−</mo><msubsup><mi mathvariant="normal">ℓ</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">p</mi><mi mathvariant="normal">r</mi><mi mathvariant="normal">e</mi><mi mathvariant="normal">v</mi></mrow></msubsup></mrow></math></span></div><div class="n">Last trade today minus the previous last trade. The sign flips if YES pays when the stock falls. Closing buckets are left out.</div></div>
<div class="b1" style="flex:1.75"><div class="lab">Company change</div><div class="e"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msubsup><mi mathvariant="normal">Δ</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msubsup><mo>=</mo><mstyle scriptlevel="0" displaystyle="true"><mfrac><mrow><munder><mo>∑</mo><mrow><mi>c</mi><mo>∈</mo><mi>k</mi></mrow></munder><msub><mi>w</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mtext> </mtext><mi mathvariant="normal">Δ</mi><msub><mi mathvariant="normal">ℓ</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow><mrow><munder><mo>∑</mo><mrow><mi>c</mi><mo>∈</mo><mi>k</mi></mrow></munder><msub><mi>w</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></mfrac></mstyle></mrow></math></span></div><div class="n">One number per company and day, like a stock return. <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>w</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span> is the dollars traded in contract <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>c</mi></mrow></math></span> on day <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>, so busier contracts count more.</div></div>
<div class="b1" style="flex:0.8"><div class="lab">Dollars</div><div class="e"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>V</mi><msubsup><mtext> </mtext><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msubsup><mo>=</mo><msub><mo>∑</mo><mrow><mi>c</mi><mo>∈</mo><mi>k</mi></mrow></msub><msub><mi>w</mi><mrow><mi>c</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span></div><div class="n">Dollars traded across the company's contracts on day <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>.</div></div>
</div>

</div></div>
<div class="ar">&darr;</div>
<div class="nr"><div class="sn">2</div><div class="rb">
<div class="r2">
<div class="card"><div class="ch">Momentum</div><div class="ce"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mo>∑</mo><mrow><mi>d</mi><mtext> </mtext><mo>∈</mo><mtext> </mtext><mo stretchy="false">(</mo><mi>t</mi><mo>−</mo><mn>12</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow><mo separator="true">,</mo><mtext>  </mtext><mi>t</mi><mo>−</mo><mn>1</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow><mo stretchy="false">]</mo></mrow></msub><msubsup><mi mathvariant="normal">Δ</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msubsup></mrow></math></span></div><div class="cdv">Stock momentum multiplies <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mo stretchy="false">(</mo><mn>1</mn><mo>+</mo><mi>r</mi><mo stretchy="false">)</mo></mrow></math></span>. Log-odds changes add, so we sum them. The window is the past year, skipping the latest month. It starts in late 2026.</div></div>
<div class="card"><div class="ch">Volatility</div><div class="ce"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mrow><mi mathvariant="normal">s</mi><mi mathvariant="normal">d</mi></mrow><mrow><mi>d</mi><mtext> </mtext><mo>∈</mo><mtext> </mtext><mn>1</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow></mrow></msub><mtext> ⁣</mtext><mrow><mo fence="true">(</mo><msubsup><mi mathvariant="normal">Δ</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msubsup><mo fence="true">)</mo></mrow></mrow></math></span></div><div class="cdv">The standard deviation of daily <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msup><mi mathvariant="normal">Δ</mi><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msup></mrow></math></span> over the days <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span> of the last month.</div></div>
<div class="card"><div class="ch">Illiquidity</div><div class="ce"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">e</mi><mi mathvariant="normal">a</mi><mi mathvariant="normal">n</mi></mrow><mrow><mi>d</mi><mtext> </mtext><mo>∈</mo><mtext> </mtext><mn>6</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow></mrow></msub><mtext> ⁣</mtext><mrow><mo fence="true">(</mo><mstyle scriptlevel="0" displaystyle="true"><mfrac><mrow><mi mathvariant="normal">∣</mi><msubsup><mi mathvariant="normal">Δ</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msubsup><mi mathvariant="normal">∣</mi></mrow><mrow><mi>V</mi><msubsup><mtext> </mtext><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msubsup></mrow></mfrac></mstyle><mo fence="true">)</mo></mrow><mo>×</mo><msup><mn>10</mn><mn>6</mn></msup></mrow></math></span></div><div class="cdv">How far the Polymarket price moves per $1 million traded, averaged over the days of the last six months.</div></div>
</div>

</div></div>
<div class="ar">&darr;</div>
<div class="nr"><div class="sn">3</div><div class="rb">
<div class="r3">
<div class="l"><div class="t">Blend the ranks</div><div class="q"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mtext>combined</mtext><mo>=</mo><mo stretchy="false">(</mo><mn>1</mn><mo>−</mo><mi>w</mi><mo stretchy="false">)</mo><mtext> </mtext><msub><mtext>rank</mtext><mrow><mi mathvariant="normal">s</mi><mi mathvariant="normal">t</mi><mi mathvariant="normal">o</mi><mi mathvariant="normal">c</mi><mi mathvariant="normal">k</mi></mrow></msub><mo>+</mo><mi>w</mi><mtext> </mtext><msub><mtext>rank</mtext><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msub></mrow></math></span></div><div class="q"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>w</mi><mo>=</mo><mstyle scriptlevel="0" displaystyle="true"><mfrac><mrow><mi mathvariant="normal">∣</mi><msub><mover accent="true"><mi>β</mi><mo>^</mo></mover><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msub><mi mathvariant="normal">∣</mi></mrow><mrow><mi mathvariant="normal">∣</mi><msub><mover accent="true"><mi>β</mi><mo>^</mo></mover><mrow><mi mathvariant="normal">s</mi><mi mathvariant="normal">t</mi><mi mathvariant="normal">o</mi><mi mathvariant="normal">c</mi><mi mathvariant="normal">k</mi></mrow></msub><mi mathvariant="normal">∣</mi><mo>+</mo><mi mathvariant="normal">∣</mi><msub><mover accent="true"><mi>β</mi><mo>^</mo></mover><mrow><mi mathvariant="normal">P</mi><mi mathvariant="normal">M</mi></mrow></msub><mi mathvariant="normal">∣</mi></mrow></mfrac></mstyle></mrow></math></span></div></div>
<div class="rg"><div class="q"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>E</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>=</mo><msub><mi>S</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mtext> </mtext><mi>β</mi><mo>+</mo><msub><mi>u</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span></div>
<div class="lg"><div><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>E</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span></div><div>Company <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>k</mi></mrow></math></span>'s average article embedding on day <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>: 2,560 numbers.</div><div><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>S</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span></div><div>Its 28 characteristic ranks on day <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>.</div><div><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mover accent="true"><mi>β</mi><mo>^</mo></mover></mrow></math></span></div><div>Slopes from regressing <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>E</mi></mrow></math></span> on <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>S</mi></mrow></math></span>. Each day <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>, we fit them on the company-days of the month before <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>, pooled over all companies.</div><div><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi mathvariant="normal">∣</mi><msub><mover accent="true"><mi>β</mi><mo>^</mo></mover><mi>j</mi></msub><mi mathvariant="normal">∣</mi></mrow></math></span></div><div>The length of the 2,560 slopes on characteristic <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>j</mi></mrow></math></span>.</div></div></div>
</div>
</div></div>
<div class="trk">Part II: Prediction &rsaquo; <b>Polymarket characteristics</b></div>

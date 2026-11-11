---
marp: true
theme: default
paginate: true
style: |
    section { font-family: "Helvetica Neue", Arial, sans-serif; padding: 44px 64px; color: #1b2430; }
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
  .pm { font-size: 14px; font-weight: 700; color: #14365d; background: #dbe6f3; padding: 1px 7px; margin: 2px 0 0 0; white-space: nowrap; display: inline-block; font-family: "Helvetica Neue", Arial, sans-serif; }
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
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
---

# Stock characteristics

<div class="cols">
<div class="flow">
<div class="frow"><div class="sn">1</div><div class="g">
<div class="fb sp2"><div class="h">Stock data</div><div class="t">Yahoo Finance: prices, volume, SPY, Treasury bill rate, and statements. Market cap: <span style="font-size:12.5px">companiesmarketcap.com</span>.</div></div>
<div class="fb sp2"><div class="h">Polymarket trades</div><div class="t">The price and dollar size of every trade (slide 9).</div></div>
<div class="fb sp2"><div class="h">Matched articles</div><div class="t">The articles matched to each company (slides 6 to 8).</div></div>
</div></div>
<div class="ar">&darr;</div>
<div class="frow"><div class="sn">2</div><div class="g">
<div class="fb sp4"><div class="h">Characteristics S</div><div class="t">28 columns: 8 stock, 3 Polymarket (slide 11), 16 industry indicators, and a constant. A statement counts 4 months after its period ends. Each day, we rank the companies on each column. Rank <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>ρ</mi></mrow></math></span> out of <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>n</mi></mrow></math></span> becomes <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>x</mi><mo>=</mo><mn>2</mn><mtext> </mtext><mstyle scriptlevel="0" displaystyle="true"><mfrac><mrow><mi>ρ</mi><mo>−</mo><mn>1</mn></mrow><mrow><mi>n</mi><mo>−</mo><mn>1</mn></mrow></mfrac></mstyle><mo>−</mo><mn>1</mn></mrow></math></span>, from &minus;1 to +1.</div></div>
<div class="fb sp2"><div class="h">Embedding E</div><div class="t">The average embedding of a company's matched articles on one day: 2,560 numbers.</div></div>
</div></div>
<div class="ar">&darr;</div>
<div class="frow"><div class="sn">3</div><div class="g">
<div class="fb sp3 dk"><div class="h">Regression, one per day d</div><div class="t"><div class="eqline"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>E</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>=</mo><msub><mi>S</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mtext> </mtext><mi>β</mi><mo>+</mo><msub><mi>u</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub></mrow></math></span></div><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>k</mi></mrow></math></span> is a company and <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span> is a day. Rows: every company-day with at least one matched article, in the month before <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span>. All companies share one <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>β</mi></mrow></math></span>.</div></div>
<div class="fb sp3 dk"><div class="h">News shock on day d</div><div class="t"><div class="eqline"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>u</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>=</mo><msub><mi>E</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo>−</mo><msub><mi>S</mi><mrow><mi>k</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><msub><mover accent="true"><mi>β</mi><mo>^</mo></mover><mi>d</mi></msub></mrow></math></span></div>The part of company <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>k</mi></mrow></math></span>'s news on day <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi></mrow></math></span> left after the characteristics' prediction. We then move to <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>d</mi><mo>+</mo><mn>1</mn></mrow></math></span> and fit again.</div></div>
</div></div>
</div>
<div class="panel">
<div class="pt">Definitions</div>
<div class="ps"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>r</mi></mrow></math></span> is a stock's return with dividends, over a day (<span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>r</mi><mi>d</mi></msub></mrow></math></span>) or a month (<span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>r</mi><mi>t</mi></msub></mrow></math></span>). <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>r</mi><mi>m</mi></msub></mrow></math></span> is SPY's return and <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>r</mi><mi>f</mi></msub></mrow></math></span> the 3-month Treasury bill rate, over the same period. <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>V</mi><mi>d</mi></msub></mrow></math></span> is dollar volume: closing price times shares traded. <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi mathvariant="normal">B</mi><mi mathvariant="normal">E</mi></mrow></math></span> is book equity, <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi mathvariant="normal">M</mi><mi mathvariant="normal">E</mi></mrow></math></span> market cap, and <span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>A</mi></mrow></math></span> total assets.</div>
<div class="rows">
<div class="cr"><div class="cn">Beta</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mi>β</mi><mo>=</mo><mstyle scriptlevel="0" displaystyle="true"><mfrac><mrow><msub><mrow><mi mathvariant="normal">C</mi><mi mathvariant="normal">o</mi><mi mathvariant="normal">v</mi></mrow><mrow><mn>60</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow></mrow></msub><mo stretchy="false">(</mo><msub><mi>r</mi><mi>t</mi></msub><mo>−</mo><msub><mi>r</mi><mrow><mi>f</mi><mo separator="true">,</mo><mi>t</mi></mrow></msub><mo separator="true">,</mo><mtext>  </mtext><msub><mi>r</mi><mrow><mi>m</mi><mo separator="true">,</mo><mi>t</mi></mrow></msub><mo>−</mo><msub><mi>r</mi><mrow><mi>f</mi><mo separator="true">,</mo><mi>t</mi></mrow></msub><mo stretchy="false">)</mo></mrow><mrow><msub><mrow><mi mathvariant="normal">V</mi><mi mathvariant="normal">a</mi><mi mathvariant="normal">r</mi></mrow><mrow><mn>60</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow></mrow></msub><mo stretchy="false">(</mo><msub><mi>r</mi><mrow><mi>m</mi><mo separator="true">,</mo><mi>t</mi></mrow></msub><mo>−</mo><msub><mi>r</mi><mrow><mi>f</mi><mo separator="true">,</mo><mi>t</mi></mrow></msub><mo stretchy="false">)</mo></mrow></mfrac></mstyle></mrow></math></span></div></div>
<div class="cr"><div class="cn">Size</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mrow><mi mathvariant="normal">M</mi><mi mathvariant="normal">E</mi></mrow><mo>=</mo><mtext>market cap</mtext></mrow></math></span></div></div>
<div class="cr"><div class="cn">Book-to-market</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mrow><mi mathvariant="normal">B</mi><mi mathvariant="normal">E</mi></mrow><mtext> </mtext><mi mathvariant="normal">/</mi><mtext> </mtext><mrow><mi mathvariant="normal">M</mi><mi mathvariant="normal">E</mi></mrow></mrow></math></span></div></div>
<div class="cr"><div class="cn">Profitability</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mo stretchy="false">(</mo><mrow><mi mathvariant="normal">E</mi><mi mathvariant="normal">B</mi><mi mathvariant="normal">I</mi><mi mathvariant="normal">T</mi><mi mathvariant="normal">D</mi><mi mathvariant="normal">A</mi></mrow><mo>−</mo><mtext>interest</mtext><mo stretchy="false">)</mo><mtext> </mtext><mi mathvariant="normal">/</mi><mtext> </mtext><mrow><mi mathvariant="normal">B</mi><mi mathvariant="normal">E</mi></mrow></mrow></math></span></div></div>
<div class="cr"><div class="cn">Investment</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mi>A</mi><mi>t</mi></msub><mtext> </mtext><mi mathvariant="normal">/</mi><mtext> </mtext><msub><mi>A</mi><mrow><mi>t</mi><mo>−</mo><mn>1</mn><mtext> </mtext><mrow><mi mathvariant="normal">y</mi><mi mathvariant="normal">r</mi></mrow></mrow></msub><mo>−</mo><mn>1</mn></mrow></math></span></div></div>
<div class="cr"><div class="cn">Momentum</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><mo stretchy="false">(</mo><mn>1</mn><mo>+</mo><msub><mi>r</mi><mrow><mi>t</mi><mo>−</mo><mn>11</mn></mrow></msub><mo stretchy="false">)</mo><mo>×</mo><mo>⋯</mo><mo>×</mo><mo stretchy="false">(</mo><mn>1</mn><mo>+</mo><msub><mi>r</mi><mrow><mi>t</mi><mo>−</mo><mn>1</mn></mrow></msub><mo stretchy="false">)</mo><mo>−</mo><mn>1</mn></mrow></math></span></div></div>
<div class="cr"><div class="cn">Volatility</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mrow><mi mathvariant="normal">s</mi><mi mathvariant="normal">d</mi></mrow><mrow><mn>1</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow></mrow></msub><mo stretchy="false">(</mo><msub><mi>r</mi><mi>d</mi></msub><mo>−</mo><msub><mi>r</mi><mrow><mi>f</mi><mo separator="true">,</mo><mi>d</mi></mrow></msub><mo stretchy="false">)</mo></mrow></math></span></div></div>
<div class="cr"><div class="cn">Illiquidity</div><div class="cf"><span class="katex"><math xmlns="http://www.w3.org/1998/Math/MathML"><mrow><msub><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">e</mi><mi mathvariant="normal">a</mi><mi mathvariant="normal">n</mi></mrow><mrow><mn>6</mn><mtext> </mtext><mrow><mi mathvariant="normal">m</mi><mi mathvariant="normal">o</mi></mrow></mrow></msub><mtext> ⁣</mtext><mrow><mo fence="true">(</mo><mi mathvariant="normal">∣</mi><msub><mi>r</mi><mi>d</mi></msub><mi mathvariant="normal">∣</mi><mtext> </mtext><mi mathvariant="normal">/</mi><mtext> </mtext><msub><mi>V</mi><mi>d</mi></msub><mo fence="true">)</mo></mrow><mo>×</mo><msup><mn>10</mn><mn>6</mn></msup></mrow></math></span><div class="cg">Return move per $1 million traded. |r|/V is per dollar, so we scale by 10<sup>6</sup>.</div></div></div>
<div class="cr"><div class="cn">Industry</div><div class="cf">17 groups, 16 yes/no indicators</div></div>
</div>
</div>
</div>
<div class="trk">Part II: Prediction &rsaquo; <b>Stock characteristics</b></div>

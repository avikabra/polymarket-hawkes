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
  .steps { flex: 1.12; display: flex; flex-direction: column; }
  .st { flex: 1; display: flex; gap: 16px; align-items: center; border-bottom: 1px solid #d9dee5; padding: 4px 0; }
  .st:last-child { border-bottom: none; }
  .nb { width: 44px; height: 44px; border-radius: 50%; background: #14365d; color: #fff; font-size: 24px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex: none; }
  .st .t { font-size: 24px; font-weight: 700; color: #14365d; margin-bottom: 3px; }
  .st .d { font-size: 19px; line-height: 1.32; }
  .eq { font-family: "Times New Roman", Georgia, serif; font-size: 28px; background: #eef3f9; border-left: 5px solid #14365d; padding: 6px 14px; margin: 8px 0 2px 0; display: inline-block; }
  .frac { display: inline-block; vertical-align: middle; text-align: center; margin: 0 3px; }
  .frac > span { display: block; padding: 0 5px; line-height: 1.15; }
  .frac > span:first-child { border-bottom: 2px solid #1b2430; }
  .panel { flex: 1; background: #eef3f9; border-left: 6px solid #14365d; padding: 16px 20px; display: flex; flex-direction: column; }
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
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 11px; }
  section::after { display: none; }
  section::before { content: "9"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# Polymarket contracts and trades

<div class="cols">
<div class="steps">
<div class="st"><div class="nb">1</div><div><div class="t">Price as log-odds</div><div class="d">A Polymarket contract pays $1 if its event occurs. Its YES price is the market's probability of that event. We store each price as a probability p and as log-odds:</div><div class="eq">&ell; = ln<span class="frac"><span>p</span><span>1 &minus; p</span></span></div></div></div>
<div class="st"><div class="nb">2</div><div><div class="t">Pull the contracts</div><div class="d">We pull the 22,563 contracts tagged with one of our 61 tickers.</div></div></div>
<div class="st"><div class="nb">3</div><div><div class="t">Pull the trades</div><div class="d">We pull every trade in those contracts: 832,257 trades worth $51.3M, from Sep 26, 2025 to Oct 29, 2026. Each trade has a timestamp, price, dollar size, and side.</div></div></div>
</div>
<div class="panel">
<div class="pt">Contracts by type</div>
<div class="ps">The 22,563 contracts sit in 2,536 events. An event holds one or more contracts. A price ladder has one contract per strike.</div>
<div class="rows">
<div class="r"><div class="lb"><div class="l1">Barrier ladder</div><div class="l2">Touch a price</div></div><div class="bw"><div class="bf" style="width:230px"></div><div class="bv">8,755</div></div></div>
<div class="r"><div class="lb"><div class="l1">Close ladder</div><div class="l2">Close above a price</div></div><div class="bw"><div class="bf" style="width:194px"></div><div class="bv">7,400</div></div></div>
<div class="r"><div class="lb"><div class="l1">Closing bucket</div><div class="l2">Close in a range</div></div><div class="bw"><div class="bf" style="width:134px"></div><div class="bv">5,094</div></div></div>
<div class="r"><div class="lb"><div class="l1">Up or down</div><div class="l2">Close vs prior close</div></div><div class="bw"><div class="bf" style="width:16px"></div><div class="bv">608</div></div></div>
<div class="r"><div class="lb"><div class="l1">KPI</div><div class="l2">Figure above a level</div></div><div class="bw"><div class="bf" style="width:11px"></div><div class="bv">436</div></div></div>
<div class="r"><div class="lb"><div class="l1">Earnings</div><div class="l2">Beat the estimate</div></div><div class="bw"><div class="bf" style="width:7px"></div><div class="bv">249</div></div></div>
<div class="r"><div class="lb"><div class="l1">Valuation</div><div class="l2">Company value</div></div><div class="bw"><div class="bf" style="width:3px"></div><div class="bv">21</div></div></div>
</div>
</div>
</div>
<div class="trk">Part II: Prediction &rsaquo; <b>Polymarket data</b></div>

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
  .wrap { display: flex; flex-direction: column; gap: 12px; height: 562px; }
  .top2 { display: flex; gap: 16px; flex: none; }
  .card { flex: 1; border: 2px solid #14365d; display: flex; flex-direction: column; }
  .card .hd { background: #14365d; color: #fff; padding: 8px 20px 9px 20px; font-size: 24px; font-weight: 700; }
  .card .hd span { font-weight: 400; font-size: 19px; opacity: 0.92; margin-left: 8px; }
  .card .bd { padding: 6px 20px 8px 20px; flex: 1; display: flex; flex-direction: column; }
  .card .bd.fill .row { flex: 1; align-items: center; }
  .row { display: flex; gap: 12px; align-items: baseline; padding: 6px 0; border-bottom: 1px solid #d9dee5; }
  .row:last-child { border-bottom: none; }
  .num { font-size: 32px; font-weight: 700; color: #14365d; width: 30px; flex: none; }
  .rt { font-size: 23px; font-weight: 700; color: #14365d; }
  .rd { font-size: 18px; line-height: 1.3; margin-top: 2px; }
  .nrow { display: flex; gap: 16px; align-items: center; flex: 1; padding: 6px 0; border-bottom: 1px solid #d9dee5; }
  .nrow:last-child { border-bottom: none; }
  .big { font-size: 40px; font-weight: 700; color: #14365d; width: 112px; flex: none; text-align: right; }
  .rd2 { font-size: 20px; line-height: 1.32; margin: 2px 0 10px 0; }
  .ex2 { font-size: 19px; line-height: 1.35; margin: 4px 0; }
  .ex2 b { color: #14365d; }
  .p { font-size: 18px; line-height: 1.32; margin: 0 0 8px 0; }
  .ex { font-size: 17px; line-height: 1.3; margin: 3px 0; }
  .ex b { color: #14365d; }
  .list { flex: 1; border: 2px solid #14365d; display: flex; flex-direction: column; }
  .nm { white-space: nowrap; }
  .nm:not(:last-child)::after { content: ','; }
  .list .hd { background: #14365d; color: #fff; padding: 7px 20px 8px 20px; font-size: 22px; font-weight: 700; }
  .list .bd { padding: 8px 20px 8px 20px; font-size: 19px; line-height: 1.55; display: flex; align-items: center; flex: 1; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
---

# Companies and names

<div class="wrap">
<div class="top2">
<div class="card"><div class="hd">Which companies</div><div class="bd fill">
<div class="row"><div class="num">1</div><div><div class="rt">Publicly traded.</div><div class="rd">Every later measure needs a stock price.</div></div></div>
<div class="row"><div class="num">2</div><div><div class="rt">A ticker of 3 or more letters.</div><div class="rd">Polymarket tags each contract with a ticker, which links it to its company. Tickers of one or two letters (V, C, MS) double as ordinary words.</div></div></div>
<div class="row"><div class="num">3</div><div><div class="rt">At least one resolved Polymarket contract.</div></div></div>
</div></div>
<div class="card"><div class="hd">Which names</div><div class="bd fill">
<div class="nrow"><div class="big">4,428</div><div><div class="rt">Names</div><div class="rd2">An article can name a company through its subsidiaries, brands, products, and shows. Each one must appear in the article, and each counts as part of the company. We start from Wikidata.</div><div class="ex2"><b>Apple:</b> iPhone, AirPods, Apple TV, CarPlay.</div><div class="ex2"><b>Disney:</b> ESPN, Hulu, Pixar, Marvel Studios.</div></div></div>
</div></div>
</div>
<div class="list"><div class="hd">The 61 companies</div><div class="bd"><div><span class="nm">Adobe</span> <span class="nm">Airbnb</span> <span class="nm">Alphabet</span> <span class="nm">Amazon</span> <span class="nm">AMD</span> <span class="nm">American Express</span> <span class="nm">Apple</span> <span class="nm">Arm</span> <span class="nm">Bank of America</span> <span class="nm">BlackRock</span> <span class="nm">Broadcom</span> <span class="nm">Chevron</span> <span class="nm">Cloudflare</span> <span class="nm">Coinbase</span> <span class="nm">Costco</span> <span class="nm">CrowdStrike</span> <span class="nm">Datadog</span> <span class="nm">Dell</span> <span class="nm">Disney</span> <span class="nm">DoorDash</span> <span class="nm">Eli Lilly</span> <span class="nm">ExxonMobil</span> <span class="nm">GameStop</span> <span class="nm">HP</span> <span class="nm">IBM</span> <span class="nm">Intel</span> <span class="nm">Intuit</span> <span class="nm">JPMorgan Chase</span> <span class="nm">Lockheed Martin</span> <span class="nm">Lyft</span> <span class="nm">McDonald's</span> <span class="nm">Merck</span> <span class="nm">Meta</span> <span class="nm">Microsoft</span> <span class="nm">MicroStrategy</span> <span class="nm">Moderna</span> <span class="nm">Netflix</span> <span class="nm">Nike</span> <span class="nm">Nvidia</span> <span class="nm">Oracle</span> <span class="nm">Palantir</span> <span class="nm">Palo Alto Networks</span> <span class="nm">PayPal</span> <span class="nm">Pfizer</span> <span class="nm">Qualcomm</span> <span class="nm">Reddit</span> <span class="nm">Rivian</span> <span class="nm">Robinhood</span> <span class="nm">Roblox</span> <span class="nm">Salesforce</span> <span class="nm">Snowflake</span> <span class="nm">SpaceX</span> <span class="nm">Starbucks</span> <span class="nm">T-Mobile</span> <span class="nm">Tesla</span> <span class="nm">TSMC</span> <span class="nm">Uber</span> <span class="nm">UnitedHealth</span> <span class="nm">Walmart</span> <span class="nm">Wells Fargo</span> <span class="nm">Workday</span></div></div></div>
</div>
<div class="trk">Part I: Matching &rsaquo; <b>Companies</b></div>

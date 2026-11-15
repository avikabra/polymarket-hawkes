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
  .steps { flex: 1.25; display: flex; flex-direction: column; }
  .st { flex: 1; display: flex; gap: 16px; align-items: center; border-bottom: 1px solid #d9dee5; padding: 4px 0; }
  .st:last-child { border-bottom: none; }
  .nb { width: 44px; height: 44px; border-radius: 50%; background: #14365d; color: #fff; font-size: 24px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex: none; }
  .st .t { font-size: 24px; font-weight: 700; color: #14365d; margin-bottom: 3px; }
  .st .d { font-size: 18px; line-height: 1.32; }
  .panel { flex: 1; background: #eef3f9; border-left: 6px solid #14365d; padding: 18px 22px 18px 22px; display: flex; flex-direction: column; justify-content: space-between; }
  .panel .pt { font-size: 22px; font-weight: 700; color: #14365d; line-height: 1.25; }
  .bl { font-size: 18px; color: #3a4658; margin-bottom: 5px; }
  .bb { box-sizing: border-box; height: 62px; display: flex; align-items: center; padding-left: 16px; font-size: 30px; font-weight: 700; color: #fff; background: #7f98ba; }
  .bb.hi { background: #14365d; }
  .cn { font-size: 18px; color: #14365d; font-weight: 700; display: flex; align-items: center; gap: 10px; }
  .cn::before { content: "\2193"; font-size: 26px; }
  .panel .nt { font-size: 18px; line-height: 1.32; border-top: 1px solid #c3cfde; padding-top: 10px; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
  section { align-content: start; line-height: normal; }
  h1 { padding-bottom: 0; border-bottom: none; margin-bottom: 11px; }
  section::after { display: none; }
  section::before { content: "7"; position: absolute; font-size: 18px; color: #8a95a3; padding: 0; right: 40px; bottom: 24px; }
---

# GDELT articles

<div class="cols">
<div class="steps">
<div class="st"><div class="nb">1</div><div><div class="t">Pull the URLs</div><div class="d">GDELT is a free database of news articles. We read its daily files for each day on which one of our companies has an open contract. We keep only the web-news records.</div></div></div>
<div class="st"><div class="nb">2</div><div><div class="t">Filter on GDELT's name tags</div><div class="d">GDELT extracts the organizations and names in each article it crawls. We keep a URL when one of our company names appears in that record as a whole word with exact capitalization.</div></div></div>
<div class="st"><div class="nb">3</div><div><div class="t">Download the text</div><div class="d">GDELT stores no text. We download the full page of every kept URL from its publisher.</div></div></div>
<div class="st"><div class="nb">4</div><div><div class="t">Filter again on the text</div><div class="d">We search the page title and body for the names of the companies GDELT flagged for that URL. GDELT's tags come from its own extraction, so this step confirms each name in the text itself.</div></div></div>
</div>
<div class="panel">
<div class="pt">Counts, Sep 26, 2025 to Oct 29, 2026</div>
<div><div class="bl">Rows, one per URL and company</div><div class="bb" style="width:100%">5,004,614</div></div>
<div class="cn">Drop repeated URLs</div>
<div><div class="bl">Distinct URLs</div><div class="bb" style="width:86%">4,296,455</div></div>
<div class="cn">Download, filter on text</div>
<div><div class="bl">Articles with text</div><div class="bb hi" style="width:69%">3,446,368</div></div>
<div class="nt">GDELT dates each article to the day, so the project uses no time of day.</div>
</div>
</div>
<div class="trk">Part I: Matching &rsaquo; <b>GDELT URLs</b></div>

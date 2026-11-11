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
  .steps { flex: 1.15; display: flex; flex-direction: column; }
  .st { flex: 1; display: flex; gap: 16px; align-items: center; border-bottom: 1px solid #d9dee5; padding: 4px 0; }
  .st:last-child { border-bottom: none; }
  .nb { width: 44px; height: 44px; border-radius: 50%; background: #14365d; color: #fff; font-size: 24px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex: none; }
  .st .t { font-size: 24px; font-weight: 700; color: #14365d; margin-bottom: 3px; }
  .st .d { font-size: 19px; line-height: 1.32; }
  .rt { flex: 1; border: 2px solid #14365d; display: flex; flex-direction: column; }
  .rt .eh { background: #14365d; color: #fff; padding: 9px 20px; font-size: 22px; font-weight: 700; }
  .rt .eb { flex: 1; padding: 14px 20px 14px 20px; display: flex; flex-direction: column; justify-content: space-between; }
  .lab { font-size: 17px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #5b6573; margin-bottom: 6px; }
  .quote { font-size: 25px; line-height: 1.38; background: #eef3f9; border-left: 6px solid #14365d; padding: 12px 16px; }
  .chips { display: flex; gap: 12px; }
  .chip { font-size: 28px; font-weight: 700; padding: 12px 28px; border: 2px solid #9aa6b6; color: #5b6573; }
  .chip.on { background: #14365d; border-color: #14365d; color: #fff; }
  .arw { font-size: 23px; font-weight: 700; color: #14365d; text-align: center; }
  .cap { font-size: 17px; color: #5b6573; }
  .trk { position: absolute; left: 64px; bottom: 20px; font-size: 16px; color: #5b6573; }
  .trk b { color: #14365d; }
---

# Matching method

<div class="cols">
<div class="steps">
<div class="st"><div class="nb">1</div><div><div class="t">Start from the candidates</div><div class="d">The GDELT pull tags each article with the companies whose names it found.</div></div></div>
<div class="st"><div class="nb">2</div><div><div class="t">Ask the model</div><div class="d">Qwen3.5-4B reads the article and its candidate companies. It picks the ones that are main subjects. Our structured parsing method reads each reply into the list of picked companies.</div></div></div>
<div class="st"><div class="nb">3</div><div><div class="t">Keep the matches</div><div class="d">Every company the model picks becomes a match. Articles with the same headline on the same day count as one story for that company.</div></div></div>
<div class="st"><div class="nb">4</div><div><div class="t">Check the matches</div><div class="d">We label 500 articles before seeing the model's answers. We score precision (the share of its matches that are right) and recall (the share of true matches it finds). We scored 98% or higher on both.</div></div></div>
</div>
<div class="rt"><div class="eh">Example</div><div class="eb">
<div><div class="lab">Article</div><div class="quote">Nvidia unveils its next data-center chip, due next year. The report compares the design with Apple's laptop silicon.</div></div>
<div><div class="lab">Candidates from GDELT</div><div class="chips"><div class="chip">Nvidia</div><div class="chip">Apple</div></div></div>
<div class="arw">&darr; Qwen3.5-4B picks the main subjects</div>
<div><div class="lab">Matches</div><div class="chips"><div class="chip on">Nvidia</div></div></div>
</div></div>
</div>
<div class="trk">Part I: Matching &rsaquo; <b>Pick main subjects</b></div>

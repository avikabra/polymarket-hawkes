"""Check the company matching on hand labels, without the labeller seeing the model's answer.

    python scripts/ingest/09_hand_check.py --draw                 # sample.parquet + labels.html for the current prompt_version
    python scripts/ingest/09_hand_check.py --score labels.json    # precision and recall against the pass bar -> result.json

--draw takes 200 articles (2 x hand_check.n_per_group), seeded: 100 with at least one yes answer and 100 with
no company. The no-company group is half articles the pair filter dropped (a name hit but no pair asked) and
half articles whose asked pairs were all answered no. The yes group is stratified: each article belongs to the
stratum of its rarest yes company, and the 100 are dealt round-robin over the strata, so every company with a
yes gets a share. weight = stratum size / sample size, so weighted counts estimate all articles with a name hit.
Articles with an asked pair that has no answer yet are left out.

labels.html holds only headline, source, date and text (no model output, no stratum, no weight). Open it in a
browser, tick the companies each article is primarily about (or none), label all 200, press Export, and pass the
saved labels.json to --score.

--score refuses a labels.json that is incomplete, names an unknown company, or is for another prompt_version.
Precision = weighted share of the model's yes companies that are right; recall = weighted share of the true
companies the model found. 95% intervals: stratified bootstrap. passed = both point values >= pass_bar.
result.json is written to data/news/hand_check/<prompt_version>/.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import yaml

from src.ingest.companies import load_companies
from src.ingest.company_map import article_text

HAND = Path("data/news/hand_check")
MAP = Path("data/news/company_map")

_spec = importlib.util.spec_from_file_location("map08", Path(__file__).with_name("08_map_companies.py"))
map08 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(map08)


def write_text(text: str, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


# ── draw ────────────────────────────────────────────────────────────────────

def draw(pv: str, cfg: dict, seed: int) -> None:
    folder = HAND / pv
    if (folder / "sample.parquet").exists():
        sys.exit(f"{folder / 'sample.parquet'} exists: a drawn sample is never redrawn (labels would no longer match)")
    ans = map08.read_answers(MAP / pv)
    pairs = pd.read_parquet(MAP / pv / "hits.parquet")  # written by 08 --scan
    pairs = pairs.merge(ans[["article_id", "company_id", "answer"]], on=["article_id", "company_id"], how="left")
    asked = pairs[pairs["asked"]]
    unanswered = set(asked.loc[asked["answer"].isna(), "article_id"])
    yes = asked[asked["answer"] == "yes"].groupby("article_id")["company_id"].apply(list)
    n_asked = asked.groupby("article_id").size()
    pop = pd.DataFrame({"article_id": pairs["article_id"].unique()})
    pop = pop[~pop["article_id"].isin(unanswered)]
    pop["companies"] = pop["article_id"].map(yes).map(lambda x: x if isinstance(x, list) else [])
    pop["asked"] = pop["article_id"].map(n_asked).fillna(0)
    freq = pd.Series([c for cs in pop["companies"] for c in cs]).value_counts()
    pop["stratum"] = [("co:" + min(cs, key=lambda c: (freq[c], c))) if cs else ("none:no" if n else "none:dropped")
                      for cs, n in zip(pop["companies"], pop["asked"])]
    n = cfg["n_per_group"]
    rng = np.random.default_rng(seed)

    has = pop[pop["companies"].map(len) > 0]
    drop, no = pop[pop["stratum"] == "none:dropped"], pop[pop["stratum"] == "none:no"]
    need = {"yes": (has, n), "dropped by the filter": (drop, n // 2), "answered no": (no, n - n // 2)}
    for k, (g, m) in need.items():
        if len(g) < m:
            sys.exit(f"need {m} articles that are {k}; have {len(g)}")

    pools = {s: list(rng.permutation(g.index.to_numpy())) for s, g in has.groupby("stratum")}
    order = list(rng.permutation(sorted(pools)))
    picked = []
    while len(picked) < n:  # round-robin over the company strata
        for s in order:
            if pools[s] and len(picked) < n:
                picked.append(pools[s].pop())
    sample = pd.concat([pop.loc[picked]] + [g.loc[rng.choice(g.index.to_numpy(), m, replace=False)]
                                            for g, m in (need["dropped by the filter"], need["answered no"])])
    sample["stratum_size"] = sample["stratum"].map(pop["stratum"].value_counts())
    sample["sample_size"] = sample["stratum"].map(sample["stratum"].value_counts())
    sample["weight"] = sample["stratum_size"] / sample["sample_size"]
    kept = map08.load_kept(["headline", "lede", "source", "day"], set(sample["article_id"]))
    sample = sample.merge(kept[["article_id", "headline", "lede", "body", "source", "day"]], on="article_id")
    sample = sample.sample(frac=1, random_state=seed).reset_index(drop=True)  # shown in random order
    sample["prompt_version"] = pv
    sample["text"] = [article_text(l, b) for l, b in zip(sample["lede"], sample["body"])]

    folder.mkdir(parents=True, exist_ok=True)
    keep = ["article_id", "stratum", "stratum_size", "sample_size", "weight", "companies",
            "headline", "source", "day", "text", "prompt_version"]
    sample[keep].to_parquet(folder / "sample.parquet", index=False)
    write_text(labels_html(sample, pv), folder / "labels.html")
    print(f"{len(sample)} articles ({sum(s.startswith('co:') for s in sample['stratum'].unique())} company strata, "
          f"{n // 2} dropped by the filter, {n - n // 2} answered no), weights sum {sample['weight'].sum():.0f} "
          f"of {len(pop)} articles with a name hit -> {folder}/sample.parquet, labels.html")


def labels_html(sample: pd.DataFrame, pv: str) -> str:
    """Self-contained labelling page. Built only from the blind columns below, so no model output can reach it."""
    blind = sample[["article_id", "headline", "source", "day", "text"]]
    data = {
        "prompt_version": pv,
        "companies": [{"id": c.id, "name": c.name} for c in load_companies()],
        "articles": [{k: ("" if v is None else str(v)) for k, v in r.items()} for r in blind.to_dict("records")],
    }
    blob = json.dumps(data).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return HTML.replace("__DATA__", blob)


HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Company labels</title>
<style>
body{font:15px/1.5 system-ui,sans-serif;margin:0;color:#111;background:#fff}
header{position:sticky;top:0;background:#f3f3f3;border-bottom:1px solid #ccc;padding:8px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
main{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:16px;padding:16px}
@media(max-width:800px){main{grid-template-columns:1fr}}
h1{font-size:20px;margin:0 0 4px}.meta{color:#555;margin-bottom:12px}
.text{white-space:pre-wrap;max-height:75vh;overflow:auto;border:1px solid #ddd;padding:12px}
.boxes{columns:2;font-size:14px}.boxes label{display:block;break-inside:avoid;padding:1px 0}
button{padding:5px 12px;font:inherit;cursor:pointer}
.none{font-weight:600;margin-bottom:8px;display:block}
</style></head><body>
<header>
<button id="prev">Prev</button><button id="next">Next</button>
<span id="pos"></span><strong id="done"></strong>
<button id="export">Export labels.json</button>
<button id="skipundone">Next unlabelled</button>
</header>
<main>
<section><h1 id="headline"></h1><div class="meta" id="meta"></div><div class="text" id="text"></div></section>
<section><label class="none"><input type="checkbox" id="none"> None of the companies</label><div class="boxes" id="boxes"></div></section>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById("data").textContent);
const KEY = "handcheck-" + D.prompt_version;
let state = {}, i = 0;  // state[article_id] = {none: bool, companies: [ids]}
try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
const isDone = a => { const s = state[a.article_id]; return !!s && (s.none || s.companies.length > 0); };
const boxes = document.getElementById("boxes"), none = document.getElementById("none");
D.companies.forEach(c => {
  const l = document.createElement("label"), b = document.createElement("input");
  b.type = "checkbox"; b.value = c.id; b.className = "co";
  b.onchange = () => { const s = cur(); s.companies = [...document.querySelectorAll(".co:checked")].map(x => x.value);
    if (s.companies.length) s.none = false; save(); show(); };
  l.append(b, " " + c.name + " (" + c.id + ")"); boxes.append(l);
});
none.onchange = () => { const s = cur(); s.none = none.checked; if (s.none) s.companies = []; save(); show(); };
function cur() { const id = D.articles[i].article_id; return state[id] = state[id] || {none: false, companies: []}; }
function show() {
  const a = D.articles[i], s = state[a.article_id] || {none: false, companies: []};
  document.getElementById("headline").textContent = a.headline;
  document.getElementById("meta").textContent = a.source + " | " + a.day;
  document.getElementById("text").textContent = a.text;
  none.checked = s.none;
  document.querySelectorAll(".co").forEach(b => b.checked = s.companies.includes(b.value));
  document.getElementById("pos").textContent = "Article " + (i + 1) + " / " + D.articles.length;
  document.getElementById("done").textContent = D.articles.filter(isDone).length + " done";
}
const go = d => { i = Math.min(D.articles.length - 1, Math.max(0, i + d)); show(); document.getElementById("text").scrollTop = 0; };
document.getElementById("prev").onclick = () => go(-1);
document.getElementById("next").onclick = () => go(1);
document.getElementById("skipundone").onclick = () => {
  const k = D.articles.findIndex((a, j) => j > i && !isDone(a)); const t = k >= 0 ? k : D.articles.findIndex(a => !isDone(a));
  if (t >= 0) { i = t; show(); }
};
document.getElementById("export").onclick = () => {
  const labels = {};
  D.articles.filter(isDone).forEach(a => labels[a.article_id] = state[a.article_id].companies);
  const n = Object.keys(labels).length;
  if (n < D.articles.length && !confirm(n + " of " + D.articles.length + " labelled. Export anyway? Scoring needs all.")) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify({prompt_version: D.prompt_version, labels}, null, 1)], {type: "application/json"}));
  const a = document.createElement("a"); a.href = url; a.download = "labels.json"; a.click(); URL.revokeObjectURL(url);
};
show();
</script></body></html>
"""


# ── score ───────────────────────────────────────────────────────────────────

def ratios(tp, m, t, w):
    """Weighted precision and recall; nan when the denominator is 0."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return (w * tp).sum(-1) / (w * m).sum(-1), (w * tp).sum(-1) / (w * t).sum(-1)


def bootstrap(tp, m, t, w, strata, reps, seed):
    """Stratified bootstrap: resample articles within each stratum; -> (precision draws, recall draws)."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((3, reps))
    for s in np.unique(strata):
        idx = np.flatnonzero(strata == s)
        draw = idx[rng.integers(0, len(idx), (reps, len(idx)))]
        for k, v in enumerate((tp, m, t)):
            acc[k] += (w[draw] * v[draw]).sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return acc[0] / acc[1], acc[0] / acc[2]


def ci(x):
    x = x[~np.isnan(x)]
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) else [float("nan")] * 2


def score(path: str, pv: str, cfg: dict, seed: int) -> None:
    sp = HAND / pv / "sample.parquet"
    if not sp.exists():
        sys.exit(f"{sp} missing: run --draw first")
    sample = pd.read_parquet(sp)
    try:
        lab = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        sys.exit(f"cannot read {path}: {e}")
    if lab.get("prompt_version") != pv:
        sys.exit(f"{path} is for prompt_version {lab.get('prompt_version')!r}, current is {pv!r}")
    labels = lab.get("labels")
    if not isinstance(labels, dict):
        sys.exit(f"{path} has no 'labels' object")
    missing = set(sample["article_id"]) - set(labels)
    extra = set(labels) - set(sample["article_id"])
    if missing or extra:
        sys.exit(f"{path} is incomplete or for another sample: {len(missing)} articles unlabelled, {len(extra)} unknown")
    valid = {c.id for c in load_companies()}
    for a, ids in labels.items():
        if not isinstance(ids, list) or not set(ids) <= valid or len(set(ids)) != len(ids):
            sys.exit(f"bad label for {a}: {ids!r}")

    truth = [set(labels[a]) for a in sample["article_id"]]
    model = [set(c) for c in sample["companies"]]
    tp = np.array([len(a & b) for a, b in zip(model, truth)], float)
    m = np.array([len(a) for a in model], float)
    t = np.array([len(b) for b in truth], float)
    w = sample["weight"].to_numpy(float)
    strata_arr = sample["stratum"].to_numpy()
    prec, rec = (float(x) for x in ratios(tp, m, t, w))
    bp, br = bootstrap(tp, m, t, w, strata_arr, cfg["bootstrap_reps"], seed)
    p_ci, r_ci = ci(bp), ci(br)
    uprec, urec = tp.sum() / m.sum() if m.sum() else float("nan"), tp.sum() / t.sum() if t.sum() else float("nan")
    bar = cfg["pass_bar"]
    passed = bool(prec >= bar and rec >= bar)

    print(f"prompt_version {pv}; {len(sample)} articles; pass bar {bar:.0%}")
    print(f"precision {prec:.4f}  95% CI [{p_ci[0]:.4f}, {p_ci[1]:.4f}]  (unweighted {uprec:.4f}; {int(m.sum())} model labels)")
    print(f"recall    {rec:.4f}  95% CI [{r_ci[0]:.4f}, {r_ci[1]:.4f}]  (unweighted {urec:.4f}; {int(t.sum())} true labels)")
    strata = sample.drop_duplicates("stratum")
    none_pop = strata.loc[strata["stratum"].str.startswith("none"), "stratum_size"].sum() / strata["stratum_size"].sum()
    print(f"none-share: sample {np.mean(m == 0):.1%} of articles by model, {np.mean(t == 0):.1%} by hand; "
          f"mapped population (model) {none_pop:.1%}")
    print("PASSED" if passed else "FAILED")

    names = {c.id: c.name for c in load_companies()}
    rows = []
    for c in sorted(valid):
        tpc = sum(c in a and c in b for a, b in zip(model, truth))
        fp = sum(c in a and c not in b for a, b in zip(model, truth))
        fn = sum(c not in a and c in b for a, b in zip(model, truth))
        if tpc + fp + fn:
            rows.append((c, names[c], tpc, fp, fn))
    print(f"\nper company (raw counts in the sample):\n{'id':<20}{'name':<24}{'TP':>4}{'FP':>4}{'FN':>4}")
    for r in sorted(rows, key=lambda r: -(r[3] + r[4])):
        print(f"{r[0]:<20}{r[1][:23]:<24}{r[2]:>4}{r[3]:>4}{r[4]:>4}")

    bad = [i for i in range(len(sample)) if model[i] != truth[i]]
    print(f"\n{len(bad)} disagreements:")
    for i in bad:
        print(f"  {sample['article_id'].iloc[i][:12]}  {sample['headline'].iloc[i]!r}\n"
              f"      model {sorted(model[i])}  hand {sorted(truth[i])}  "
              f"false+ {sorted(model[i] - truth[i])}  false- {sorted(truth[i] - model[i])}")

    result = {"prompt_version": pv, "passed": passed, "pass_bar": bar, "n_articles": len(sample),
              "precision": prec, "precision_ci95": p_ci, "recall": rec, "recall_ci95": r_ci,
              "precision_unweighted": float(uprec), "recall_unweighted": float(urec),
              "n_model_labels": int(m.sum()), "n_true_labels": int(t.sum()), "n_disagreements": len(bad),
              "labels_file": str(path)}
    text = json.dumps(result, indent=1) + "\n"
    write_text(text, HAND / pv / "result.json")
    print(f"\nresult -> {HAND / pv / 'result.json'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--draw", action="store_true")
    g.add_argument("--score", metavar="labels.json")
    args = ap.parse_args()
    full = yaml.safe_load(open("config/ingest.yaml"))
    pv, cfg = str(full["llm_map"]["prompt_version"]), full["hand_check"]
    if args.draw:
        draw(pv, cfg, cfg["seed"])
    else:
        score(args.score, pv, cfg, cfg["seed"])


if __name__ == "__main__":
    main()

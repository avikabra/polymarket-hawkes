"""Tune the matching instructions on a labelled sample (step 26), before any long run.

    python scripts/ingest/08_tune.py --draw                # CPU: 400 random articles from questions.parquet -> tune/sample400.parquet
    python scripts/ingest/08_tune.py --run                 # GPU: answer the sample with every variant in tune/variants/*.txt not yet run
    python scripts/ingest/08_tune.py --score labels.jsonl  # CPU: precision and recall of each variant, per half (dev, holdout)

A variant is a system prompt (a .txt file, answered as a list as in company_map), or a .json file
{"system": ..., "format": "list" | "verdict" | "verdict3" | "reason"}: "verdict" asks for one verdict per named company ("about" or
"passing"); "reason" asks for a short reason, then the verdict, per company.
The sample's halves alternate by article_id: variants are compared on dev, and only the chosen one is scored on holdout.
Precision = share of the model's (article, company) matches that the labels hold; recall = share of labelled matches
the model found.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import pyarrow.parquet as pq
import yaml

from src.ingest.companies import load_companies
from src.ingest.company_map import fit_message, parse_answer, schema

TUNE = Path("data/news/company_map/tune")
LEVELS3 = ("main subject", "one of the subjects", "passing")  # verdict3: either of the first two counts
VERDICT_Q = "For each listed company: is this article about it, or is it a passing mention?"


def reason_schema(names: list[str]) -> dict:
    """Per company: a short reason first, then the verdict."""
    one = {"type": "object", "properties": {"reason": {"type": "string"}, "verdict": {"type": "string", "enum": ["about", "passing"]}},
           "required": ["reason", "verdict"], "additionalProperties": False}
    return {"type": "object", "properties": {n: one for n in names}, "required": names, "additionalProperties": False}


OTHER = ("another company or organisation", "a person, place, product or topic")


def primary_schema(names: list[str]) -> dict:
    """The article's main subject first (a listed company, or something not listed), then any other listed main subjects."""
    return {"type": "object", "properties": {"main_subject": {"type": "string", "enum": names + list(OTHER)},
                                             "also_main_subjects": {"type": "array", "items": {"type": "string", "enum": names}}},
            "required": ["main_subject", "also_main_subjects"], "additionalProperties": False}


def verdict_schema(names: list[str], levels=("about", "passing")) -> dict:
    return {"type": "object", "properties": {n: {"type": "string", "enum": list(levels)} for n in names},
            "required": names, "additionalProperties": False}
QUESTIONS = Path("data/news/company_map/v5/questions.parquet")


def draw(name: str, n: int = 400, seed: int = 7) -> None:
    f = pq.ParquetFile(QUESTIONS)
    ids = pd.read_parquet(QUESTIONS, columns=["article_id"])["article_id"]
    used = [pd.read_parquet(p, columns=["article_id"])["article_id"] for p in TUNE.glob("sample*.parquet")]
    ids = ids[~ids.isin(pd.concat(used))] if used else ids  # a fresh sample never reuses a tuned article
    ids = ids.sample(n, random_state=seed)
    keep = set(ids)
    q = pd.concat([b.to_pandas()[lambda d: d["article_id"].isin(keep)] for b in f.iter_batches(batch_size=50000)])
    q = q.sort_values("article_id").reset_index(drop=True)
    q["half"] = ["dev" if i % 2 == 0 else "holdout" for i in range(len(q))]
    TUNE.mkdir(parents=True, exist_ok=True)
    q.to_parquet(TUNE / f"{name}.parquet", index=False)
    q[["article_id", "half", "hits", "headline", "text"]].to_json(TUNE / f"{name}.jsonl", orient="records", lines=True)
    print(f"{len(q)} articles -> {TUNE}")


def run(names: list[str], only: list[str] | None = None, model: str | None = None) -> None:
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    cfg = yaml.safe_load(open("config/ingest.yaml"))["llm_map"]
    model = model or cfg["model"]
    tag = "" if model == cfg["model"] else "@" + model.split("/")[-1]  # answers of another model get its name
    companies = load_companies()
    tok = AutoTokenizer.from_pretrained(model)
    llm = LLM(model=model, enable_prefix_caching=True, seed=cfg["seed"],
              max_model_len=2048 + cfg["max_input_tokens"] + cfg["max_output_tokens"])
    for name in names:
        run_sample(name, only, cfg, companies, tok, llm, tag)


def run_sample(name, only, cfg, companies, tok, llm, tag) -> None:
    from vllm import SamplingParams
    from vllm.sampling_params import StructuredOutputsParams

    q = pd.read_parquet(TUNE / f"{name}.parquet")
    ans_dir = TUNE / ("answers" if name == "sample400" else f"answers_{name}")
    todo = [p for p in sorted((TUNE / "variants").glob("*.*")) if not (ans_dir / f"{p.stem}{tag}.parquet").exists()
            and (not only or p.stem in only)]
    if not todo:
        print(name, "nothing to do")
        return
    msgs, offered = [], []
    for r in q.to_dict("records"):
        hits = json.loads(r["hits"])
        msgs.append(fit_message(hits, r["headline"], r["text"], tok, cfg["max_input_tokens"])[0])
        offered.append([h[0] for h in hits])
    def sp(js, mt=cfg["max_output_tokens"]):
        return SamplingParams(temperature=cfg["temperature"], seed=cfg["seed"], max_tokens=mt,
                              structured_outputs=StructuredOutputsParams(json=js))
    by_format = {"list": [sp(schema(n)) for n in offered], "verdict": [sp(verdict_schema(n)) for n in offered],
                 "reason": [sp(reason_schema(n), 64 + 64 * len(n)) for n in offered],
                 "verdict3": [sp(verdict_schema(n, LEVELS3)) for n in offered],
                 "primary": [sp(primary_schema(n)) for n in offered]}
    ans_dir.mkdir(exist_ok=True)
    by_name = {c.name: c.id for c in companies}
    for p in todo:
        v = json.loads(p.read_text()) if p.suffix == ".json" else {"system": p.read_text().strip(), "format": "list"}
        q_end = v.get("question", VERDICT_Q)
        user = msgs if v["format"] == "list" else [m.rsplit("\n\n", 1)[0] + "\n\n" + q_end for m in msgs]
        res = llm.chat([[{"role": "system", "content": v["system"]}, {"role": "user", "content": m}] for m in user],
                       by_format[v["format"]], chat_template_kwargs={"enable_thinking": False}, use_tqdm=False)
        rows = []
        for a, o, n in zip(q["article_id"], res, offered):
            try:
                if v["format"] == "list":
                    ans = parse_answer(o.outputs[0].text, companies, set(n))
                elif v["format"] == "primary":
                    out = json.loads(o.outputs[0].text)
                    ans = sorted({by_name[c] for c in [out["main_subject"], *out["also_main_subjects"]] if c in n})
                else:
                    out = json.loads(o.outputs[0].text)
                    out = {c: (x["verdict"] if isinstance(x, dict) else x) for c, x in out.items()}
                    ans = sorted({by_name[c] for c, x in out.items() if x in ("about", *LEVELS3[:2]) and c in n})
                err = None
            except (ValueError, KeyError) as e:
                ans, err = [], str(e)[:200]
            rows.append({"article_id": a, "companies": ans, "error": err, "raw": o.outputs[0].text})
        pd.DataFrame(rows).to_parquet(ans_dir / f"{p.stem}{tag}.parquet", index=False)
        print(name, p.stem + tag, "matched share", round(sum(bool(r["companies"]) for r in rows) / len(rows), 3), flush=True)


def score(labels: Path) -> None:
    lab = pd.read_json(labels, lines=True)[["article_id", "companies"]].rename(columns={"companies": "truth"})
    q = pd.read_parquet(TUNE / "sample400.parquet", columns=["article_id", "half"]).merge(lab, on="article_id")
    out = []
    for p in sorted((TUNE / "answers").glob("*.parquet")):
        m = q.merge(pd.read_parquet(p), on="article_id")
        for half, g in m.groupby("half"):
            pred = [(a, c) for a, cs in zip(g["article_id"], g["companies"]) for c in cs]
            true = {(a, c) for a, cs in zip(g["article_id"], g["truth"]) for c in cs}
            tp = sum(x in true for x in pred)
            out.append({"variant": p.stem, "half": half, "n": len(g), "pred": len(pred), "true": len(true), "tp": tp,
                        "precision": round(tp / len(pred), 3) if pred else None,
                        "recall": round(tp / len(true), 3) if true else None})
    print(pd.DataFrame(out).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draw", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--score", type=Path)
    ap.add_argument("--sample", nargs="+", default=["sample400"], help="sample names under tune/ (--draw: a new name draws a fresh sample)")
    ap.add_argument("--model", default=None, help="model to run instead of llm_map.model")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--variants", nargs="*", help="run only these variant stems")
    a = ap.parse_args()
    draw(a.sample[0], seed=a.seed) if a.draw else run(a.sample, a.variants, a.model) if a.run else score(a.score)


if __name__ == "__main__":
    main()

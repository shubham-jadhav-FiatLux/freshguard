"""FreshGuard benchmark: runs the real pipeline (via Bifrost + Tavily) on labelled claims.

Usage:
  FG_NEWS_DAYS=365 .venv/bin/python -m eval.run_eval news_365     # default: news (365d) + web
  FG_NEWS_DAYS=30  .venv/bin/python -m eval.run_eval news_30      # ablation: 30-day news window
  FG_NEWS_DAYS=0   .venv/bin/python -m eval.run_eval web_only     # ablation: general web search only
  .venv/bin/python -m eval.run_eval --report                     # metrics table for all runs

Each answer is a single claim. Prediction = label of the lowest-scoring extracted claim
(stale / current / uncertain), or "skipped" if no time-sensitive claim was extracted.
Results are appended to eval/results/<run>.jsonl so an interrupted run resumes where it stopped.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).parent
CLAIMS = [json.loads(line) for line in (HERE / "claims.jsonl").read_text().splitlines() if line.strip()]
RESULTS = HERE / "results"
PAUSE_S = 6          # pacing between items (Groq free tier: ~8k tokens/min on the judge model)
MAX_TRIES = 6


def predict(report: dict) -> tuple[str, dict | None]:
    claims = report.get("claims") or []
    if not claims:
        return "skipped", None
    worst = min(claims, key=lambda c: c["freshness_score"])
    return {"stale": "stale", "fresh": "current"}.get(worst["label"], "uncertain"), worst


def correct(label: str, pred: str) -> bool:
    if label == "timeless":
        return pred in ("skipped", "current")
    return label == pred


async def run(name: str) -> None:
    from freshguard import pipeline  # imported here so FG_* env vars apply
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{name}.jsonl"
    done = {json.loads(l)["id"] for l in out.read_text().splitlines()} if out.exists() else set()
    print(f"[{name}] news_days={pipeline.NEWS_DAYS} model={pipeline.FG_MODEL} fallback={pipeline.FG_FALLBACK_MODEL} "
          f"done={len(done)}/{len(CLAIMS)}", flush=True)
    async with httpx.AsyncClient() as client:
        for item in CLAIMS:
            if item["id"] in done:
                continue
            for attempt in range(1, MAX_TRIES + 1):
                t0 = time.time()
                try:
                    rep = await pipeline.check_answer(item["text"], client)
                    break
                except Exception as e:  # mostly 429 rate limits from the free LLM tier
                    wait = 20 * attempt
                    print(f"  ! {item['id']} attempt {attempt}: {str(e)[:120]} -> retry in {wait}s", flush=True)
                    await asyncio.sleep(wait)
            else:
                print(f"  x {item['id']} failed after {MAX_TRIES} tries", flush=True)
                continue
            pred, worst = predict(rep)
            row = {"id": item["id"], "group": item["group"], "label": item["label"], "pred": pred,
                   "correct": correct(item["label"], pred), "score": worst["freshness_score"] if worst else None,
                   "current_fact": worst.get("current_fact") if worst else None,
                   "sources": [s.get("url") for s in (worst or {}).get("sources", [])],
                   "seconds": round(time.time() - t0, 1), "tokens": rep.get("llm_usage", {}).get("total_tokens", 0)}
            with out.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"  {'✓' if row['correct'] else '✗'} {item['id']:<20} label={item['label']:<8} pred={pred:<9} "
                  f"score={row['score']} {row['seconds']}s", flush=True)
            await asyncio.sleep(PAUSE_S)


def metrics(rows: list[dict]) -> dict:
    def pct(a, b):
        return round(100 * a / b, 1) if b else None
    stale = [r for r in rows if r["label"] == "stale"]
    cur = [r for r in rows if r["label"] == "current"]
    recent = [r for r in rows if r["group"] == "recent_change"]
    recent_stale = [r for r in recent if r["label"] == "stale"]
    flagged = [r for r in rows if r["pred"] == "stale"]
    return {
        "n": len(rows),
        "accuracy": pct(sum(r["correct"] for r in rows), len(rows)),
        "stale_recall": pct(sum(r["pred"] == "stale" for r in stale), len(stale)),
        "stale_precision": pct(sum(r["label"] == "stale" for r in flagged), len(flagged)),
        "recent_change_recall": pct(sum(r["pred"] == "stale" for r in recent_stale), len(recent_stale)),
        "recent_change_accuracy": pct(sum(r["correct"] for r in recent), len(recent)),
        "current_confirmed": pct(sum(r["pred"] == "current" for r in cur), len(cur)),
        "false_alarm_rate": pct(sum(r["pred"] == "stale" for r in cur), len(cur)),
        "uncertain": sum(r["pred"] == "uncertain" for r in rows),
        "avg_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 1) if rows else None,
        "avg_tokens": round(sum(r["tokens"] for r in rows) / len(rows)) if rows else None,
    }


def report() -> None:
    runs = {p.stem: [json.loads(l) for l in p.read_text().splitlines()] for p in sorted(RESULTS.glob("*.jsonl"))}
    table = {name: metrics(rows) for name, rows in runs.items()}
    (RESULTS / "summary.json").write_text(json.dumps(table, indent=2))
    keys = list(next(iter(table.values())).keys())
    print("| metric | " + " | ".join(table) + " |\n|---|" + "---|" * len(table))
    for k in keys:
        print(f"| {k} | " + " | ".join(str(table[n][k]) for n in table) + " |")
    for name, rows in runs.items():
        wrong = [f"{r['id']}({r['label']}→{r['pred']})" for r in rows if not r["correct"]]
        print(f"\n{name} errors: {', '.join(wrong) or 'none'}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--report"]:
        report()
    else:
        asyncio.run(run(sys.argv[1]))

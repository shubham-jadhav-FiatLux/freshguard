"""FreshGuard core pipeline: extract time-sensitive claims -> verify live with Tavily -> score freshness.

All LLM calls go through the Bifrost gateway (OpenAI-compatible endpoint).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import date

import httpx
from dotenv import load_dotenv

load_dotenv()

BIFROST_URL = os.getenv("BIFROST_URL", "http://localhost:8080")
FG_MODEL = os.getenv("FG_MODEL", "groq/openai/gpt-oss-120b")          # judge / extractor
FG_ANSWER_MODEL = os.getenv("FG_ANSWER_MODEL", FG_MODEL)                    # model used for demo answers
FG_FALLBACK_MODEL = os.getenv("FG_FALLBACK_MODEL", "")                      # optional Bifrost fallback
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"
MAX_CLAIMS = int(os.getenv("FG_MAX_CLAIMS", "6"))
NEWS_DAYS = int(os.getenv("FG_NEWS_DAYS", "365"))      # recency window for the news search (0 = web only)
MAX_EVIDENCE = int(os.getenv("FG_MAX_EVIDENCE", "8"))
NEWS_CATEGORIES = {"leadership", "pricing", "company", "regulation", "event", "version"}

CATEGORIES = ["pricing", "version", "regulation", "leadership", "company", "statistic", "event", "other"]

EXTRACT_PROMPT = """You audit AI-generated answers for information that may have gone out of date.
Today's date is {today}.

From the ANSWER below, extract up to {n} atomic factual claims that are TIME-SENSITIVE, i.e. could
change over time (prices, plans, API/software versions, laws/regulations, who holds a role, company
facts, statistics, "latest"/"current"/"newest" statements, release dates). Skip timeless facts and opinions.

Return ONLY JSON: {{"claims": [{{"claim": "<self-contained statement, resolve pronouns>",
"category": one of {cats}, "volatility": "high"|"medium"|"low",
"search_query": "<web search query that would verify it today>",
"news_query": "<short news query that would surface a recent CHANGE to this fact, e.g. 'X CEO steps down'>"}}]}}

ANSWER:
\"\"\"{answer}\"\"\""""

JUDGE_PROMPT = """You are a fact-freshness judge. Today's date is {today}.
Decide whether the CLAIM is still accurate *today*, using ONLY the EVIDENCE (live web results).
Evidence items marked [NEWS] come from a news search limited to the last {news_days} days; others are general
web pages (profiles, docs, wikis) that are often months or years out of date.
Rules:
- A credible, recent NEWS report that the fact CHANGED (resigned, replaced, discontinued, repriced, new version
  released, law amended...) overrides older pages that still state the old fact -> "outdated".
- If several recent outlets agree on a change, be confident even if profile pages disagree.
- Prefer primary sources (the company's or project's own site, release notes, official government pages) and
  dated news from major outlets over third-party trackers, aggregators and SEO pages, which often lag behind.
- Numbers that differ only by rounding or formatting ($19.99 vs "$20", 3.15 vs 3.15.0) are the SAME fact;
  only call a number outdated if the evidence explicitly gives a different current value or reports a change.
- Never call something "the latest" unless the evidence is recent. Mention the evidence date in current_fact.
- If evidence is missing or ambiguous, say "unverified".

CLAIM: {claim}

EVIDENCE:
{evidence}

Return ONLY JSON: {{"verdict": "current"|"outdated"|"unverified",
"confidence": <0.0-1.0>,
"current_fact": "<what is true now according to evidence, or empty>",
"reason": "<one short sentence>",
"source_ids": [<ids of evidence items you relied on>]}}"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"No JSON in model output: {text[:200]}")
    return json.loads(m.group(0))


async def chat(client: httpx.AsyncClient, messages: list[dict], model: str | None = None,
               json_mode: bool = False, temperature: float = 0.0) -> tuple[str, dict]:
    """Call an LLM through Bifrost. Returns (content, usage)."""
    body: dict = {"model": model or FG_MODEL, "messages": messages, "temperature": temperature}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if FG_FALLBACK_MODEL:  # Bifrost retries on this model if the primary provider fails / rate-limits
        body["fallbacks"] = [FG_FALLBACK_MODEL]
    # Empty include-clients header: FreshGuard's own calls must not get Bifrost's MCP tools injected
    # (that would recurse into verify_freshness and clash with JSON mode).
    r = await client.post(f"{BIFROST_URL}/v1/chat/completions", json=body, timeout=90,
                          headers={"x-bf-mcp-include-clients": "", "x-freshguard-skip": "1"})
    r.raise_for_status()
    data = r.json()
    usage = dict(data.get("usage") or {})
    usage["_model"] = data.get("model", "")  # which model actually answered (Bifrost may have used the fallback)
    return data["choices"][0]["message"]["content"] or "", usage


async def tavily_search(client: httpx.AsyncClient, query: str, news_days: int | None = None) -> list[dict]:
    """General web search, or (news_days set) a news search restricted to the last N days."""
    body = {"query": query, "search_depth": "advanced", "max_results": 5, "include_answer": False}
    if news_days:
        body |= {"topic": "news", "days": news_days}
    r = await client.post(TAVILY_URL, headers={"Authorization": f"Bearer {TAVILY_API_KEY}"}, json=body, timeout=60)
    r.raise_for_status()
    results = r.json().get("results", [])
    for x in results:
        x["_news"] = bool(news_days)
    return results


async def gather_evidence(client: httpx.AsyncClient, claim: dict, query: str) -> list[dict]:
    """Hybrid retrieval: recent news (catches changes from the last days) + general web (stable reference pages).
    General pages alone miss fresh changes, e.g. a CEO who resigned 3 days ago is still listed on profile pages."""
    searches = [tavily_search(client, query)]
    if NEWS_DAYS > 0 and (claim.get("volatility") in ("high", "medium") or claim.get("category") in NEWS_CATEGORIES):
        searches.insert(0, tavily_search(client, claim.get("news_query") or claim["claim"], news_days=NEWS_DAYS))
    merged, seen = [], set()
    for res in await asyncio.gather(*searches, return_exceptions=True):
        if isinstance(res, Exception):
            claim.setdefault("search_errors", []).append(str(res))
            continue
        for r in res:
            if r.get("url") not in seen:
                seen.add(r.get("url"))
                merged.append(r)
    return merged[:MAX_EVIDENCE]


def freshness_score(verdict: str, confidence: float, volatility: str) -> int:
    """0 = definitely stale, 100 = verified current. Unverified claims are penalised by volatility."""
    c = max(0.0, min(1.0, float(confidence or 0)))
    if verdict == "current":
        return round(60 + 40 * c)
    if verdict == "outdated":
        return round(30 * (1 - c))
    base = {"high": 35, "medium": 45, "low": 55}.get(volatility, 45)
    return base


def label(score: int) -> str:
    return "fresh" if score >= 70 else ("stale" if score < 35 else "uncertain")


async def extract_claims(client: httpx.AsyncClient, answer: str) -> tuple[list[dict], dict]:
    prompt = EXTRACT_PROMPT.format(today=date.today().isoformat(), n=MAX_CLAIMS,
                                   cats="|".join(CATEGORIES), answer=answer)
    content, usage = await chat(client, [{"role": "user", "content": prompt}], json_mode=True)
    claims = _parse_json(content).get("claims", [])[:MAX_CLAIMS]
    return [c for c in claims if c.get("claim")], usage


async def verify_claim(client: httpx.AsyncClient, claim: dict) -> dict:
    query = claim.get("search_query") or claim["claim"]
    year = str(date.today().year)
    if claim.get("volatility") == "high" and year not in query:  # bias fast-moving facts to recent pages
        query = f"{query} {year}"
    results = await gather_evidence(client, claim, query)
    evidence = "\n\n".join(
        f"[{i}]{' [NEWS]' if r.get('_news') else ''} {r.get('title', '')} ({r.get('url', '')})"
        + (f" published {r['published_date']}" if r.get("published_date") else "")
        + f"\n{(r.get('content') or '')[:700]}"
        for i, r in enumerate(results)
    ) or "(no results)"
    judged, usage = {"verdict": "unverified", "confidence": 0, "reason": "No evidence found."}, {}
    if results:
        content, usage = await chat(client, [{"role": "user", "content": JUDGE_PROMPT.format(
            today=date.today().isoformat(), news_days=NEWS_DAYS, claim=claim["claim"], evidence=evidence)}],
            json_mode=True)
        judged = _parse_json(content)
    verdict = judged.get("verdict", "unverified")
    if verdict not in ("current", "outdated", "unverified"):
        verdict = "unverified"
    score = freshness_score(verdict, judged.get("confidence", 0), claim.get("volatility", "medium"))
    ids = [i for i in judged.get("source_ids", []) if isinstance(i, int) and 0 <= i < len(results)]
    sources = [{"title": results[i].get("title"), "url": results[i].get("url"),
                "published_date": results[i].get("published_date"), "news": results[i].get("_news", False)} for i in (ids or range(min(2, len(results))))]
    return {**claim, "verdict": verdict, "confidence": judged.get("confidence", 0),
            "current_fact": judged.get("current_fact", ""), "reason": judged.get("reason", ""),
            "freshness_score": score, "label": label(score), "sources": sources, "_usage": usage}


def _add_usage(total: dict, u: dict) -> None:
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        total[k] = total.get(k, 0) + int(u.get(k, 0) or 0)
    if u.get("_model"):
        models = total.setdefault("models", {})
        models[u["_model"]] = models.get(u["_model"], 0) + 1


async def check_answer(answer: str, client: httpx.AsyncClient | None = None) -> dict:
    """Full FreshGuard report for an LLM answer."""
    own = client is None
    client = client or httpx.AsyncClient()
    try:
        usage: dict = {}
        claims, u = await extract_claims(client, answer)
        _add_usage(usage, u)
        verified = await asyncio.gather(*(verify_claim(client, c) for c in claims))
        for v in verified:
            _add_usage(usage, v.pop("_usage", {}))
        overall = round(sum(v["freshness_score"] for v in verified) / len(verified)) if verified else 100
        return {
            "overall_freshness": overall,
            "overall_label": label(overall),
            "checked_on": date.today().isoformat(),
            "claims": verified,
            "stale_count": sum(v["label"] == "stale" for v in verified),
            "judge_model": FG_MODEL,
            "llm_usage": usage,
            "tavily_searches": len(claims),
        }
    finally:
        if own:
            await client.aclose()

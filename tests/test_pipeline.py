"""Offline tests: Bifrost and Tavily are mocked with httpx.MockTransport."""
import asyncio
import json

import httpx

from freshguard import pipeline


def test_scoring_bands():
    assert pipeline.freshness_score("current", 1.0, "high") == 100
    assert pipeline.freshness_score("outdated", 1.0, "high") == 0
    assert pipeline.freshness_score("unverified", 0, "high") < pipeline.freshness_score("unverified", 0, "low")
    assert pipeline.label(90) == "fresh" and pipeline.label(10) == "stale" and pipeline.label(50) == "uncertain"


def test_parse_json_tolerates_fences():
    assert pipeline._parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def _mock_transport():
    def handler(req: httpx.Request) -> httpx.Response:
        if "tavily" in str(req.url):
            return httpx.Response(200, json={"results": [
                {"title": "Python 3.14 released", "url": "https://python.org", "content": "Python 3.14 is the latest.",
                 "published_date": "2026-10-07"}]})
        prompt = json.loads(req.content)["messages"][-1]["content"]
        if "extract up to" in prompt:
            out = {"claims": [{"claim": "The latest Python version is 3.11.", "category": "version",
                               "volatility": "high", "search_query": "latest python version"}]}
        else:
            out = {"verdict": "outdated", "confidence": 0.9, "current_fact": "Python 3.14",
                   "reason": "Newer release exists.", "source_ids": [0]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(out)}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
    return httpx.MockTransport(handler)


def test_end_to_end_flags_stale_claim():
    async def run():
        async with httpx.AsyncClient(transport=_mock_transport()) as c:
            return await pipeline.check_answer("The latest Python is 3.11.", c)
    rep = asyncio.run(run())
    assert rep["stale_count"] == 1
    cl = rep["claims"][0]
    assert cl["label"] == "stale" and cl["current_fact"] == "Python 3.14"
    assert cl["sources"][0]["url"] == "https://python.org"
    assert rep["llm_usage"]["total_tokens"] == 30

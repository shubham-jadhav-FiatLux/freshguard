"""FreshGuard HTTP service.

- GET  /                      -> demo UI
- POST /api/check             -> {"answer": "..."} -> freshness report
- POST /api/ask               -> {"question": "..."} -> LLM answer (via Bifrost) + freshness report
- POST /v1/chat/completions   -> drop-in OpenAI-compatible proxy in front of Bifrost that attaches
                                 a `freshguard` report to every (non-streaming) completion.
"""
from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import pipeline

app = FastAPI(title="FreshGuard", version="0.1.0")
STATIC = Path(__file__).parent / "static"


class CheckIn(BaseModel):
    answer: str


class AskIn(BaseModel):
    question: str
    model: str | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health():
    async with httpx.AsyncClient() as c:
        try:
            ok = (await c.get(f"{pipeline.BIFROST_URL}/health", timeout=5)).status_code == 200
        except httpx.HTTPError:
            ok = False
    return {"freshguard": "ok", "bifrost": ok, "tavily_key": bool(pipeline.TAVILY_API_KEY),
            "judge_model": pipeline.FG_MODEL}


def _err(e: Exception) -> HTTPException:
    if isinstance(e, httpx.HTTPStatusError):
        return HTTPException(502, f"Upstream error {e.response.status_code}: {e.response.text[:300]}")
    return HTTPException(500, str(e))


@app.post("/api/check")
async def api_check(body: CheckIn):
    if not body.answer.strip():
        raise HTTPException(400, "answer is empty")
    try:
        return await pipeline.check_answer(body.answer)
    except Exception as e:
        raise _err(e)


@app.post("/api/ask")
async def api_ask(body: AskIn):
    try:
        async with httpx.AsyncClient() as c:
            answer, usage = await pipeline.chat(
                c, [{"role": "system", "content": "Answer concisely from your own knowledge. Do not hedge."},
                    {"role": "user", "content": body.question}],
                model=body.model or pipeline.FG_ANSWER_MODEL, temperature=0.3)
            report = await pipeline.check_answer(answer, c)
        return {"question": body.question, "answer": answer, "answer_usage": usage, "report": report}
    except Exception as e:
        raise _err(e)


@app.post("/v1/chat/completions")
async def proxy(request: Request):
    """Drop-in replacement for Bifrost's endpoint: same request, same response + `freshguard` field."""
    body = await request.json()
    if body.get("stream"):
        raise HTTPException(400, "FreshGuard proxy supports non-streaming requests only")
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{pipeline.BIFROST_URL}/v1/chat/completions", json=body, timeout=120)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"].get("content") or ""
            data["freshguard"] = await pipeline.check_answer(text, c) if text.strip() else None
    except Exception as e:
        raise _err(e)
    score = (data["freshguard"] or {}).get("overall_freshness", 100)
    return JSONResponse(data, headers={"X-FreshGuard-Score": str(score)})

# FreshGuard: a freshness check for LLM answers, built on Bifrost + Tavily

> LLMs answer confidently from training data that is months or years old.
> FreshGuard catches the outdated parts of an answer before your users act on them.

FreshGuard is a **verification layer that runs alongside the Bifrost AI gateway**. Any LLM answer, whether from your own app, a chatbot or one pasted in by a user, gets:

1. **Claim extraction:** an LLM, called through Bifrost, pulls out the *time-sensitive* factual claims. These are prices, API/software versions, laws, leadership, company facts and "latest/current" statements. Timeless facts are ignored.
2. **Live verification:** each claim is re-checked against the live web with **Tavily**. Fast-changing claims are biased toward recent pages.
3. **Judgment + freshness score:** a judge LLM, also called through Bifrost, compares the claim with the dated evidence. It returns `current` / `outdated` / `unverified`, a **0–100 freshness score**, the *current fact*, and **source links**.

It ships as two things:
- **A drop-in, OpenAI-compatible endpoint** (`/v1/chat/completions`). Point your app's base URL at FreshGuard instead of Bifrost. Responses come back unchanged plus a `freshguard` report and an `X-FreshGuard-Score` header, so no app code has to change.
- **A web UI** to ask an LLM a question, or paste any AI answer, and see the outdated claims highlighted with sources.

Hackathon: Geek Room Global AI Hackathon 2026.
- **Primary problem statement:** Bifrost: *Extend the open-source Bifrost gateway*.
- **Integrated Tavily problem statement:** *Stale-Answer Detector*.

---

## Example (real output)

Input answer:
> The latest stable Python release is Python 3.11. Twitter is run by CEO Parag Agrawal, and the GPT-4 API costs $0.03 per 1K input tokens. Water boils at 100°C at sea level.

| Claim | Label | Score | What is true now (from live sources) |
|---|---|---|---|
| Latest stable Python is 3.11 | **stale** | 0 | Python 3.15.x is the latest (Oct 2026), per python.org / Wikipedia |
| Twitter CEO is Parag Agrawal | **stale** | 2 | Twitter (now X) has different leadership, per Wikipedia |
| GPT-4 API costs $0.03 / 1K input tokens | **fresh** | 98 | Still the listed legacy GPT-4 price, per OpenAI docs |
| Water boils at 100°C | *(skipped)* | | Not time-sensitive |

Overall freshness: **33 / 100** · 3 Tavily searches · ~5.5k tokens via Bifrost · ~7 s end-to-end.

---

## Architecture

```
            ┌──────────────────────────── FreshGuard (FastAPI) ────────────────────────────┐
 your app ─▶│ /v1/chat/completions ─▶ forward to Bifrost ─▶ answer                          │
 or UI    ─▶│ /api/ask, /api/check          │                                               │
            │                              ▼                                               │
            │   1. extract claims ──LLM──▶ Bifrost ──▶ Groq / Gemini / OpenAI / ...         │
            │   2. verify (parallel) ─────▶ Tavily Search (live web, dated sources)         │
            │   3. judge + score ───LLM──▶ Bifrost (with automatic fallback model)          │
            │                              ▼                                               │
            │   answer + freshguard report {overall score, per-claim verdict, sources}     │
            └──────────────────────────────────────────────────────────────────────────────┘
```

### What each technology contributes
| | Role in FreshGuard |
|---|---|
| **Bifrost (Maxim AI)** | The single gateway for *every* LLM call: the user's answer, claim extraction and judging. It provides provider-agnostic `provider/model` routing (swap Groq to OpenAI to Gemini by changing one env var) and **automatic fallbacks** (`fallbacks: [...]`) when a provider is down or rate-limited. It also gives request logging and token/cost visibility in the Bifrost dashboard. FreshGuard sits next to it as a drop-in endpoint, so any app already on Bifrost gains freshness checking. |
| **Tavily** | Live web retrieval for each flagged claim. It uses advanced search depth and returns content snippets, URLs and publish dates, which become the evidence and citations. |
| **LLMs** (default: `groq/openai/gpt-oss-120b`, fallback `groq/qwen/qwen3.8-27b`) | Time-sensitive claim extraction (JSON mode) and evidence-grounded judging. The judge is told to use **only** the retrieved evidence and to say `unverified` rather than guess. |

### Freshness score
| Verdict | Score |
|---|---|
| `current` | 60 + 40 × confidence → **fresh** (≥ 70) |
| `outdated` | 30 × (1 − confidence) → **stale** (< 35) |
| `unverified` | 35 / 45 / 55 for high / medium / low volatility claims → **uncertain** |

The overall score is the mean over all claims.

---

## Quick start

Requirements: Docker, Python 3.10+, a Tavily API key, and at least one LLM key (Groq's free tier works).

```bash
git clone <this repo> && cd <repo>
cp .env.example .env          # add TAVILY_API_KEY and GROQ_API_KEY (or GEMINI/OPENAI/ANTHROPIC)

./scripts/start_bifrost.sh    # runs maximhq/bifrost in Docker on :8080, configured from .env

python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn freshguard.app:app --port 8000
```

Open **http://localhost:8000** for the UI and **http://localhost:8080** for the Bifrost dashboard (request logs and tokens).

### Configuration (`.env`)
| Variable | Default | Meaning |
|---|---|---|
| `TAVILY_API_KEY` | | required |
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | | any one or more; registered with Bifrost |
| `FG_MODEL` | `groq/openai/gpt-oss-120b` | extractor + judge model (Bifrost `provider/model`) |
| `FG_ANSWER_MODEL` | `FG_MODEL` | model that answers questions in the UI |
| `FG_FALLBACK_MODEL` | | Bifrost fallback model if the primary fails |
| `FG_MAX_CLAIMS` | `6` | maximum claims checked per answer |
| `BIFROST_URL` | `http://localhost:8080` | |

---

## API

**Check any answer**
```bash
curl localhost:8000/api/check -H 'Content-Type: application/json' \
  -d '{"answer": "The latest iPhone is the iPhone 15 Pro, starting at $999."}'
```

**Ask + verify**
```bash
curl localhost:8000/api/ask -H 'Content-Type: application/json' \
  -d '{"question": "What is the latest version of Node.js?"}'
```

**Drop-in for existing OpenAI/Bifrost clients:** just change the base URL:
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused")
r = client.chat.completions.create(model="groq/openai/gpt-oss-120b",
                                   messages=[{"role": "user", "content": "Latest iPhone and price?"}])
print(r.model_extra["freshguard"]["overall_freshness"])   # also in the X-FreshGuard-Score header
```

Report shape:
```json
{
  "overall_freshness": 34, "overall_label": "stale", "stale_count": 2, "checked_on": "2026-11-15",
  "claims": [{
    "claim": "The latest iPhone model is the iPhone 15 Pro", "category": "version", "volatility": "high",
    "verdict": "outdated", "confidence": 0.9, "freshness_score": 3, "label": "stale",
    "current_fact": "The latest iPhone models are the iPhone 18 Pro / Pro Max (Sep 2026)",
    "reason": "Newer models have been released.", "sources": [{"title": "...", "url": "...", "published_date": "..."}]
  }],
  "judge_model": "groq/openai/gpt-oss-120b", "llm_usage": {"total_tokens": 5572}, "tavily_searches": 3
}
```

---

## Tests
```bash
.venv/bin/python -m pytest -q
```
The offline tests mock Bifrost and Tavily with `httpx.MockTransport`. They cover the scoring bands, JSON parsing, and an end-to-end stale-claim detection.

## Project layout
```
freshguard/pipeline.py      claim extraction → Tavily verification → judging → scoring
freshguard/app.py           FastAPI: UI, /api/check, /api/ask, drop-in /v1/chat/completions
freshguard/static/index.html  demo UI
scripts/start_bifrost.sh    starts Bifrost in Docker, configured from .env
tests/                      offline tests
```

## How AI is used
- LLMs (through Bifrost) **extract** time-sensitive claims and **judge** them against retrieved evidence. Both use JSON mode at temperature 0.
- Tavily's AI search **retrieves** current, dated evidence for each claim.
- The project was built during the hackathon with help from an AI coding assistant (Claude Code).

## Limitations & next steps
- Judgments are only as good as the retrieved evidence. Low-evidence claims are reported as `uncertain` instead of guessed.
- Streaming responses aren't checked yet; the proxy handles non-streaming completions.
- Next steps:
  - package the check as a native Bifrost `PostLLMHook` plugin so it runs inside the gateway;
  - cache verdicts per claim with a TTL by volatility;
  - add per-domain trusted-source lists such as official docs and pricing pages.

## License
MIT

# FreshGuard: a freshness check for LLM answers, built on Bifrost + Tavily

> LLMs answer confidently from training data that is months or years old.
> FreshGuard catches the outdated parts of an answer before your users act on them.

FreshGuard is a **verification layer that runs alongside the Bifrost AI gateway**. Any LLM answer, whether from your own app, a chatbot or one pasted in by a user, gets:

1. **Claim extraction:** an LLM, called through Bifrost, pulls out the *time-sensitive* factual claims. These are prices, API/software versions, laws, leadership, company facts and "latest/current" statements. Timeless facts are ignored.
2. **Live verification (hybrid retrieval):** for each claim, two **Tavily** searches run in parallel. A **news search limited to the last 30 days** looks for recent *changes*, and a general web search finds reference pages. News is ranked first and labelled `[NEWS]` for the judge.
3. **Judgment + freshness score:** a judge LLM, also called through Bifrost, compares the claim with the dated evidence. It returns `current` / `outdated` / `unverified`, a **0–100 freshness score**, the *current fact*, and **source links**.

It plugs into Bifrost in **three ways**, each through a public Bifrost extension point or interface:

| # | Integration | Bifrost extension point | Works on stock `maximhq/bifrost`? |
|---|---|---|---|
| 1 | **MCP tool server**: `verify_freshness` and `verify_claim`, auto-executed by Bifrost **Agent Mode** | MCP gateway (`mcp.client_configs`, `tools_to_auto_execute`) | ✅ yes, verified end to end (direct tool execution + Agent Mode) |
| 2 | **Native Go plugin** (`bifrost-plugin/`): annotates every chat completion with `X-FreshGuard-*` headers and a report | `HTTPTransportPostHook` plugin interface | needs a dynamically built Bifrost (see plugin README) |
| 3 | **Drop-in OpenAI-compatible endpoint**: point the base URL at FreshGuard | Bifrost's OpenAI-compatible API | ✅ yes |

There is also a **web UI** to ask an LLM a question, or paste any AI answer, and see the outdated claims highlighted with sources.

### Demo through a stock Bifrost gateway (real output, `scripts/demo_agent_mode.sh`)
```
━━ 1) LLM answer via Bifrost (groq/qwen/qwen3.8-27b), no tools ━━
The latest stable Python version in my training knowledge is Python 3.12. The newest iPhone is the
iPhone 15 Pro Max, which has a starting price of $1,199.

━━ 2) FreshGuard via Bifrost MCP gateway: tool freshguard-verify_freshness ━━
Overall freshness: 34/100 (stale)
 ❌ [  1] The latest stable Python version is Python 3.12
        now: The latest stable Python version as of November 15 2026 is Python 3.15.2
 ❌ [  2] The newest iPhone model is the iPhone 15 Pro Max
        now: As of 2026-11-15 the latest iPhone model is the iPhone 18 Pro Max
 ✅ [ 99] The iPhone 15 Pro Max has a starting price of $1,199
```
Step 2 goes through Bifrost's own `/v1/mcp/tool/execute` endpoint. With `AGENT=1`, step 3 lets **Bifrost Agent Mode** run the tool loop itself: the model calls `freshguard-verify_freshness` and rewrites its answer. In our tests, `gpt-oss-120b` corrected "Python 3.13.2" to "3.15.2" this way. Some Groq models reject multi-step tool loops intermittently, which is why the default demo uses direct tool execution.

Hackathon: Geek Room Global AI Hackathon 2026 · Pitch deck: [docs/FreshGuard_Pitch.pdf](docs/FreshGuard_Pitch.pdf)
- **Primary problem statement:** Bifrost: *Extend the open-source Bifrost gateway*.
- **Integrated Tavily problem statement:** *Stale-Answer Detector*.

---

## Caught in the wild: a change from 3 days ago

On 12 Nov 2026 Jensen Huang resigned as NVIDIA's CEO, and Colette Kress was named interim CEO. While we were building this, our *own AI coding assistant* still answered "Jensen Huang".

The first FreshGuard version **also rated that claim fresh (99/100)**. It only searched the general web, where company profiles still list Huang. We added recent-news retrieval and an evidence rule: credible recent news of a change overrides older pages. Now:

| Claim | Before | After | Evidence |
|---|---|---|---|
| "The CEO of NVIDIA is Jensen Huang." | fresh · 99 ❌ | **stale · 0** ✅ | NVIDIA newsroom "CEO transition", NPR, AP… (12–13 Nov 2026) |
| "Satya Nadella is the CEO of Microsoft." *(control)* | fresh | **fresh · 99** ✅ | Nov 2026 news still names Nadella |

A regression test (`test_recent_news_overrides_stale_profile_pages`) locks this in.

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
                    ┌──────────────────── Bifrost gateway (:8080) ─────────────────────┐
  app / agent ────▶ │ /v1/chat/completions                                             │
                    │   ├─ MCP gateway ── Agent Mode auto-calls ──┐                    │
                    │   ├─ Go plugin: HTTPTransportPostHook ──────┤  (x-freshguard-    │
                    │   └─ routing + fallbacks ─▶ Groq/Gemini/…   │   skip on internal │
                    └─────────────────────────────────────────────┼───── calls) ───────┘
                                                                  ▼
                    ┌─────────────── FreshGuard (:8000 API/UI, :8001 MCP) ─────────────┐
                    │ 1. extract time-sensitive claims ─LLM via Bifrost (JSON mode)    │
                    │ 2. verify each claim in parallel ─▶ Tavily Search (dated pages)  │
                    │ 3. judge on evidence only ────────LLM via Bifrost (+ fallback)   │
                    │ 4. score 0–100 per claim → report {verdict, current fact, URLs}  │
                    └──────────────────────────────────────────────────────────────────┘
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
git clone https://github.com/shubham-jadhav-FiatLux/freshguard && cd freshguard
cp .env.example .env          # add TAVILY_API_KEY and GROQ_API_KEY (or GEMINI/OPENAI/ANTHROPIC)

python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./scripts/run.sh              # FreshGuard API/UI on :8000 + MCP server on :8001 (keep running)

# in a second terminal:
./scripts/start_bifrost.sh    # stock maximhq/bifrost in Docker on :8080: providers from .env,
                              # FreshGuard registered as an MCP client with Agent Mode auto-execute
./scripts/demo_agent_mode.sh  # before/after: same question without and with FreshGuard
```

Open **http://localhost:8000** for the UI and **http://localhost:8080** for the Bifrost dashboard. The dashboard shows request logs, tokens and MCP tool calls.

> The MCP server listens on `0.0.0.0:8001` so the Bifrost container can reach it via `host.docker.internal`. On a shared network, firewall that port or set `FG_MCP_HOST`.

### Native Go plugin
```bash
cd bifrost-plugin && make test && make build   # -> build/freshguard.so
```
See [`bifrost-plugin/README.md`](bifrost-plugin/README.md) for the `config.json` block and the dynamic-build requirement.

### Configuration (`.env`)
| Variable | Default | Meaning |
|---|---|---|
| `TAVILY_API_KEY` | | required |
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | | any one or more; registered with Bifrost |
| `FG_MODEL` | `groq/openai/gpt-oss-120b` | extractor + judge model (Bifrost `provider/model`) |
| `FG_ANSWER_MODEL` | `FG_MODEL` | model that answers questions in the UI |
| `FG_FALLBACK_MODEL` | | Bifrost fallback model if the primary fails |
| `FG_MAX_CLAIMS` | `6` | maximum claims checked per answer |
| `FG_NEWS_DAYS` | `30` | recency window of the news search |
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
.venv/bin/python -m pytest -q          # Python: scoring, parsing, end-to-end with mocks
cd bifrost-plugin && go test ./...     # Go plugin: path filter, skip header, annotate, fail-open
```
The offline tests mock Bifrost and Tavily with `httpx.MockTransport`. They cover the scoring bands, JSON parsing, and an end-to-end stale-claim detection.

## Project layout
```
freshguard/pipeline.py      claim extraction → Tavily verification → judging → scoring
freshguard/app.py           FastAPI: UI, /api/check, /api/ask, drop-in /v1/chat/completions
freshguard/static/index.html  demo UI
freshguard/mcp_server.py    MCP server (verify_freshness, verify_claim) for Bifrost's MCP gateway
bifrost-plugin/             native Bifrost Go plugin (HTTPTransportPostHook) + unit tests
scripts/run.sh              runs API/UI + MCP server
scripts/start_bifrost.sh    starts stock Bifrost in Docker, configured from .env (providers + MCP)
scripts/demo_agent_mode.sh  before/after Agent Mode demo
tests/                      offline Python tests
```

## How AI is used
- LLMs (through Bifrost) **extract** time-sensitive claims and **judge** them against retrieved evidence. Both use JSON mode at temperature 0.
- Tavily's AI search **retrieves** current, dated evidence for each claim.
- The project was built during the hackathon with help from an AI coding assistant (Claude Code).

## Limitations & next steps
- Judgments are only as good as the retrieved evidence. Low-evidence claims are reported as `uncertain` instead of guessed. Changes newer than the search index (minutes old) can still be missed.
- Streaming responses aren't checked yet; the proxy and the plugin handle non-streaming completions.
- On Groq's free tier, `gpt-oss-120b` is limited to 8k tokens/min. One check uses about 5k tokens, so Bifrost's fallback model takes over under load.
- Next steps:
  - publish a Bifrost image variant with the Go plugin preloaded;
  - cache verdicts per claim with a TTL by volatility;
  - add per-domain trusted-source lists such as official docs and pricing pages.

## License
MIT

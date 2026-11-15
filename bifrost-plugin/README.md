# FreshGuard: native Bifrost Go plugin

A Bifrost **HTTP transport plugin**. After every successful, non-streaming `/v1/chat/completions` response, it sends the assistant's answer to the FreshGuard service. That service extracts time-sensitive claims and re-verifies them live with Tavily. The plugin then annotates the response with:

| Header | Meaning |
|---|---|
| `X-FreshGuard-Status` | `checked` / `skipped` (answer too short) / `error` (service unavailable, so it fails open) |
| `X-FreshGuard-Score` | overall freshness 0–100 |
| `X-FreshGuard-Label` | `fresh` / `uncertain` / `stale` |
| `X-FreshGuard-Stale-Count` | number of outdated claims |
| `X-FreshGuard-Claims` | number of time-sensitive claims checked |

It also adds an optional `freshguard` field to the JSON body containing the full per-claim report (verdict, current fact, sources).

Design rules:
- **Fail open.** Any error leaves the original response untouched and only adds `X-FreshGuard-Status: error`.
- **Opt out per request** with `x-freshguard-skip: 1`. FreshGuard sends this on its own internal LLM calls, which prevents recursion.
- **Streaming is left untouched.** Event-stream responses pass straight through.
- The core logic (`freshness.go`) has no Bifrost dependency, so it is unit-tested in isolation.

## Build & test
```bash
make test     # 5 unit tests (fake FreshGuard service via httptest)
make build    # -> build/freshguard.so
```

> **Note.** Go plugins (`-buildmode=plugin`) only load into a Bifrost binary built **dynamically**, with the same Go version and the same `github.com/maximhq/bifrost/core` version as the plugin (see Bifrost's *Building a dynamic binary* guide). The default `maximhq/bifrost` Docker image is statically linked. On the stock image, use FreshGuard's **MCP integration** instead (see the root README). It works with a standard Bifrost install today.

## Configure (Bifrost `config.json`)
```json
{
  "plugins": [{
    "enabled": true,
    "name": "freshguard",
    "path": "/app/plugins/freshguard.so",
    "config": {
      "check_url": "http://localhost:8000/api/check",
      "paths": ["/v1/chat/completions"],
      "timeout_seconds": 60,
      "embed_report": true,
      "min_chars": 40
    }
  }]
}
```

Built against `github.com/maximhq/bifrost/core v1.15.2`.

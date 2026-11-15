"""Pretty-prints a Bifrost /v1/mcp/tool/execute response that carries a FreshGuard report (stdin)."""
import json
import sys

d = json.load(sys.stdin)
c = d.get("content", d)
if isinstance(c, list):
    c = "".join(p.get("text", "") for p in c if isinstance(p, dict))
try:
    r = json.loads(c) if isinstance(c, str) else c
except json.JSONDecodeError:
    sys.exit(print(c))
if isinstance(r, dict) and "result" in r:
    r = r["result"]
if not isinstance(r, dict) or "claims" not in r:
    sys.exit(print(d))
icon = {"fresh": "✅", "stale": "❌", "uncertain": "⚠️ "}
print(f"Overall freshness: {r['overall_freshness']}/100 ({r['overall_label']})")
for cl in r["claims"]:
    print(f" {icon.get(cl['label'], '?')} [{cl['freshness_score']:>3}] {cl['claim']}")
    if cl["label"] != "fresh" and cl.get("current_fact"):
        print(f"        now: {cl['current_fact']}")
    if cl.get("sources"):
        print(f"        src: {cl['sources'][0]}")

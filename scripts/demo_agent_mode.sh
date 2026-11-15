#!/usr/bin/env bash
# End-to-end demo through a STOCK Bifrost gateway:
#   1) ask an LLM via Bifrost with MCP tools disabled -> typical (possibly stale) answer
#   2) verify that answer with FreshGuard through Bifrost's MCP gateway (/v1/mcp/tool/execute)
#   3) optional (AGENT=1): Bifrost Agent Mode, where the model calls freshguard-verify_freshness itself
set -euo pipefail
BIFROST=${BIFROST:-http://localhost:8080}
MODEL=${MODEL:-groq/qwen/qwen3.8-27b}
Q=${1:-"What is the latest stable Python version, and what is the newest iPhone and its starting price?"}

ask_body=$(python3 -c 'import json,sys;print(json.dumps({"model":sys.argv[1],"messages":[{"role":"user","content":sys.argv[2]+" Answer confidently in 2-3 sentences from your own training knowledge; do not refuse or mention browsing."}]}))' "$MODEL" "$Q")

echo "━━ 1) LLM answer via Bifrost ($MODEL), no tools ━━"
answer=$(curl -s "$BIFROST/v1/chat/completions" -H 'Content-Type: application/json' -H 'x-bf-mcp-include-clients;' -d "$ask_body" \
  | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["choices"][0]["message"]["content"] if "choices" in d else d)')
echo "$answer"
echo

echo "━━ 2) FreshGuard via Bifrost MCP gateway: tool freshguard-verify_freshness ━━"
call=$(python3 -c 'import json,sys;print(json.dumps({"id":"call_fg_1","type":"function","function":{"name":"freshguard-verify_freshness","arguments":json.dumps({"text":sys.argv[1]})}}))' "$answer")
curl -s "$BIFROST/v1/mcp/tool/execute" -H 'Content-Type: application/json' -d "$call" | python3 "$(dirname "$0")/fmt_report.py"

if [ "${AGENT:-0}" = "1" ]; then
  echo
  echo "━━ 3) Bifrost Agent Mode: the model calls FreshGuard itself ━━"
  agent_body=$(python3 -c 'import json,sys;print(json.dumps({"model":sys.argv[1],"messages":[{"role":"system","content":"Before answering anything time-sensitive, verify your draft by calling the tool freshguard-verify_freshness, then answer with sources."},{"role":"user","content":sys.argv[2]}]}))' "${AGENT_MODEL:-groq/openai/gpt-oss-120b}" "$Q")
  curl -s "$BIFROST/v1/chat/completions" -H 'Content-Type: application/json' -H 'x-bf-mcp-include-clients: freshguard' -d "$agent_body" \
    | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["choices"][0]["message"]["content"] if "choices" in d else "(provider rejected the tool loop: "+str(d.get("error",{}).get("message"))+")")'
fi

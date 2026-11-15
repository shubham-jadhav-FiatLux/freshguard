#!/usr/bin/env bash
# Starts a local Bifrost gateway in Docker, configured from the LLM keys present in .env.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Create .env first (see .env.example)"; exit 1; }
set -a; source .env; set +a

mkdir -p bifrost-data
providers=()
add() { providers+=("\"$1\": {\"keys\": [{\"name\": \"$1-key\", \"value\": \"env.$2\", \"models\": [\"*\"], \"weight\": 1.0}]}"); }
[ -n "${GROQ_API_KEY:-}" ]      && add groq GROQ_API_KEY
[ -n "${GEMINI_API_KEY:-}" ]    && add gemini GEMINI_API_KEY
[ -n "${OPENAI_API_KEY:-}" ]    && add openai OPENAI_API_KEY
[ -n "${ANTHROPIC_API_KEY:-}" ] && add anthropic ANTHROPIC_API_KEY
[ ${#providers[@]} -gt 0 ] || { echo "No LLM provider key found in .env"; exit 1; }

joined=$(IFS=,; echo "${providers[*]}")
FG_MCP_URL="${FG_MCP_URL:-http://host.docker.internal:8001/mcp}"
cat > bifrost-data/config.json <<EOF
{
  "client": { "enable_logging": true, "enforce_auth_on_inference": false },
  "providers": { $joined },
  "mcp": {
    "client_configs": [{
      "name": "freshguard",
      "connection_type": "http",
      "connection_string": "$FG_MCP_URL",
      "tools_to_execute": ["*"],
      "tools_to_auto_execute": ["*"]
    }],
    "tool_manager_config": { "max_agent_depth": 5, "tool_execution_timeout": "90s" }
  }
}
EOF

docker rm -f bifrost >/dev/null 2>&1 || true
# config.json is the source of truth: drop the cached config DB so edits always apply (request logs are kept)
rm -f bifrost-data/config.db bifrost-data/config.db-shm bifrost-data/config.db-wal
docker run -d --name bifrost -p 8080:8080 --add-host=host.docker.internal:host-gateway \
  --env-file .env -v "$PWD/bifrost-data:/app/data" maximhq/bifrost >/dev/null
echo -n "Waiting for Bifrost"
for _ in $(seq 1 40); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health)" = "200" ] && { echo " ready on http://localhost:8080"; exit 0; }
  echo -n "."; sleep 2
done
echo " timed out; check: docker logs bifrost"; exit 1

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
cat > bifrost-data/config.json <<EOF
{ "client": { "enable_logging": true, "enforce_auth_on_inference": false }, "providers": { $joined } }
EOF

docker rm -f bifrost >/dev/null 2>&1 || true
docker run -d --name bifrost -p 8080:8080 --env-file .env -v "$PWD/bifrost-data:/app/data" maximhq/bifrost >/dev/null
echo -n "Waiting for Bifrost"
for _ in $(seq 1 40); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health)" = "200" ] && { echo " ready on http://localhost:8080"; exit 0; }
  echo -n "."; sleep 2
done
echo " timed out; check: docker logs bifrost"; exit 1

#!/usr/bin/env bash
# Runs the FreshGuard API/UI (:8000) and the FreshGuard MCP server (:8001) together. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
"$PY" -m freshguard.mcp_server & MCP=$!
trap 'kill $MCP 2>/dev/null' EXIT INT TERM
"$PY" -m uvicorn freshguard.app:app --host 127.0.0.1 --port 8000

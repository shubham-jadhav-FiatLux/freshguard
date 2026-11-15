"""FreshGuard as an MCP server, so Bifrost's MCP gateway can expose it to every model and app.

Run:  .venv/bin/python -m freshguard.mcp_server        (streamable HTTP on :8001/mcp)

Registered in Bifrost through config.json -> mcp.client_configs (see scripts/start_bifrost.sh).
With `tools_to_auto_execute`, Bifrost's Agent Mode calls `verify_freshness` on its own when a model
wants to check facts, with no client-side tool loop needed.
"""
from __future__ import annotations

import os

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from . import pipeline

server = MCPServer(
    name="freshguard",
    instructions=(
        "FreshGuard checks whether facts in a text are still true today. Call verify_freshness on any "
        "answer that mentions prices, versions, laws, leadership, company facts or 'latest' items "
        "before presenting it to the user, then correct stale claims using current_fact and cite sources."
    ),
)


def _compact(report: dict) -> dict:
    """Return a smaller report so it fits easily into a model's context."""
    return {
        "overall_freshness": report["overall_freshness"],
        "overall_label": report["overall_label"],
        "checked_on": report["checked_on"],
        "claims": [
            {k: c.get(k) for k in ("claim", "label", "freshness_score", "verdict", "current_fact", "reason")}
            | {"sources": [s.get("url") for s in c.get("sources", [])]}
            for c in report["claims"]
        ],
    }


@server.tool(description=(
    "Verify whether the factual claims in a piece of text (typically an AI-generated answer) are still "
    "current. Extracts time-sensitive claims, re-checks each against the live web with Tavily, and "
    "returns a 0-100 freshness score per claim with the current fact and source URLs."
))
async def verify_freshness(text: str) -> dict:
    return _compact(await pipeline.check_answer(text))


@server.tool(description="Verify a single time-sensitive claim against live web sources and return its freshness.")
async def verify_claim(claim: str) -> dict:
    return _compact(await pipeline.check_answer(claim))


def app():
    # Bifrost runs in Docker and reaches us as host.docker.internal, so allow that Host header.
    hosts = os.getenv("FG_MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,host.docker.internal:*").split(",")
    return server.streamable_http_app(
        stateless_http=True, json_response=True, host="0.0.0.0",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                                     allowed_hosts=hosts, allowed_origins=[]),
    )


if __name__ == "__main__":
    uvicorn.run(app(), host=os.getenv("FG_MCP_HOST", "0.0.0.0"), port=int(os.getenv("FG_MCP_PORT", "8001")))

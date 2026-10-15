"""INTEGRATION: the MCP server over stdio, driven by a real MCP client (requires FalkorDB)."""

import asyncio
import json
import os
import sys

import pytest

from conftest import ROOT, TEST_GRAPH

pytestmark = pytest.mark.integration


def test_mcp_server_stdio(ingested, store):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {**os.environ, "FALKORDB_GRAPH": TEST_GRAPH}
    if os.getenv("FALKORDB_TEST_URL"):
        env["FALKORDB_URL"] = os.environ["FALKORDB_TEST_URL"]

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "researchmind.mcp_server"], cwd=str(ROOT), env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                result = await session.call_tool("compare_claims", {"topic": "generalization to unseen proteins"})
                return names, json.loads("".join(getattr(c, "text", "") for c in result.content))

    names, payload = asyncio.run(run())
    assert names == {"list_papers", "search_evidence", "get_paper", "explore_entity", "find_related_papers",
                     "compare_claims", "find_research_gaps", "get_evidence", "graph_query"}
    assert payload["contradictions"]

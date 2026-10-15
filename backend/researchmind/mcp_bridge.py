"""In-process MCP client the investigation agent uses to call the ResearchMind MCP tools.

The agent never calls graph functions directly: every tool call goes through the MCP server built
by `researchmind.mcp_server.build_server`, over the MCP client protocol (in-process, no subprocess).
That keeps one tool surface for external MCP clients (Claude Desktop, Claude Code) and the agent.
"""

from __future__ import annotations

import asyncio
import json
import logging

from mcp import Client

from .mcp_server import build_server
from .tools import ResearchTools

log = logging.getLogger(__name__)


class MCPToolError(Exception):
    """The MCP server reported a tool failure (bad arguments or an exception inside the tool)."""


class MCPToolClient:
    """Calls ResearchMind tools through an in-process MCP server bound to `tools`.

    Each call opens a short-lived in-process client session (~25 ms), which keeps the bridge
    safe to use from any worker thread without sharing an event loop.
    """

    def __init__(self, tools: ResearchTools, timeout_seconds: float = 60.0):
        self.tools = tools
        self.server = build_server(lambda: tools)
        self.timeout_seconds = timeout_seconds

    def list_tools(self) -> list[str]:
        async def run():
            async with Client(self.server) as client:
                return [t.name for t in (await client.list_tools()).tools]
        return asyncio.run(run())

    def call(self, name: str, args: dict) -> dict:
        async def run():
            async with Client(self.server, read_timeout_seconds=self.timeout_seconds) as client:
                return await client.call_tool(name, args)

        result = asyncio.run(run())
        text = "".join(getattr(c, "text", "") for c in result.content)
        if result.is_error:
            raise MCPToolError(text or f"Tool {name} failed")
        if isinstance(result.structured_content, dict):
            payload = result.structured_content.get("result", result.structured_content)
            if isinstance(payload, dict):
                return payload
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError:
            return {"error": f"{name} returned a non-JSON result"}
        return payload if isinstance(payload, dict) else {"result": payload}

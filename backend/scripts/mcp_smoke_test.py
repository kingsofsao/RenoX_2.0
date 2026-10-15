"""Start the MCP server over stdio as a real MCP client would, list its tools and call two of them.

Usage:  python scripts/mcp_smoke_test.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


def _text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=["-m", "researchmind.mcp_server"],
                                   cwd=str(ROOT), env={**os.environ})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = [t.name for t in (await session.list_tools()).tools]
            print("tools:", ", ".join(names))

            papers = json.loads(_text(await session.call_tool("list_papers", {})))
            print(f"list_papers -> {papers['count']} papers")

            res = json.loads(_text(await session.call_tool("search_evidence", {"query": "generalization to unseen proteins", "top_k": 2})))
            for r in res["results"]:
                print(f"search_evidence -> [{r['chunk_id']}] {r['paper_title']} p.{r['page']}")
            gaps = json.loads(_text(await session.call_tool("find_research_gaps", {"max_gaps": 3})))
            for g in gaps["gaps"]:
                print(f"find_research_gaps -> {g['id']} {g['type']}: {g['title'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

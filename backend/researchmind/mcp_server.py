"""MCP server exposing the ResearchMind graph tools.

Run over stdio (for Claude Desktop, Claude Code, or any MCP client):
    python -m researchmind.mcp_server

The investigation agent talks to the same server in-process (see `researchmind.mcp_bridge`),
so there is one tool implementation (`researchmind.tools.ResearchTools`) behind both.
"""

from __future__ import annotations

import logging
import sys
from typing import Callable

from mcp.server.mcpserver import MCPServer

from .graph import GraphStore
from .tools import ResearchTools

INSTRUCTIONS = (
    "Tools over a FalkorDB knowledge graph of scientific papers. Every result carries evidence chunk ids "
    "(e.g. p_1a2b3c4d5e6f:c003) with paper and page; cite them. Start with list_papers."
)


def build_server(get_tools: Callable[[], ResearchTools]) -> MCPServer:
    """Create an MCP server whose tools delegate to `get_tools()` (resolved lazily on each call)."""
    server = MCPServer(name="researchmind", instructions=INSTRUCTIONS)

    @server.tool()
    def list_papers() -> dict:
        """List all papers in the knowledge graph with ids, titles, authors and years."""
        return get_tools().list_papers()

    @server.tool()
    def search_evidence(query: str, top_k: int = 6, paper_id: str | None = None) -> dict:
        """Hybrid semantic + keyword search over page-level evidence passages. Returns chunk ids, pages and extracted statements."""
        return get_tools().search_evidence(query, top_k, paper_id)

    @server.tool()
    def get_paper(paper_id: str) -> dict:
        """Structured record of one paper: methods, datasets, claims, findings, limitations, each with evidence."""
        return get_tools().get_paper(paper_id)

    @server.tool()
    def explore_entity(name: str, entity_type: str = "auto") -> dict:
        """Multi-hop traversal from a method or dataset to the papers, results and limitations connected to it.
        entity_type: auto | method | dataset."""
        return get_tools().explore_entity(name, entity_type)

    @server.tool()
    def find_related_papers(paper_id: str) -> dict:
        """Papers linked to this one by shared methods/datasets, similar or contradicting statements, or addressed limitations."""
        return get_tools().find_related_papers(paper_id)

    @server.tool()
    def compare_claims(topic: str, top_k: int = 10) -> dict:
        """Claims and findings about a topic across papers, with detected contradictions and closely related statements."""
        return get_tools().compare_claims(topic, top_k)

    @server.tool()
    def find_research_gaps(topic: str | None = None, max_gaps: int = 8) -> dict:
        """Candidate research gaps (unaddressed/recurring limitations, conflicts, untested method-dataset combinations) with evidence."""
        return get_tools().find_research_gaps(topic, max_gaps)

    @server.tool()
    def get_evidence(chunk_ids: list[str]) -> dict:
        """Full text, paper and page for specific evidence chunk ids."""
        return get_tools().get_evidence(chunk_ids)

    @server.tool()
    def graph_query(cypher: str) -> dict:
        """Read-only Cypher over the graph (Paper, Author, Chunk, Method, Dataset, Claim, Finding, Limitation). Return properties, not nodes."""
        return get_tools().graph_query(cypher)

    return server


_tools: ResearchTools | None = None


def tools() -> ResearchTools:
    global _tools
    if _tools is None:
        _tools = ResearchTools(GraphStore())
    return _tools


# Module-level server for the stdio entry point (connects to FalkorDB on the first tool call).
mcp = build_server(tools)


def main() -> None:
    # stdout carries the MCP protocol over stdio, so logs must go to stderr.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    mcp.run("stdio")


if __name__ == "__main__":
    main()

"""MCP server exposing the ResearchMind graph tools.

Run over stdio (for Claude Desktop, Claude Code, or any MCP client):
    python -m researchmind.mcp_server

The tools are the same implementations the built-in investigation agent uses.
"""

from __future__ import annotations

import logging
import sys

from mcp.server.mcpserver import MCPServer

from .graph import GraphStore
from .tools import ResearchTools

# stdout carries the MCP protocol over stdio, so logs must go to stderr.
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)

mcp = MCPServer(
    name="researchmind",
    instructions=(
        "Tools over a FalkorDB knowledge graph of scientific papers. Every result carries evidence chunk ids "
        "(e.g. p_1a2b3c4d5e6f:c003) with paper and page; cite them. Start with list_papers."
    ),
)

_tools: ResearchTools | None = None


def tools() -> ResearchTools:
    global _tools
    if _tools is None:
        _tools = ResearchTools(GraphStore())
    return _tools


@mcp.tool()
def list_papers() -> dict:
    """List all papers in the knowledge graph with ids, titles, authors and years."""
    return tools().list_papers()


@mcp.tool()
def search_evidence(query: str, top_k: int = 6, paper_id: str | None = None) -> dict:
    """Hybrid semantic + keyword search over page-level evidence passages. Returns chunk ids, pages and extracted statements."""
    return tools().search_evidence(query, top_k, paper_id)


@mcp.tool()
def get_paper(paper_id: str) -> dict:
    """Structured record of one paper: methods, datasets, claims, findings, limitations, each with evidence."""
    return tools().get_paper(paper_id)


@mcp.tool()
def explore_entity(name: str, entity_type: str = "auto") -> dict:
    """Multi-hop traversal from a method or dataset to the papers, results and limitations connected to it.
    entity_type: auto | method | dataset."""
    return tools().explore_entity(name, entity_type)


@mcp.tool()
def find_related_papers(paper_id: str) -> dict:
    """Papers linked to this one by shared methods/datasets, similar or contradicting statements, or addressed limitations."""
    return tools().find_related_papers(paper_id)


@mcp.tool()
def compare_claims(topic: str, top_k: int = 10) -> dict:
    """Claims and findings about a topic across papers, with detected contradictions and closely related statements."""
    return tools().compare_claims(topic, top_k)


@mcp.tool()
def find_research_gaps(topic: str | None = None, max_gaps: int = 8) -> dict:
    """Candidate research gaps (unaddressed/recurring limitations, conflicts, untested method-dataset combinations) with evidence."""
    return tools().find_research_gaps(topic, max_gaps)


@mcp.tool()
def get_evidence(chunk_ids: list[str]) -> dict:
    """Full text, paper and page for specific evidence chunk ids."""
    return tools().get_evidence(chunk_ids)


@mcp.tool()
def graph_query(cypher: str) -> dict:
    """Read-only Cypher over the graph (Paper, Author, Chunk, Method, Dataset, Claim, Finding, Limitation). Return properties, not nodes."""
    return tools().graph_query(cypher)


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()

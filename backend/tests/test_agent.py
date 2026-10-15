"""Investigation agent: offline plan, Claude tool-use loop (with a scripted fake client), citations."""

import json
from types import SimpleNamespace

from researchmind.agent import Investigator
from researchmind.extract import ClaudeExtractor
from researchmind.ingest import parse_pdf
from researchmind.report import finalize_citations


def block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


class FakeLLM:
    """Mimics ClaudeLLM.create by replaying scripted responses and recording requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def test_offline_investigation(ingested, store):
    events = []
    result = Investigator(store, use_llm=False).run(
        "Do graph attention models generalize to unseen proteins?", on_event=events.append)
    assert result.mode == "offline"
    assert {"## Answer", "## Agreements and Conflicts", "## Candidate Research Gaps", "## References"} <= {
        line.strip() for line in result.report_markdown.splitlines()}
    assert result.references and not result.warnings
    assert all(r.get("paper") and r.get("page") for r in result.references)
    assert "p_" not in result.report_markdown.split("## References")[0].replace("`p_", "")  # ids replaced by [n]
    assert any(e["type"] == "tool_call" for e in events) and events[-1]["type"] == "done"


def test_claude_loop_with_fake_client(ingested, store):
    tools_probe = Investigator(store, use_llm=False).tools
    hit = tools_probe.search_evidence("unseen proteins", top_k=1)["results"][0]
    cid = hit["chunk_id"]
    fake = FakeLLM([
        SimpleNamespace(stop_reason="tool_use", content=[
            block("text", text="I'll search the evidence first."),
            block("tool_use", id="tu_1", name="search_evidence", input={"query": "unseen proteins", "top_k": 3}),
            block("tool_use", id="tu_2", name="find_research_gaps", input={"topic": "cold-start"}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[block("text", text=(
            f"# Report\n\n## Answer\nGraph models degrade on unseen proteins [{cid}]. "
            "A made-up citation [p_000000000000:c999] must be flagged.\n"))]),
    ])
    events = []
    result = Investigator(store, llm=fake).run("Do graph models generalize?", on_event=events.append)

    assert result.mode == "claude"
    assert [s["tool"] for s in result.steps] == ["search_evidence", "find_research_gaps"]
    assert result.gaps  # captured from the gap tool
    # Both tool results went back in ONE user message, matched to their tool_use ids
    tool_msg = fake.requests[1]["messages"][2]
    assert tool_msg["role"] == "user" and [c["tool_use_id"] for c in tool_msg["content"]] == ["tu_1", "tu_2"]
    assert json.loads(tool_msg["content"][0]["content"])["results"]
    # Tools were offered and effort was set
    assert {t["name"] for t in fake.requests[0]["tools"]} >= {"search_evidence", "explore_entity", "compare_claims"}
    assert fake.requests[0]["output_config"]["effort"]
    # Citations: real one numbered and referenced, fabricated one flagged
    assert "[1]" in result.report_markdown and "[unverified]" in result.report_markdown
    assert result.references[0]["chunk_id"] == cid
    assert any("p_000000000000:c999" in w for w in result.warnings)
    assert result.report_markdown.startswith("# Investigation: Do graph models generalize?")
    assert any(e["type"] == "thought" for e in events)


def test_claude_refusal_falls_back_to_offline(ingested, store):
    fake = FakeLLM([SimpleNamespace(stop_reason="refusal", content=[])])
    result = Investigator(store, llm=fake).run("Any question")
    assert result.mode == "offline" and result.references
    assert any("declined" in w for w in result.warnings)


def test_claude_extractor_drops_unverifiable_items(sample_pdfs):
    paper = parse_pdf(sample_pdfs[0])
    real = paper.chunks[0]
    quote = real.text.split(". ")[0] + "."
    payload = {
        "methods": [{"text": "Graph Attention Network", "chunk_id": real.id, "quote": quote}],
        "datasets": [{"text": "DAVIS", "chunk_id": "p_bogus:c000", "quote": quote}],          # bad chunk id
        "claims": [{"text": "Invented claim", "chunk_id": real.id, "quote": "This sentence is not in the paper."}],
        "findings": [], "limitations": [],
    }
    fake = FakeLLM([SimpleNamespace(stop_reason="end_turn", content=[block("text", text=json.dumps(payload))])])
    x = ClaudeExtractor(fake).extract(paper)
    assert [m.text for m in x.methods] == ["Graph Attention Network"]
    assert x.datasets == [] and x.claims == []
    assert fake.requests[0]["output_config"]["format"]["type"] == "json_schema"


def test_finalize_citations_groups_and_dedupes():
    reg = {"p_aaaaaaaaaaaa:c001": {"chunk_id": "p_aaaaaaaaaaaa:c001", "paper": "A", "page": 2, "quote": "q"}}
    md, refs, warnings = finalize_citations("x [p_aaaaaaaaaaaa:c001, p_aaaaaaaaaaaa:c001] y [p_aaaaaaaaaaaa:c001]", reg)
    assert md.startswith("x [1] y [1]") and len(refs) == 1 and not warnings

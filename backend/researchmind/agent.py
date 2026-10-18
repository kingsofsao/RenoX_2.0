"""The investigation agent.

LLM mode, by provider:
- ollama (and any provider exposing chat()): retrieval-first grounded investigation
  (researchmind/grounded.py) - evidence is gathered through the MCP tools, the model writes a
  report citing numbered sources and may request a limited number of extra searches.
- anthropic: Claude plans and calls the graph tools in a tool-use loop, then writes a cited report.
Citations are verified against the graph afterwards in both cases.

Offline mode: a fixed investigation plan over the same tools, producing an extractive, fully
cited report. Used only by the command-line tools and tests: the web API runs with
require_llm=True, so a missing or failing AI model fails the investigation instead of
silently replacing the AI answer with an extractive one.

Language: with `language` set (e.g. "de"), the model writes the report in that language while
keeping section headings, citation markers and "Hypothesis:" prefixes in English, because the
structured report is parsed from them (the web UI translates the headings).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Callable

import anthropic

from .accounts import LANGUAGES, NATIVE_NAMES
from .graph import GraphStore
from .grounded import GroundedInvestigation, NoRelevantEvidence
from .llm import LLMUnavailable, get_llm
from .mcp_bridge import MCPToolClient, MCPToolError
from .report import InvestigationResult, collect_evidence, finalize_citations
from .tools import MIN_RELEVANCE, TOOL_SPECS, ResearchTools, call_tool

log = logging.getLogger(__name__)

Event = dict
MAX_TOOL_RESULT_CHARS = 12000

SYSTEM_PROMPT = """You are ResearchMind, a scientific research investigator. You answer a research question about ONE paper by investigating that paper's FalkorDB knowledge graph, never from memory.

The graph links the paper to its methods, datasets, claims, findings and limitations, and every statement is tied to an evidence chunk (a page-level passage) with an id like p_1a2b3c4d5e6f:c003. The tools only return this paper's data.

How to investigate:
- Start with list_papers and get_paper, then gather evidence from several angles: search_evidence for passages, explore_entity to traverse from a method or dataset to the results and limitations connected to it, compare_claims to see how the paper's claims and findings relate to the question, and find_research_gaps for gaps the paper's limitations and future work leave open.
- Follow up on limitations and caveats rather than stopping at the first relevant passage.
- Stop investigating once additional tool calls stop changing your conclusions.

How to write the final report (Markdown):
- Sections: "## Answer" (direct answer in 2-4 sentences), "## Evidence" (the key results, grouped by theme), "## Methods, data and results", "## Limitations of the Evidence", "## Candidate Research Gaps" (each gap starts with "Hypothesis:": what is missing, why the evidence suggests it, and a concrete study that would close it), "## Not covered by the evidence", "## Confidence".
- Never compare with or refer to other papers: only this paper was provided.
- Cite every factual sentence with the evidence chunk id in square brackets, e.g. [p_1a2b3c4d5e6f:c003]. Cite only chunk ids that appeared in tool results. Several citations go in one bracket separated by commas.
- Present gaps as candidates supported by the ingested papers only, not as established facts. If the corpus cannot answer the question, say so plainly.
- Do not include a references list; it is generated automatically from your citations."""


class Investigator:
    """Runs one investigation over the graph.

    transport: "mcp" (default) sends every tool call through the ResearchMind MCP server in-process;
    "direct" calls the same ResearchTools methods without the protocol layer (AGENT_TOOL_TRANSPORT).
    time_budget_s: once exceeded, the agent stops calling tools and writes its report.
    """

    def __init__(self, store: GraphStore, llm=None, use_llm: bool = True, max_turns: int | None = None,
                 tools: ResearchTools | None = None, transport: str | None = None, time_budget_s: float | None = None,
                 paper_ids: list[str] | None = None, language: str | None = None, require_llm: bool = False):
        # paper_ids limits the investigation to those papers; None investigates the whole library.
        self.tools = tools or ResearchTools(store, paper_ids=paper_ids)
        self.language = language if language in LANGUAGES else "en"
        self.require_llm = require_llm  # True (web API): never fall back to the offline plan
        self.store = store
        self.llm = (llm or get_llm()) if use_llm else None
        self.max_turns = max_turns if max_turns is not None else int(os.getenv("AGENT_MAX_TURNS", "14"))
        self.effort = os.getenv("AGENT_EFFORT", "high")
        self.transport = (transport or os.getenv("AGENT_TOOL_TRANSPORT", "mcp")).lower()
        self.mcp = MCPToolClient(self.tools) if self.transport == "mcp" else None
        self.time_budget_s = time_budget_s
        self._deadline: float | None = None

    @property
    def mode(self) -> str:
        return "llm" if self.llm else "offline"

    @property
    def provider(self) -> str | None:
        return getattr(self.llm, "provider", "anthropic") if self.llm else None

    @property
    def scope(self) -> list[str] | None:
        """The papers this investigation is limited to; None means the whole library."""
        return getattr(self.tools, "scope", None)

    def scope_note(self) -> str:
        """Tells the model which papers it is analysing when the investigation is limited to selected papers."""
        if not self.scope:
            return ""
        papers = self.tools.list_papers()["papers"]
        titles = "; ".join(f"{p.get('title') or p['id']} ({p['id']})" for p in papers)
        return (f"\n\nScope: analyse ONLY the {len(papers)} selected paper(s): {titles}. The tools return evidence from "
                "these papers only. Do not refer to or speculate about other papers in the user's library.")

    @property
    def language_name(self) -> str:
        return f"{LANGUAGES[self.language]} ({NATIVE_NAMES[self.language]})"

    def language_rule(self) -> str:
        """System-prompt rule for the report language (small models follow the system prompt most reliably)."""
        if self.language == "en":
            return ""
        return (f"\n\nOUTPUT LANGUAGE: {self.language_name}. Write every sentence of the report in {LANGUAGES[self.language]}, "
                "even though the sources and these instructions are in English. Only the Markdown section headings, the "
                "citation markers and the word \"Hypothesis:\" stay exactly as given in English.")

    def language_note(self) -> str:
        """Final reminder in the user prompt, keeping the parts the report parser relies on in English."""
        if self.language == "en":
            return ""
        return (f"\n\nLanguage: write all report text in {self.language_name}. Keep the Markdown section headings "
                "exactly as specified in English, keep every citation marker exactly as given, and start hypotheses "
                f"with the English word \"Hypothesis:\". Answer in {LANGUAGES[self.language]} now.")

    def _fallback(self, question: str, result: InvestigationResult, on_event, warning: str, code: str = "unavailable") -> None:
        """The AI could not produce the report: fail (web API) or run the offline plan (CLI, tests)."""
        if self.require_llm:
            raise LLMUnavailable(warning, code)
        result.warnings.append(warning + " Showing the offline report instead.")
        on_event({"type": "status", "message": "AI unavailable - switching to the offline plan"})
        result.mode = "offline"
        self._run_offline(question, result, on_event)

    def _out_of_time(self) -> bool:
        return self._deadline is not None and time.monotonic() >= self._deadline

    def run(self, question: str, on_event: Callable[[Event], None] = lambda e: None,
            requirements: str | None = None) -> InvestigationResult:
        question = question.strip()
        if not question:
            raise ValueError("Question is empty.")
        self._deadline = time.monotonic() + self.time_budget_s if self.time_budget_s else None
        result = InvestigationResult(question=question, mode=self.mode, provider=self.provider,
                                     model=getattr(self.llm, "model", None), requirements=requirements or None)
        if self.require_llm and not self.llm:
            raise LLMUnavailable("No AI model is configured.", "not_configured")
        if not self.tools.list_papers()["papers"]:
            if self.scope:
                result.report_markdown = "# Investigation\n\nNone of the selected papers is in the library any more."
                result.warnings.append("The selected papers were not found.")
            else:
                result.report_markdown = "# Investigation\n\nNo papers have been ingested yet. Ingest PDFs first."
                result.warnings.append("Knowledge graph is empty.")
            return result
        if self.llm and hasattr(self.llm, "chat"):
            self._run_grounded(question, requirements, result, on_event)
        elif self.llm:
            try:
                self._run_claude(question, result, on_event)
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
                self._fallback(question, result, on_event, f"Claude credentials rejected ({e.__class__.__name__}).")
            except anthropic.APITimeoutError:
                self._fallback(question, result, on_event, "Claude did not answer in time.", "timeout")
            except anthropic.APIError as e:
                self._fallback(question, result, on_event, f"Claude API error ({e.__class__.__name__}).")
        else:
            self._run_offline(question, result, on_event)
        self._ensure_coverage(question, result, on_event)

        body, refs, warnings = finalize_citations(
            result.report_markdown, result.evidence,
            lookup=lambda ids: [row for i in range(0, len(ids), 20) for row in self.tools.get_evidence(ids[i:i + 20])["evidence"]])
        result.report_markdown, result.references = body, refs
        result.warnings += warnings
        on_event({"type": "done", "message": f"Report ready with {len(refs)} cited sources"})
        return result

    # ------------------------------------------------------------------ helpers
    def _call(self, name: str, args: dict, result: InvestigationResult, on_event, source: str = "agent") -> dict:
        on_event({"type": "tool_call", "tool": name, "args": args})
        try:
            if self.mcp is not None:
                output = self.mcp.call(name, args)
            else:
                output = call_tool(self.tools, name, args)
        except MCPToolError as e:
            log.warning("MCP tool %s failed: %s", name, e)
            output = {"error": f"{name} failed: {e}"}
        except TypeError as e:
            output = {"error": f"Invalid arguments for {name}: {e}"}
        except Exception as e:
            log.exception("Tool %s failed", name)
            output = {"error": f"{name} failed: {e}"}
        if not isinstance(output, dict):
            output = {"error": f"{name} returned an unexpected result"}
        result.raw.append({"tool": name, "args": args, "output": output})
        collect_evidence(output, result.evidence)
        if name == "find_research_gaps" and "error" not in output:
            result.gaps = output.get("gaps", result.gaps)
        summary = _summarize(name, output)
        result.steps.append({"tool": name, "args": args, "summary": summary, "source": source, "ok": "error" not in output})
        on_event({"type": "tool_result", "tool": name, "summary": summary})
        return output

    # ------------------------------------------------------------------ grounded (Ollama) path
    def _run_grounded(self, question: str, requirements: str | None, result: InvestigationResult, on_event) -> None:
        name = f"{self.provider} / {getattr(self.llm, 'model', '')}"
        try:
            GroundedInvestigation(self, requirements).run(question, result, on_event)
        except NoRelevantEvidence:
            on_event({"type": "status", "message": "No stored evidence is relevant - the model was not asked"})
            result.warnings.append("No ingested paper contains evidence relevant to this question, so the LLM was not asked.")
            result.mode = "offline"
            result.report_markdown = _no_evidence_report(question, self.tools.list_papers()["papers"])
        except LLMUnavailable as e:
            log.warning("LLM %s unavailable (%s): %s", name, e.code, e)
            self._fallback(question, result, on_event, f"LLM {name} unavailable ({e.code}: {e}).", e.code)

    # ------------------------------------------------------------------ Claude loop
    def _run_claude(self, question: str, result: InvestigationResult, on_event) -> None:
        messages: list[dict] = [{"role": "user",
                                 "content": f"Research question: {question}{self.scope_note()}{self.language_note()}"}]
        tool_specs = [t for t in TOOL_SPECS if t["name"] != "graph_query"] if self.scope else TOOL_SPECS
        on_event({"type": "status", "message": "Claude is planning the investigation"})
        final_text = ""
        for turn in range(self.max_turns + 1):
            last_turn = turn == self.max_turns or self._out_of_time()
            if last_turn:
                if turn < self.max_turns:
                    result.warnings.append("The investigation time budget was reached; the report uses the evidence gathered so far.")
                    on_event({"type": "status", "message": "Time budget reached - writing the report"})
                messages.append({"role": "user", "content": "Tool budget reached. Write the final report now using the evidence gathered."})
            with_tools = {"tools": tool_specs} if not last_turn else {"tools": tool_specs, "tool_choice": {"type": "none"}}
            response = self.llm.create(
                max_tokens=16000, system=SYSTEM_PROMPT + self.language_rule(), messages=messages,
                output_config={"effort": self.effort}, **with_tools)

            if response.stop_reason == "refusal":
                self._fallback(question, result, on_event, "Claude declined this request.", "refusal")
                return
            messages.append({"role": "assistant", "content": response.content})
            texts = [b.text for b in response.content if b.type == "text" and b.text.strip()]

            if response.stop_reason == "pause_turn":
                continue
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason == "tool_use" and tool_uses:
                for t in texts:
                    on_event({"type": "thought", "message": t})
                results = []
                for block in tool_uses:
                    args = block.input if isinstance(block.input, dict) else {}
                    output = self._call(block.name, args, result, on_event)
                    payload = json.dumps(output, default=str)
                    if len(payload) > MAX_TOOL_RESULT_CHARS:
                        payload = payload[:MAX_TOOL_RESULT_CHARS] + "... [truncated; narrow the query for more]"
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": payload,
                                    **({"is_error": True} if isinstance(output, dict) and "error" in output else {})})
                messages.append({"role": "user", "content": results})
                continue

            final_text = "\n\n".join(texts)
            if response.stop_reason == "max_tokens":
                result.warnings.append("The report hit the output token limit and may be truncated.")
            break

        if not final_text.strip():
            self._fallback(question, result, on_event, "Claude returned no report text.", "malformed")
            return
        on_event({"type": "status", "message": "Verifying citations"})
        result.report_markdown = f"# Investigation: {question}\n\n" + _strip_title(final_text)

    # ------------------------------------------------------------------ coverage
    def _ensure_coverage(self, question: str, result: InvestigationResult, on_event) -> None:
        """Guarantee the evidence base behind the structured report, whichever path the agent took.

        Claude picks its own tools; if it skipped evidence search, claim comparison, gap finding or
        paper records, each is run once here so findings, comparisons, gaps and limitations always
        come from graph evidence rather than from the narrative alone."""
        called = {r["tool"] for r in result.raw if "error" not in r["output"]}
        if "search_evidence" not in called:
            self._call("search_evidence", {"query": question, "top_k": 8}, result, on_event, source="coverage")
        if "compare_claims" not in called:
            self._call("compare_claims", {"topic": question, "top_k": 10}, result, on_event, source="coverage")
        if "find_research_gaps" not in called:
            self._call("find_research_gaps", {"topic": question, "max_gaps": 6}, result, on_event, source="coverage")
        if "get_paper" not in called:
            hits = next((r["output"].get("results", []) for r in result.raw
                         if r["tool"] == "search_evidence" and "error" not in r["output"]), [])
            relevant = [h for h in hits if (h.get("score") or 0) >= MIN_RELEVANCE and h.get("paper_id")]
            for pid in list(dict.fromkeys(h["paper_id"] for h in relevant))[:3]:
                self._call("get_paper", {"paper_id": pid}, result, on_event, source="coverage")

    # ------------------------------------------------------------------ offline plan
    def _run_offline(self, question: str, result: InvestigationResult, on_event) -> None:
        on_event({"type": "status", "message": "Running offline investigation plan (no LLM configured)"})
        papers = self._call("list_papers", {}, result, on_event).get("papers", [])
        evidence = self._call("search_evidence", {"query": question, "top_k": 8}, result, on_event).get("results", [])
        comparison = self._call("compare_claims", {"topic": question, "top_k": 10}, result, on_event)
        if "error" in comparison:
            comparison = {}
        evidence, comparison = _relevant_only(evidence, comparison)
        if not evidence and not comparison.get("statements_by_paper"):
            on_event({"type": "status", "message": "No stored evidence is relevant to this question"})
            result.report_markdown = _no_evidence_report(question, papers)
            return

        # Traverse from entities named in the question or the top evidence
        if self.scope:  # graph_query is whole-library; list only the entities of the selected papers
            entity_rows = self.store.query(
                """MATCH (p:Paper)-[:USES_METHOD|USES_DATASET]->(e) WHERE p.id IN $scope
                   RETURN DISTINCT e.name AS name, labels(e)[0] AS label""", {"scope": self.scope}, read_only=True)
        else:
            entity_rows = self._call("graph_query", {"cypher": "MATCH (e) WHERE e:Method OR e:Dataset RETURN e.name AS name, labels(e)[0] AS label"},
                                     result, on_event).get("rows", [])
        named = [r["name"] for r in entity_rows if _mentions(r["name"], question)]
        if not named:
            top_text = " ".join(e["text"] for e in evidence[:3])
            named = [r["name"] for r in entity_rows if r["label"] == "Method" and _mentions(r["name"], top_text)]
        explored = [x for x in (self._call("explore_entity", {"name": n}, result, on_event) for n in named[:2]) if "error" not in x]

        top_papers = list(dict.fromkeys(e["paper_id"] for e in evidence))[:3]
        details = [d for d in (self._call("get_paper", {"paper_id": pid}, result, on_event) for pid in top_papers) if "error" not in d]
        gaps = self._call("find_research_gaps", {"topic": question, "max_gaps": 6}, result, on_event).get("gaps", [])
        on_event({"type": "status", "message": "Assembling extractive report"})
        result.report_markdown = _offline_report(question, papers, evidence, comparison, explored, details, gaps)


# ---------------------------------------------------------------------- formatting helpers

_STOP = {"of", "for", "the", "and", "a", "an", "on", "in", "with", "to", "model", "models", "network", "networks"}


def _mentions(entity: str, text: str) -> bool:
    """True if `text` names the entity: full name, its acronym (GAT), or all its distinctive words."""
    name, low = entity.lower(), text.lower()
    if re.search(rf"\b{re.escape(name)}\b", low):
        return True
    words = re.findall(r"[a-z0-9]+", name)
    acronym = "".join(w[0] for w in words)
    tokens = set(re.findall(r"[a-z0-9]+", low))
    if len(words) >= 2 and len(acronym) >= 2 and acronym in tokens:
        return True
    distinctive = [w for w in words if w not in _STOP]
    return len(distinctive) >= 2 and all(w in tokens for w in distinctive)


def _strip_title(text: str) -> str:
    return re.sub(r"^\s*#\s+[^\n]*\n+", "", text, count=1)


def _summarize(name: str, output: dict) -> str:
    if not isinstance(output, dict):
        return "done"
    if "error" in output:
        return f"error: {output['error']}"
    if name == "list_papers":
        return f"{output.get('count', 0)} papers in the graph"
    if name == "search_evidence":
        res = output.get("results", [])
        return f"{len(res)} passages from {len({r['paper_id'] for r in res})} papers"
    if name == "compare_claims":
        n = sum(len(v) for v in output.get("statements_by_paper", {}).values())
        return f"{n} statements across {len(output.get('statements_by_paper', {}))} papers, {len(output.get('contradictions', []))} contradictions"
    if name == "find_research_gaps":
        return f"{len(output.get('gaps', []))} candidate gaps"
    if name == "explore_entity":
        return "; ".join(f"{m['type']} '{m['entity']}' used by {len(m['papers'])} papers" for m in output.get("matches", []))
    if name == "get_paper":
        return f"'{output.get('title', '')}': {len(output.get('findings', []))} findings, {len(output.get('limitations', []))} limitations"
    if name == "find_related_papers":
        return f"{len(output.get('shared_entities', []))} papers share entities, {len(output.get('statement_links', []))} statement links"
    if name == "graph_query":
        return f"{len(output.get('rows', []))} rows"
    if name == "get_evidence":
        return f"{len(output.get('evidence', []))} passages"
    return "done"


def _cite(chunk_id: str) -> str:
    return f"[{chunk_id}]"


def _relevant_only(evidence: list[dict], comparison: dict) -> tuple[list[dict], dict]:
    """Drop passages and statements below the relevance threshold, and relations not touching the rest."""
    evidence = [e for e in evidence if (e.get("score") or 0) >= MIN_RELEVANCE]
    by_paper = {}
    for title, stmts in comparison.get("statements_by_paper", {}).items():
        kept = [x for x in stmts if (x.get("relevance") or 0) >= MIN_RELEVANCE]
        if kept:
            by_paper[title] = kept
    texts = {x["text"] for stmts in by_paper.values() for x in stmts}
    touches = lambda r: r.get("statement_a") in texts or r.get("statement_b") in texts  # noqa: E731
    return evidence, {**comparison, "statements_by_paper": by_paper,
                      "contradictions": [r for r in comparison.get("contradictions", []) if touches(r)],
                      "related_statements": [r for r in comparison.get("related_statements", []) if touches(r)]}


def _no_evidence_report(question: str, papers: list) -> str:
    return "\n".join([
        f"# Investigation: {question}", "",
        "## Answer", "",
        ("This paper does not" if len(papers) == 1 else f"The {len(papers)} papers do not")
        + f" contain evidence relevant to this question: no passage or extracted statement reached the relevance "
        f"threshold ({MIN_RELEVANCE}). ResearchMind answers only from the paper itself, so the AI model was not asked "
        "to guess.", "",
        "## Confidence", "",
        "Low: there is no supporting evidence in this paper. Rephrase the question or analyse a paper on this topic.", ""])


def _offline_report(question, papers, evidence, comparison, explored, details, gaps) -> str:
    lines = [f"# Investigation: {question}", "",
             "> Generated in **offline mode** (no LLM configured): an extractive synthesis of graph evidence. "
             "Add `ANTHROPIC_API_KEY` to `.env` for Claude-driven investigation and narrative reports.", ""]

    lines += ["## Answer", ""]
    by_paper = comparison.get("statements_by_paper", {})
    key = sorted((s for stmts in by_paper.values() for s in stmts), key=lambda s: -s["relevance"])[:4]
    if key:
        lines.append(f"The {len(papers)} ingested papers contain {sum(len(v) for v in by_paper.values())} claims/findings relevant to this question. The most relevant:")
        lines.append("")
        for s in key:
            lines.append(f"- {s['text']} {_cite(s['chunk_id'])} (*{s['paper_title']}*)")
    else:
        lines.append("The ingested papers contain little direct evidence on this question.")
    lines.append("")

    lines += ["## Evidence", ""]
    for paper_title, stmts in by_paper.items():
        lines.append(f"**{paper_title}**")
        for s in stmts[:4]:
            lines.append(f"- ({s['type']}) {s['text']} {_cite(s['chunk_id'])}")
        lines.append("")
    if evidence:
        lines.append("Most relevant passages:")
        lines.append("")
        for e in evidence[:4]:
            snippet = e["text"][:260] + ("…" if len(e["text"]) > 260 else "")
            lines.append(f"- *{e['paper_title']}*, p. {e['page']} ({e['section']}): \"{snippet}\" {_cite(e['chunk_id'])}")
        lines.append("")

    for ex in explored:
        for m in ex.get("matches", []):
            lines.append(f"**Graph traversal, {m['type']}: {m['entity']}** (used by {len(m['papers'])} papers)")
            for p in m["papers"]:
                companions = p.get("datasets") or p.get("methods") or []
                extra = f"; also uses {', '.join(companions)}" if companions else ""
                lines.append(f"- *{p['title']}*{extra} {_cite(p['chunk_id'])}")
            lines.append("")

    lines += ["## Agreements and Conflicts", ""]
    contradictions, related = comparison.get("contradictions", []), comparison.get("related_statements", [])
    if not contradictions and not related:
        lines.append("No cross-paper contradictions or closely related statements were detected for this topic.")
    for c in contradictions[:4]:
        lines.append(f"- **Conflict** ({c['score']:.2f}): *{c['paper_a']}* states \"{c['statement_a']}\" {_cite(c['chunk_a'])}, "
                     f"while *{c['paper_b']}* states \"{c['statement_b']}\" {_cite(c['chunk_b'])}.")
    for a in related[:3]:
        lines.append(f"- **Closely related** ({a['score']:.2f}): \"{a['statement_a']}\" {_cite(a['chunk_a'])} ~ \"{a['statement_b']}\" {_cite(a['chunk_b'])}")
    lines.append("")

    lines += ["## Limitations of the Evidence", ""]
    any_lim = False
    for d in details:
        for l in d.get("limitations", [])[:3]:
            any_lim = True
            tag = "future work" if l.get("kind") == "future_work" else "limitation"
            lines.append(f"- *{d['title']}* ({tag}): {l['text']} {_cite(l['chunk_id'])}")
    if not any_lim:
        lines.append("- No limitations were extracted for the most relevant papers.")
    lines.append(f"- Conclusions are limited to the {len(papers)} ingested papers.")
    lines.append("")

    lines += ["## Candidate Research Gaps", "",
              "_Hypotheses derived from the ingested papers only. Verify them against the wider literature._", ""]
    if not gaps:
        lines.append("No candidate gaps were found.")
    for g in gaps:
        cites = ", ".join(dict.fromkeys(e["chunk_id"] for e in g["evidence"] if e.get("chunk_id")))
        lines.append(f"**{g['id']}. {g['title']}** (`{g['type'].replace('_', ' ')}`), score {g['score']}")
        lines.append(f"- Why: {g['rationale']} [{cites}]")
        lines.append("")

    lines += ["## Confidence", "",
              "Moderate at best: offline mode ranks evidence by semantic similarity and graph structure but does not reason over it. "
              "Treat the synthesis as a structured evidence brief.", ""]
    return "\n".join(lines)

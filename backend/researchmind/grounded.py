"""Evidence-grounded LLM investigation (used for Ollama and any provider exposing `chat()`).

Small local models are unreliable at long autonomous tool loops and at copying ids like
p_1a2b3c4d5e6f:c003, so this path is retrieval-first:

1. Evidence is gathered through the MCP tools (search, claim comparison, paper records, gaps)
   and filtered by relevance to the question.
2. The model receives the question, the user's own requirements (labelled [R]) and a numbered
   pack of source passages [S1]..[Sn], each with paper title and page. Conflicts and candidate
   gaps detected in the graph are given as hints that reference those sources.
3. The model may request more evidence with a `search_evidence` tool, a limited number of times.
4. Its citations [S#] are mapped back to evidence chunk ids and verified against the graph
   (report.finalize_citations). Unknown source numbers and quotes that do not appear in any
   source are flagged; output without any valid citation is rejected.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from .config import get_settings
from .llm import LLMUnavailable
from .report import InvestigationResult
from .tools import MIN_RELEVANCE

log = logging.getLogger(__name__)

SOURCE_CHARS = 420           # per-source excerpt length in the prompt
MAX_SOURCES = 16

SYSTEM = """You are ResearchMind, a careful research analyst. You answer ONLY from the numbered sources provided, which are excerpts of ONE paper the user uploaded. You never use outside knowledge about this paper, other papers, products or systems, and you never compare it with papers that were not provided.

Rules:
1. End every factual sentence about the papers with its source number(s) in square brackets, e.g. [S2] or [S1, S4]. Only use source numbers that appear in the list.
2. The user's own project requirements are labelled [R]. They are NOT published findings; cite them as [R] and call them "requirements".
3. Hypotheses or suggestions you derive must start with "Hypothesis:" and cite the sources that motivate them.
4. Never invent paper titles, page numbers, numbers, quotations, features or results. If the sources do not state something, write "The sources do not report ..." instead of guessing.
5. Ignore sources that are not relevant to the question.
6. Quote only text that appears word-for-word in a source.
7. Sources are grouped by paper. A fact from one paper describes ONLY the system or study in that paper. Never attribute a feature, component or result of one paper's system to another paper's system. When you name a system (for example a product or project name), cite a source from the paper that describes that system.
8. If the sources are not enough, call the search_evidence tool with a short query (at most {rounds} times), or say clearly what is missing.
9. Be concise: at most 350 words in total, no repeated points."""

FORMAT = """Write the report in Markdown with exactly these sections:
## Answer
(2-4 sentences that directly answer the question, with citations)
## Evidence from the paper
(a short bullet list of the facts from the paper that answer the question, with citations)
## Methods, data and results
(the methods, datasets and results the paper reports that matter for the question{req_hint}, with citations)
## Conflicts and uncertainty
(caveats, inconsistencies or uncertain results within the paper, or "No conflicts found in the sources.")
## Candidate research gaps
(each line starts with "Hypothesis:" and cites supporting sources; only gaps the sources support)
## Not covered by the evidence
(what the question asks that the sources do not answer)
## Confidence
(low / moderate / high, and why)"""

SEARCH_TOOL = [{
    "type": "function",
    "function": {
        "name": "search_evidence",
        "description": "Search the ingested papers for more evidence passages. Use only if the provided sources are insufficient.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Short search query"}},
                       "required": ["query"]},
    },
}]

SID = re.compile(r"\[\s*((?:S\d+|R)(?:\s*[,;]\s*(?:S\d+|R))*)\s*\]")
QUOTE = re.compile(r"[\"“]([^\"”]{25,300})[\"”]")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


@dataclass
class EvidencePack:
    sources: list[dict] = field(default_factory=list)
    _seen: set = field(default_factory=set)

    def add(self, chunk_id: str | None, paper_title: str | None, page, kind: str, text: str | None) -> str | None:
        if not chunk_id or not text or len(self.sources) >= MAX_SOURCES:
            return None
        key = (chunk_id, _norm(text)[:80])
        for s in self.sources:
            if (s["chunk_id"], _norm(s["text"])[:80]) == key:
                return s["sid"]
        if key in self._seen:
            return None
        self._seen.add(key)
        sid = f"S{len(self.sources) + 1}"
        self.sources.append({"sid": sid, "chunk_id": chunk_id, "paper_title": paper_title or "Untitled paper",
                             "page": page, "kind": kind, "text": re.sub(r"\s+", " ", text).strip()})
        return sid

    def sid_for(self, chunk_id: str) -> str | None:
        return next((s["sid"] for s in self.sources if s["chunk_id"] == chunk_id), None)

    def render(self, max_chars: int) -> str:
        """Sources grouped under one header per paper, so facts stay attached to their paper."""
        groups: dict[str, list[dict]] = {}
        for s in self.sources:
            groups.setdefault(s["paper_title"], []).append(s)
        lines, used = [], 0
        for n, (title, items) in enumerate(groups.items()):
            header = f'PAPER {chr(65 + n)}: "{title}" (the sources below describe only this paper)'
            lines.append(header)
            used += len(header)
            for s in items:
                excerpt = s["text"][:SOURCE_CHARS] + ("…" if len(s["text"]) > SOURCE_CHARS else "")
                line = f"  [{s['sid']}] page {s['page']} ({s['kind']}): {excerpt}"
                if used + len(line) > max_chars:
                    return "\n".join(lines)
                lines.append(line)
                used += len(line)
        return "\n".join(lines)

    def by_sid(self) -> dict[str, dict]:
        return {s["sid"]: s for s in self.sources}


class GroundedInvestigation:
    """Runs one grounded investigation using an Investigator's MCP tool calls and a chat() LLM."""

    def __init__(self, investigator, requirements: str | None = None):
        self.inv = investigator
        self.llm = investigator.llm
        self.requirements = (requirements or "").strip() or None
        s = get_settings()
        self.max_rounds = max(0, s.llm_max_tool_rounds)
        self.max_chars = s.llm_max_context_chars

    # ------------------------------------------------------------------ retrieval
    def gather(self, question: str, result: InvestigationResult, on_event) -> tuple[EvidencePack, list[str], list[str]]:
        call = lambda name, args: self.inv._call(name, args, result, on_event)  # noqa: E731
        pack = EvidencePack()
        call("list_papers", {})
        hits = call("search_evidence", {"query": question, "top_k": 8}).get("results", [])
        if self.requirements:
            hits += call("search_evidence", {"query": self.requirements[:300], "top_k": 6}).get("results", [])
        compare = call("compare_claims", {"topic": question, "top_k": 10})
        statements = [s for v in compare.get("statements_by_paper", {}).values() for s in v
                      if (s.get("relevance") or 0) >= MIN_RELEVANCE]
        single = self.inv.scope[0] if self.inv.scope and len(self.inv.scope) == 1 else None
        if single:  # defence in depth: the tools are already scoped, but nothing of another paper may reach the model
            hits = [h for h in hits if h.get("paper_id") == single]
            statements = [s for s in statements if s.get("paper_id") == single]
        relevant_hits = sorted((h for h in hits if (h.get("score") or 0) >= MIN_RELEVANCE), key=lambda h: -h["score"])

        # Statements first (precise), then passages (context).
        for s in sorted(statements, key=lambda s: -s["relevance"]):
            pack.add(s["chunk_id"], s["paper_title"], s["page"], s["type"].lower(), s["text"])
        for h in relevant_hits:
            pack.add(h["chunk_id"], h["paper_title"], h["page"], f"passage, {h.get('section') or 'text'}", h["text"])

        relevant_papers = list(dict.fromkeys([s["paper_id"] for s in statements] + [h["paper_id"] for h in relevant_hits]))
        if single:
            # The user chose this one paper, so its content is in scope by definition: broad questions
            # ("what are the limitations?") match no single passage closely, yet the paper answers them.
            relevant_papers = [single]
            if not relevant_hits:
                for h in sorted(hits, key=lambda h: -(h.get("score") or 0))[:5]:
                    pack.add(h["chunk_id"], h["paper_title"], h["page"], f"passage, {h.get('section') or 'text'}", h["text"])
        for pid in relevant_papers[:3]:
            paper = call("get_paper", {"paper_id": pid})
            for lim in paper.get("limitations", [])[:6 if single else 3]:
                pack.add(lim["chunk_id"], paper.get("title"), lim["page"],
                         "future work" if lim.get("kind") == "future_work" else "limitation", lim["text"])
            if single:  # the paper's own claims and findings, so the model always sees what the paper reports
                for key, kind in (("findings", "finding"), ("claims", "claim")):
                    for st in paper.get(key, [])[:4]:
                        pack.add(st["chunk_id"], paper.get("title"), st["page"], kind, st["text"])

        conflicts = []
        for c in compare.get("contradictions", []):
            a, b = pack.sid_for(c["chunk_a"]), pack.sid_for(c["chunk_b"])
            if a and b:
                conflicts.append(f"- {a} and {b} report opposing results (similarity {c['score']:.2f}).")

        gap_hints = []
        # A gap normally needs two papers behind it; an investigation of one selected paper uses that paper's own.
        min_gap_papers = 1 if self.inv.scope and len(self.inv.scope) == 1 else 2
        if relevant_papers:
            gaps = call("find_research_gaps", {"topic": question, "max_gaps": 6}).get("gaps", [])
            for g in gaps:
                ev = [e for e in g.get("evidence", []) if (e.get("chunk_id") or "").split(":")[0] in relevant_papers]
                # Only concrete gaps backed by enough relevant papers are offered to the model.
                if g.get("specific") is False or len({(e.get("chunk_id") or "").split(":")[0] for e in ev}) < min_gap_papers:
                    continue
                sids = [pack.add(e["chunk_id"], e.get("paper"), e.get("page"), "gap evidence", e.get("quote")) for e in ev]
                sids = [x for x in dict.fromkeys(sids) if x]
                if sids:
                    gap_hints.append(f"- {g['title'][:160]} ({g['type'].replace('_', ' ')}; sources {', '.join(sids)})")
        return pack, conflicts, gap_hints

    # ------------------------------------------------------------------ prompting
    def _prompt(self, question: str, pack: EvidencePack, conflicts: list[str], gap_hints: list[str]) -> str:
        parts = [f"RESEARCH QUESTION:\n{question}{self.inv.scope_note()}"]
        if self.requirements:
            parts.append(f"USER-PROVIDED PROJECT REQUIREMENTS [R] (not from the papers):\n{self.requirements[:1500]}")
        parts.append("SOURCES (excerpts from the ingested papers):\n" + pack.render(self.max_chars))
        parts.append("CONFLICTS DETECTED IN THE KNOWLEDGE GRAPH:\n" + ("\n".join(conflicts) if conflicts else "- none"))
        parts.append("CANDIDATE GAPS DETECTED IN THE KNOWLEDGE GRAPH (verify against the sources before using):\n"
                     + ("\n".join(gap_hints) if gap_hints else "- none"))
        req_hint = " and how they relate to the user's requirements [R]" if self.requirements else ""
        parts.append(FORMAT.format(req_hint=req_hint) + self.inv.language_note())
        return "\n\n".join(parts)

    def run(self, question: str, result: InvestigationResult, on_event) -> None:
        on_event({"type": "status", "message": "Retrieving evidence through the MCP tools"})
        pack, conflicts, gap_hints = self.gather(question, result, on_event)
        if not pack.sources:
            raise NoRelevantEvidence()

        messages = [{"role": "system", "content": SYSTEM.format(rounds=self.max_rounds) + self.inv.language_rule()},
                    {"role": "user", "content": self._prompt(question, pack, conflicts, gap_hints)}]
        model = getattr(self.llm, "model", "model")
        text, rounds = "", 0
        while True:
            if self.inv._out_of_time():
                raise LLMUnavailable("The investigation time budget ran out before the model finished.", "timeout")
            tools = SEARCH_TOOL if rounds < self.max_rounds else None
            on_event({"type": "status", "message": f"{model} is reading {len(pack.sources)} sources and writing"
                                                   + (" (may request more evidence)" if tools else "")})
            t0 = time.monotonic()
            reply = self.llm.chat(messages, tools=tools,
                                  on_progress=lambda n: on_event({"type": "status", "message": f"{model} generating… {n} tokens"}))
            on_event({"type": "status", "message": f"{model} answered in {time.monotonic() - t0:.0f} s ({reply.eval_tokens} tokens)"})
            if reply.tool_calls and tools:
                rounds += 1
                messages.append({"role": "assistant", "content": reply.text or "", "tool_calls": [
                    {"function": {"name": c["name"], "arguments": c["arguments"]}} for c in reply.tool_calls]})
                for c in reply.tool_calls[:2]:
                    messages.append({"role": "tool", "content": self._more_evidence(c, pack, result, on_event)})
                continue
            text = reply.text
            if reply.done_reason == "length":
                result.warnings.append("The model reached the output length limit (LLM_MAX_OUTPUT_TOKENS); the report may be cut off.")
            break

        result.report_markdown = self.postprocess(question, text, pack, result)

    def _more_evidence(self, call: dict, pack: EvidencePack, result: InvestigationResult, on_event) -> str:
        query = str((call.get("arguments") or {}).get("query") or "").strip()[:200]
        if call.get("name") != "search_evidence" or not query:
            return "Unknown tool or empty query. Only search_evidence(query) is available."
        hits = self.inv._call("search_evidence", {"query": query, "top_k": 5}, result, on_event, source="llm").get("results", [])
        added = []
        for h in hits:
            if (h.get("score") or 0) >= MIN_RELEVANCE:
                sid = pack.add(h["chunk_id"], h["paper_title"], h["page"], f"passage, {h.get('section') or 'text'}", h["text"])
                if sid:
                    added.append(next(s for s in pack.sources if s["sid"] == sid))
        if not added:
            return f"No additional relevant evidence found for '{query}'. Answer with the existing sources and state what is missing."
        return "NEW SOURCES:\n" + "\n".join(
            f"[{s['sid']}] {s['paper_title']}, page {s['page']} ({s['kind']}): {s['text'][:SOURCE_CHARS]}" for s in added)

    # ------------------------------------------------------------------ verification
    def _check_attribution(self, text: str, sources: dict, question: str, result: InvestigationResult) -> str:
        """Mark statements about a named system that their citations do not support."""
        problems = _attribution_problems(text, sources, _system_names(question, self.requirements or ""))
        for sentence, problem in problems:
            marker = "[uncited claim]" if problem == "no citation" else "[attribution not supported]"
            text = text.replace(sentence, f"{sentence.rstrip()} {marker}", 1)
        if problems:
            kinds = "; ".join(sorted({p for _, p in problems}))
            result.warnings.append(f"{len(problems)} statement(s) about named systems are not supported by their "
                                   f"citations ({kinds}) and are marked in the report.")
        return text

    def postprocess(self, question: str, text: str, pack: EvidencePack, result: InvestigationResult) -> str:
        text = (text or "").strip()
        if len(text) < 40:
            raise LLMUnavailable("The model returned an empty or unusable answer.", "malformed")
        sources = pack.by_sid()
        valid, unknown = 0, set()

        def repl(m):
            nonlocal valid
            ids = []
            for token in re.split(r"\s*[,;]\s*", m.group(1)):
                if token == "R":
                    ids.append("R")
                elif token in sources:
                    ids.append(sources[token]["chunk_id"])
                    valid += 1
                else:
                    unknown.add(token)
                    ids.append("unverified")
            chunks = [i for i in ids if i not in ("R", "unverified")]
            out = f"[{', '.join(dict.fromkeys(chunks))}]" if chunks else ""
            if "R" in ids:
                out += " [R]"
            if "unverified" in ids:
                out += " [unverified]"
            return out.strip()

        text = self._check_attribution(_strip_heading(text), sources, question, result)
        body = SID.sub(repl, text)
        # Plain mentions like "S3" outside brackets are tolerated but not counted as citations.
        if valid == 0:
            raise LLMUnavailable("The model's answer contained no citations to the provided sources.", "malformed")
        if unknown:
            result.warnings.append(f"The model cited source numbers that do not exist ({', '.join(sorted(unknown))}); "
                                   "they are marked [unverified].")
        corpus = " ".join(_norm(s["text"]) for s in pack.sources)
        if self.requirements:
            corpus += " " + _norm(self.requirements)
        bad_quotes = [q for q in QUOTE.findall(body) if _norm(q) and _norm(q) not in corpus]
        for q in bad_quotes:
            body = body.replace(q, q + " [quote not found in sources]")
        if bad_quotes:
            result.warnings.append(f"{len(bad_quotes)} quotation(s) in the model's answer do not appear in the sources "
                                   "and are marked [quote not found in sources].")
        legend = (f"> LLM report generated by **{self.llm.provider} / {getattr(self.llm, 'model', '')}** from "
                  f"{len(pack.sources)} retrieved sources. Numbers in brackets cite stored evidence"
                  + ("; [R] marks your own requirements, not published findings." if self.requirements else ".")
                  + " Statements marked Hypothesis are generated, not published.")
        return f"# Investigation: {question}\n\n{legend}\n\n{body}\n"


# Distinctive system names: all caps (TAGSY) or with an inner capital (KidBrace).
NAME = re.compile(r"\b([A-Z]{4,}|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*)\b")
NAME_STOP = {"WIFI", "ESP32", "HTTP", "JSON", "WITH", "FROM", "THIS", "THAT", "SPO2"}
CHECKED_SECTIONS = ("answer", "evidence", "comparison")


def _system_names(*texts: str) -> set[str]:
    """Names from the question/requirements whose attribution is checked, e.g. {"TAGSY", "KidBrace"}."""
    return {m for t in texts for m in NAME.findall(t or "") if m.upper() not in NAME_STOP}


def _attribution_problems(text: str, sources: dict, names: set[str]) -> list[tuple[str, str]]:
    """(sentence, problem) for statements in Answer/Evidence/Comparison that name a system but either cite
    nothing, or cite only sources that never mention that system (i.e. facts borrowed from another paper)."""
    problems, section = [], ""
    # A paper "mentions" a name if its title or any of its retrieved passages does.
    paper_text: dict[str, str] = {}
    for src in sources.values():
        paper_text[src["paper_title"]] = paper_text.get(src["paper_title"], src["paper_title"]) + " " + src["text"]
    for line in text.splitlines():
        heading = re.match(r"^#{2,4}\s+(.*)", line)
        if heading:
            section = heading.group(1).strip().lower()
            continue
        if not names or not section.startswith(CHECKED_SECTIONS):
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            named = [n for n in names if re.search(rf"\b{re.escape(n)}\b", sentence, re.I)]
            if not named and len(names) > 1 and re.search(r"\b(both|each|all)\s+(systems?|devices?|papers?|projects?|products?)\b", sentence, re.I):
                named = sorted(names)  # "Both systems ..." makes a claim about every named system
            if not named:
                continue
            cited = [sources[t] for m in SID.finditer(sentence) for t in re.split(r"\s*[,;]\s*", m.group(1)) if t in sources]
            if not cited:
                if "[R]" not in sentence and not sentence.lstrip("-* ").lower().startswith("hypothesis"):
                    problems.append((sentence, "no citation"))
                continue
            for n in named:
                if not any(re.search(rf"\b{re.escape(n)}\b", paper_text[c["paper_title"]], re.I) for c in cited):
                    problems.append((sentence, f"cited sources do not mention {n}"))
                    break
    return problems


class NoRelevantEvidence(Exception):
    """Nothing in the corpus is relevant to the question, so the model is not asked."""


def _strip_heading(text: str) -> str:
    return re.sub(r"^\s*#\s+[^\n]*\n+", "", text, count=1)

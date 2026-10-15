"""Structured investigation output for the API and UI.

The agent's Markdown report is the narrative. This module turns the raw tool outputs the agent
gathered into structured sections - findings, cross-paper comparisons, limitations, candidate gaps -
where every item points to numbered sources. Every source is re-checked against the graph
(`lookup`), and items whose evidence cannot be verified are dropped rather than shown.

Confidence is computed from evidence signals (corpus coverage, verified sources, conflicts, mode),
not asserted by the model.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

from .report import CHUNK_ID, InvestigationResult
from .tools import MIN_RELEVANCE

Lookup = Callable[[list[str]], list[dict]]

MAX_FINDINGS = 12
MAX_COMPARISONS = 10
MAX_LIMITATIONS = 10
NO_EVIDENCE = ("The ingested papers do not contain evidence relevant to this question (no passage or statement "
               "reached the relevance threshold). Upload papers on this topic or rephrase the question.")
MIN_GAP_PAPERS = 2
GAP_NOTE = ("Candidate gap derived only from the ingested papers. It is a hypothesis to check against the "
            "wider literature, not a confirmed novel research direction.")


def paper_id_of(chunk_id: str) -> str:
    return chunk_id.split(":", 1)[0]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def section(markdown: str, heading: str) -> str:
    """Body of a '## heading' section (up to the next '## '), or ''."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)", markdown or "", re.M | re.S)
    return m.group(1).strip() if m else ""


class Sources:
    """Numbered, graph-verified evidence sources shared by the report and the structured sections."""

    def __init__(self, result: InvestigationResult, lookup: Lookup | None):
        self.by_id: dict[str, dict] = {}
        self.order: list[str] = []
        self.verified: dict[str, dict] = {}
        self.dropped: set[str] = set()
        # The report's references are already verified and numbered in the Markdown; keep their numbers.
        for ref in result.references:
            self.verified[ref["chunk_id"]] = ref
            self._add(ref["chunk_id"], cited_in_report=True)
        self.lookup = lookup
        self.result = result

    def _add(self, cid: str, cited_in_report: bool = False) -> None:
        if cid in self.by_id:
            return
        v = self.verified[cid]
        self.order.append(cid)
        self.by_id[cid] = {
            "n": len(self.order), "chunk_id": cid, "paper_id": paper_id_of(cid),
            "paper_title": v.get("paper") or v.get("paper_title"), "year": v.get("year"),
            "page": v.get("page"), "section": v.get("section"),
            "quote": _clip(v.get("quote") or v.get("text") or "", 400), "cited_in_report": cited_in_report,
        }

    def verify(self, chunk_ids: Iterable[str]) -> None:
        todo = [c for c in dict.fromkeys(chunk_ids)
                if c and re.fullmatch(CHUNK_ID, c) and c not in self.verified and c not in self.dropped]
        if not todo:
            return
        rows = []
        if self.lookup:
            for i in range(0, len(todo), 20):
                rows += self.lookup(todo[i:i + 20])
        found = {r["chunk_id"]: r for r in rows if r.get("chunk_id")}
        for cid in todo:
            if cid in found:
                row = found[cid]
                prev = self.result.evidence.get(cid, {})
                self.verified[cid] = {"paper": row.get("paper_title"), "year": row.get("year"), "page": row.get("page"),
                                      "section": row.get("section"), "quote": prev.get("quote") or row.get("text")}
            else:
                self.dropped.add(cid)

    def cite(self, chunk_id: str | None) -> int | None:
        if not chunk_id or chunk_id not in self.verified:
            return None
        self._add(chunk_id)
        return self.by_id[chunk_id]["n"]

    def as_list(self) -> list[dict]:
        return [self.by_id[c] for c in self.order]


def _clip(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _outputs(result: InvestigationResult, tool: str) -> list[dict]:
    return [r["output"] for r in result.raw if r["tool"] == tool and "error" not in r["output"]]


def _side(sources: Sources, text: str, chunk_id: str, paper_title: str | None) -> dict | None:
    n = sources.cite(chunk_id)
    if n is None:
        return None
    src = sources.by_id[chunk_id]
    return {"text": text, "paper_id": src["paper_id"], "paper_title": paper_title or src["paper_title"],
            "page": src["page"], "citation": n}


def build_structured(result: InvestigationResult, lookup: Lookup | None, corpus_size: int | None = None) -> dict:
    sources = Sources(result, lookup)

    compare = _outputs(result, "compare_claims")
    papers_out = _outputs(result, "get_paper")
    explore = _outputs(result, "explore_entity")
    search = _outputs(result, "search_evidence")

    # Only evidence that is actually about the question counts; weakly similar text is ignored.
    statements = [s for c in compare for stmts in c.get("statements_by_paper", {}).values() for s in stmts
                  if (s.get("relevance") or 0) >= MIN_RELEVANCE]
    hits = [h for x in search for h in x.get("results", []) if (h.get("score") or 0) >= MIN_RELEVANCE]
    relevant_papers = {s.get("paper_id") for s in statements} | {h.get("paper_id") for h in hits}
    relevant_texts = {_norm(s.get("text", "")) for s in statements}

    def touches_topic(x: dict) -> bool:
        return _norm(x.get("statement_a")) in relevant_texts or _norm(x.get("statement_b")) in relevant_texts

    contradictions = [x for c in compare for x in c.get("contradictions", []) if touches_topic(x)]
    related = [x for c in compare for x in c.get("related_statements", []) if touches_topic(x)]
    paper_statements = [(p, key, s) for p in papers_out if p.get("id") in relevant_papers
                        for key in ("findings", "claims") for s in p.get(key, [])]
    limitations_raw = ([(p.get("title"), l) for p in papers_out if p.get("id") in relevant_papers for l in p.get("limitations", [])] +
                       [(l.get("paper_title"), l) for x in explore for m in x.get("matches", [])
                        for l in m.get("limitations_of_papers_using_it", [])
                        if paper_id_of(l.get("chunk_id") or "") in relevant_papers])
    entity_uses = ([(e["name"], label, p.get("id"), p.get("title"), e.get("chunk_id"))
                    for p in papers_out if p.get("id") in relevant_papers
                    for key, label in (("methods", "Method"), ("datasets", "Dataset")) for e in p.get(key, [])] +
                   [(m["entity"], m["type"], q.get("paper_id"), q.get("title"), q.get("chunk_id"))
                    for x in explore for m in x.get("matches", []) for q in m.get("papers", [])
                    if q.get("paper_id") in relevant_papers])
    evidence_found = bool(statements or hits)
    gaps_in = result.gaps if evidence_found else []

    # Verify every chunk id the structured sections may cite, in one batched pass.
    wanted = ([s.get("chunk_id") for s in statements] + [s.get("chunk_id") for _, _, s in paper_statements] +
              [x.get(k) for x in contradictions + related for k in ("chunk_a", "chunk_b")] +
              [l.get("chunk_id") for _, l in limitations_raw] + [u[4] for u in entity_uses] +
              [e.get("chunk_id") for g in gaps_in for e in g.get("evidence", [])] +
              [h.get("chunk_id") for h in hits])
    sources.verify(c for c in wanted if c)

    # ---------------------------------------------------------------- findings
    findings, seen = [], set()
    ranked = sorted(statements, key=lambda s: -(s.get("relevance") or 0))
    ranked += [{**s, "type": "Finding" if key == "findings" else "Claim", "paper_title": p.get("title"),
                "relevance": None} for p, key, s in paper_statements]
    for s in ranked:
        key = _norm(s.get("text", ""))
        if not key or key in seen:
            continue
        n = sources.cite(s.get("chunk_id"))
        if n is None:
            continue
        seen.add(key)
        src = sources.by_id[s["chunk_id"]]
        findings.append({"type": (s.get("type") or "Finding").lower(), "text": s["text"], "paper_id": src["paper_id"],
                         "paper_title": s.get("paper_title") or src["paper_title"], "year": src["year"], "page": src["page"],
                         "relevance": s.get("relevance"), "citations": [n]})
        if len(findings) >= MAX_FINDINGS:
            break

    # ---------------------------------------------------------------- comparisons
    comparisons, seen_pairs = [], set()
    for kind, rows in (("contradiction", contradictions), ("related", related)):
        for x in sorted(rows, key=lambda r: -(r.get("score") or 0)):
            pair = frozenset((_norm(x.get("statement_a")), _norm(x.get("statement_b"))))
            if pair in seen_pairs:
                continue
            a = _side(sources, x.get("statement_a"), x.get("chunk_a"), x.get("paper_a"))
            b = _side(sources, x.get("statement_b"), x.get("chunk_b"), x.get("paper_b"))
            if not a or not b:
                continue
            seen_pairs.add(pair)
            comparisons.append({
                "kind": kind, "score": round(float(x.get("score") or 0), 3), "a": a, "b": b,
                "note": ("The two papers report opposing results on closely related statements."
                         if kind == "contradiction" else
                         "The statements address the same topic; read both to judge whether they agree."),
            })
    comparisons = comparisons[:MAX_COMPARISONS]

    methods: dict[tuple[str, str], dict] = {}
    for name, label, pid, title, cid in entity_uses:
        n = sources.cite(cid)
        if n is None or not pid:
            continue
        entry = methods.setdefault((label, name), {"entity": name, "type": label.lower(), "papers": {}})
        entry["papers"].setdefault(pid, {"paper_id": pid, "paper_title": title, "citation": n})
    method_comparison = sorted(
        ({**m, "papers": list(m["papers"].values())} for m in methods.values()),
        key=lambda m: (-len(m["papers"]), m["type"], m["entity"]))

    # ---------------------------------------------------------------- limitations
    limitations, seen_lim = [], set()
    for title, l in limitations_raw:
        key = _norm(l.get("text", ""))
        if not key or key in seen_lim:
            continue
        n = sources.cite(l.get("chunk_id"))
        if n is None:
            continue
        seen_lim.add(key)
        src = sources.by_id[l["chunk_id"]]
        limitations.append({"text": l["text"], "kind": "future_work" if l.get("kind") == "future_work" else "limitation",
                            "paper_id": src["paper_id"], "paper_title": title or src["paper_title"], "page": src["page"],
                            "citations": [n]})
        if len(limitations) >= MAX_LIMITATIONS:
            break

    # ---------------------------------------------------------------- gaps
    gaps = []
    for g in gaps_in:
        # A research gap must be concrete (not a generic sentence) and rest on verified evidence from
        # at least MIN_GAP_PAPERS papers that are relevant to this question. Single-paper limitations
        # stay in the Limitations section instead.
        if g.get("specific") is False:
            continue
        gap_papers = {paper_id_of(e.get("chunk_id") or "") for e in g.get("evidence", [])}
        if len(gap_papers & relevant_papers) < MIN_GAP_PAPERS:
            continue
        evidence = []
        for e in g.get("evidence", []):
            n = sources.cite(e.get("chunk_id"))
            if n is not None:
                src = sources.by_id[e["chunk_id"]]
                evidence.append({"citation": n, "paper_id": src["paper_id"], "paper_title": e.get("paper") or src["paper_title"],
                                 "page": src["page"], "quote": _clip(e.get("quote") or "", 300)})
        if len({e["paper_id"] for e in evidence}) < MIN_GAP_PAPERS:
            continue  # not enough verifiable evidence once unverifiable citations are removed
        gaps.append({"id": f"G{len(gaps) + 1}", "title": g.get("title", ""), "type": g.get("type", "candidate"),
                     "rationale": g.get("rationale", ""), "score": g.get("score"), "status": "candidate",
                     "evidence": evidence, "citations": sorted({e["citation"] for e in evidence}), "note": GAP_NOTE,
                     "support_papers": len({e["paper_id"] for e in evidence})})

    # Relevant search passages not cited elsewhere still count as consulted evidence.
    for h in hits[:4]:
        sources.cite(h.get("chunk_id"))

    source_list = sources.as_list()
    papers: dict[str, dict] = {}
    for s in source_list:
        p = papers.setdefault(s["paper_id"], {"paper_id": s["paper_id"], "title": s["paper_title"], "year": s["year"], "sources": 0})
        p["sources"] += 1

    unverified = [w for w in result.warnings if "does not match any evidence" in w]
    if sources.dropped:
        result.warnings.append(f"{len(sources.dropped)} evidence reference(s) returned by tools could not be verified "
                               "in the knowledge graph and were left out.")
    confidence = assess_confidence(mode=result.mode, findings=findings, comparisons=comparisons, sources=source_list,
                                   papers=len(papers), corpus_size=corpus_size, unverified=len(unverified),
                                   narrative=section(result.report_markdown, "Confidence"), evidence_found=evidence_found)
    return {
        "evidence_found": evidence_found,
        "summary": summarize(result.report_markdown, findings) if evidence_found else NO_EVIDENCE,
        "inferences": inferences(result.report_markdown) if result.mode == "llm" else [],
        "open_questions": open_questions(result.report_markdown, evidence_found, result.question),
        "findings": findings,
        "comparisons": comparisons,
        "method_comparison": method_comparison[:12],
        "gaps": gaps,
        "limitations": limitations,
        "confidence": confidence,
        "sources": source_list,
        "papers": sorted(papers.values(), key=lambda p: -p["sources"]),
    }


def summarize(markdown: str, findings: list[dict]) -> str:
    answer = section(markdown, "Answer")
    lines = [l for l in answer.splitlines() if l.strip() and not l.lstrip().startswith(">")]
    if lines:
        return "\n".join(lines).strip()
    if findings:
        return "Most relevant evidence: " + " ".join(f"{f['text']} [{f['citations'][0]}]" for f in findings[:2])
    return "The ingested papers contain little direct evidence on this question."


def assess_confidence(*, mode: str, findings: list, comparisons: list, sources: list, papers: int,
                      corpus_size: int | None, unverified: int, narrative: str = "", evidence_found: bool = True) -> dict:
    conflicts = sum(1 for c in comparisons if c["kind"] == "contradiction")
    reasons, uncertainties = [], []
    reasons.append(f"{len(sources)} verified evidence passage(s) from {papers} paper(s)"
                   + (f" out of {corpus_size} ingested" if corpus_size else "") + ".")
    if mode == "offline":
        uncertainties.append("Offline mode: evidence was ranked by similarity and graph structure; no language model reasoned over it.")
    if conflicts:
        uncertainties.append(f"{conflicts} cross-paper conflict(s) detected; the papers disagree on part of this question.")
    if unverified:
        uncertainties.append(f"{unverified} citation(s) in the narrative did not match stored evidence and are marked [unverified].")
    if corpus_size is not None and corpus_size < 5:
        uncertainties.append(f"Small corpus ({corpus_size} paper(s)); conclusions and gaps reflect only these papers.")
    uncertainties.append("Candidate gaps are hypotheses from the ingested papers, not confirmed novel directions.")

    if not evidence_found:
        level = "low"
        reasons.append("No ingested paper contains evidence relevant to this question.")
    elif not findings or papers < 2 or len(sources) < 3:
        level = "low"
        reasons.append("Little direct evidence or evidence from fewer than two papers.")
    elif mode == "llm" and papers >= 3 and len(sources) >= 6 and not unverified and not conflicts:
        level = "high"
        reasons.append("Consistent evidence across three or more papers, all citations verified.")
    else:
        level = "moderate"
    return {"level": level, "reasons": reasons, "uncertainties": uncertainties, "narrative": narrative or None}


_CITE_NUMS = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _bullets(text: str) -> list[str]:
    out = []
    for line in (text or "").splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", line).strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def inferences(markdown: str) -> list[dict]:
    """Model-generated hypotheses ("Hypothesis: ...") - inferences, not findings stated in the papers."""
    out = []
    for line in _bullets(section(markdown, "Candidate research gaps") or section(markdown, "Candidate Research Gaps")):
        m = re.match(r"^\[?hypothesis:?\]?:?\s*(.*)$", line, re.I)
        if not m or not m.group(1).strip():
            continue
        nums = sorted({int(n) for g in _CITE_NUMS.findall(line) for n in re.split(r"\s*,\s*", g)})
        out.append({"text": m.group(1).strip(), "citations": nums})
    return out[:8]


def open_questions(markdown: str, evidence_found: bool, question: str) -> list[str]:
    """What the evidence does not answer (the report's "Not covered" section), or the whole question."""
    if not evidence_found:
        return [question]
    items = _bullets(section(markdown, "Not covered by the evidence"))
    return [i for i in items if not re.match(r"^(nothing|none|n/a)\b", i, re.I)][:8]

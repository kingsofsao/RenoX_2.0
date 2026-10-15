"""Citation handling and report assembly.

Agents cite evidence with raw chunk ids, e.g. [p_1a2b3c4d5e6f:c003]. This module
turns them into numbered references, verifies every cited id exists in the graph,
and appends a References section pointing to paper + page.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CHUNK_ID = r"p_[0-9a-f]{12}:c\d{3}"
CITATION = re.compile(rf"\[\s*({CHUNK_ID}(?:\s*[,;]\s*{CHUNK_ID})*)\s*\]")


@dataclass
class InvestigationResult:
    question: str
    mode: str
    report_markdown: str = ""
    steps: list[dict] = field(default_factory=list)
    evidence: dict[str, dict] = field(default_factory=dict)
    references: list[dict] = field(default_factory=list)
    gaps: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        return asdict(self)


def collect_evidence(obj, registry: dict[str, dict]) -> None:
    """Walk a tool result and register every evidence chunk it mentions."""
    if isinstance(obj, dict):
        cid = obj.get("chunk_id")
        if isinstance(cid, str) and re.fullmatch(CHUNK_ID, cid):
            entry = registry.setdefault(cid, {"chunk_id": cid})
            for src, dst in (("paper_title", "paper"), ("paper", "paper"), ("title", "paper"), ("page", "page"),
                             ("section", "section"), ("year", "year")):
                if obj.get(src) is not None and dst not in entry:
                    entry[dst] = obj[src]
            quote = obj.get("quote") or obj.get("text")
            if quote and "quote" not in entry:
                entry["quote"] = quote
        for v in obj.values():
            collect_evidence(v, registry)
    elif isinstance(obj, list):
        for v in obj:
            collect_evidence(v, registry)


def finalize_citations(markdown: str, registry: dict[str, dict], lookup=None) -> tuple[str, list[dict], list[str]]:
    """Replace chunk-id citations with [n] and build the reference list.

    `lookup(ids) -> list[dict]` fetches evidence for ids the agent cited but no tool returned
    (still verified against the graph). Ids that do not exist anywhere are flagged.
    """
    cited: list[str] = []
    for m in CITATION.finditer(markdown):
        for cid in re.findall(CHUNK_ID, m.group(1)):
            if cid not in cited:
                cited.append(cid)

    # Verify every cited id against the graph and fill in paper/page/section/year from the source of truth.
    if cited and lookup:
        verified = set()
        for row in lookup(cited):
            verified.add(row["chunk_id"])
            prev = registry.get(row["chunk_id"], {})
            registry[row["chunk_id"]] = {**prev, "chunk_id": row["chunk_id"],
                                         "paper": row.get("paper_title"), "page": row.get("page"),
                                         "section": row.get("section"), "year": row.get("year"),
                                         "quote": prev.get("quote") or row.get("text")}
        for cid in cited:
            if cid not in verified:
                registry.pop(cid, None)
    warnings = []
    numbers: dict[str, int] = {}
    refs: list[dict] = []
    for cid in cited:
        if cid in registry and registry[cid].get("paper"):
            numbers[cid] = len(numbers) + 1
            refs.append({"n": numbers[cid], **registry[cid]})
        else:
            warnings.append(f"Citation {cid} does not match any evidence in the knowledge graph and was marked unverified.")

    def repl(m):
        parts = []
        for cid in re.findall(CHUNK_ID, m.group(1)):
            parts.append(str(numbers[cid]) if cid in numbers else "unverified")
        return "[" + ", ".join(dict.fromkeys(parts)) + "]"

    body = CITATION.sub(repl, markdown)
    if refs:
        lines = ["", "## References", ""]
        for r in refs:
            year = f" ({r['year']})" if r.get("year") else ""
            page = f", p. {r['page']}" if r.get("page") else ""
            section = f", {r['section']}" if r.get("section") else ""
            quote = (r.get("quote") or "").replace("\n", " ")
            quote = quote if len(quote) <= 220 else quote[:219] + "…"
            lines.append(f"{r['n']}. *{r['paper']}*{year}{page}{section} — \"{quote}\" `{r['chunk_id']}`")
        body = body.rstrip() + "\n" + "\n".join(lines) + "\n"
    return body, refs, warnings


def save_report(result: InvestigationResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = re.sub(r"[^a-z0-9]+", "-", result.question.lower()).strip("-")[:50] or "report"
    md_path = out_dir / f"{stamp}-{name}.md"
    md_path.write_text(result.report_markdown, encoding="utf-8")
    md_path.with_suffix(".json").write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
    return md_path

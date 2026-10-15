"""Command-line interface.

    python -m researchmind.cli check                 # verify FalkorDB + embeddings + Claude config
    python -m researchmind.cli samples               # generate synthetic demo PDFs into data/papers
    python -m researchmind.cli ingest data/papers    # ingest a PDF or a folder of PDFs
    python -m researchmind.cli ask "your question"   # run an investigation, save the report
    python -m researchmind.cli gaps ["topic"]        # list candidate research gaps
    python -m researchmind.cli stats                 # node / relationship counts
    python -m researchmind.cli reset --yes           # delete the knowledge graph
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import BACKEND_ROOT, get_settings
from .graph import GraphConnectionError, GraphStore
from .ingest import IngestionError


def _store() -> GraphStore:
    return GraphStore()


def cmd_check(args) -> int:
    settings = get_settings()
    ok = True
    print(f"FalkorDB graph '{settings.graph_name}': ", end="")
    try:
        with _store() as store:
            print(f"connected ({len(store.list_papers())} papers)")
    except GraphConnectionError as e:
        print(f"FAILED - {e}")
        ok = False
    from .embeddings import get_embedder
    emb = get_embedder()
    print(f"Embeddings: {emb.name} ({emb.dim} dims)")
    from .llm import llm_status
    st = llm_status()
    print(f"Investigation LLM: {st['provider']} {st.get('model') or ''} - {st['status']}: {st['message']}")
    print("Extraction LLM: " + ("Claude" if settings.has_anthropic_key else "heuristic extractor (ANTHROPIC_API_KEY unset)"))
    return 0 if ok else 1


def cmd_samples(args) -> int:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))
    from make_sample_pdfs import main as make
    for p in make(args.out):
        print(f"wrote {p}")
    return 0


def cmd_ingest(args) -> int:
    from .pipeline import ingest_directory, ingest_file
    use_llm = False if args.no_llm else None
    failures = 0
    with _store() as store:
        for target in args.paths:
            path = Path(target)
            results = (ingest_directory(path, store, force=args.force, progress=print) if path.is_dir()
                       else [_safe_ingest(ingest_file, path, store, args.force, use_llm)])
            for r in results:
                if r.get("status") == "error":
                    failures += 1
                    print(f"  ERROR {r.get('file')}: {r.get('error')}")
                elif r.get("status") == "ingested":
                    print(f"  {r['title']}: {r['chunks']} chunks, {r['methods']} methods, {r['datasets']} datasets, "
                          f"{r['claims']} claims, {r['findings']} findings, {r['limitations']} limitations, "
                          f"{r['cross_paper_links']} cross-paper links ({r['extractor']})")
                else:
                    print(f"  {r.get('title')}: unchanged (use --force to re-ingest)")
        print(store.stats())
    return 1 if failures else 0


def _safe_ingest(fn, path, store, force, use_llm):
    try:
        return fn(path, store, force=force, use_llm=use_llm, progress=print)
    except IngestionError as e:
        return {"file": Path(path).name, "status": "error", "error": str(e)}


def cmd_ask(args) -> int:
    from .agent import Investigator
    from .report import save_report

    def on_event(e):
        if e["type"] == "tool_call":
            print(f"  -> {e['tool']}({', '.join(f'{k}={v!r}' for k, v in e['args'].items())})")
        elif e["type"] == "tool_result":
            print(f"     {e['summary']}")
        elif e["type"] in ("status", "thought"):
            print(f"  .. {e['message'][:200]}")

    with _store() as store:
        result = Investigator(store, use_llm=not args.offline).run(args.question, on_event=on_event)
    path = save_report(result, get_settings().data_dir / "reports")
    print("\n" + result.report_markdown)
    for w in result.warnings:
        print(f"WARNING: {w}")
    print(f"\nSaved report to {path}")
    return 0


def cmd_gaps(args) -> int:
    from .tools import ResearchTools
    with _store() as store:
        gaps = ResearchTools(store).find_research_gaps(args.topic)["gaps"]
    for g in gaps:
        print(f"{g['id']} [{g['type']}] score={g['score']}: {g['title']}")
        print(f"    {g['rationale']}")
        for e in g["evidence"]:
            print(f"    - {e.get('paper')} p.{e.get('page', '?')} [{e['chunk_id']}]")
    return 0


def cmd_stats(args) -> int:
    with _store() as store:
        for k, v in sorted(store.stats().items()):
            print(f"{k}: {v}")
    return 0


def cmd_reset(args) -> int:
    if not args.yes:
        print("This deletes every node in the graph. Re-run with --yes to confirm.")
        return 1
    with _store() as store:
        store.reset()
    print("Graph deleted.")
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="researchmind", description="ResearchMind AI command line")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    p = sub.add_parser("samples"); p.add_argument("--out", default=None); p.set_defaults(fn=cmd_samples)
    p = sub.add_parser("ingest"); p.add_argument("paths", nargs="+"); p.add_argument("--force", action="store_true")
    p.add_argument("--no-llm", action="store_true", help="use the heuristic extractor even if Claude is configured")
    p.set_defaults(fn=cmd_ingest)
    p = sub.add_parser("ask"); p.add_argument("question"); p.add_argument("--offline", action="store_true"); p.set_defaults(fn=cmd_ask)
    p = sub.add_parser("gaps"); p.add_argument("topic", nargs="?"); p.set_defaults(fn=cmd_gaps)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    p = sub.add_parser("reset"); p.add_argument("--yes", action="store_true"); p.set_defaults(fn=cmd_reset)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except GraphConnectionError as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""PDF parsing and heuristic extraction (no database needed)."""

import pytest

from researchmind.extract import HeuristicExtractor, quote_in_chunk, slug
from researchmind.ingest import IngestionError, parse_pdf


def test_parse_metadata_and_chunks(sample_pdfs):
    paper = parse_pdf(sample_pdfs[0])
    assert paper.title == "Graph Attention Networks for Drug-Target Interaction Prediction"
    assert paper.authors == ["Maya Chen", "Arjun Patel"]
    assert paper.year == 2023
    assert paper.num_pages == 2
    assert paper.abstract.startswith("Predicting drug-target interactions")
    sections = [c.section for c in paper.chunks]
    assert {"Abstract", "Method", "Limitations"} <= set(sections)
    assert all(c.id.startswith(paper.id + ":c") for c in paper.chunks)
    assert {c.page for c in paper.chunks} == {1, 2}  # page tracking survives the page break
    assert not any("Placeholder reference" in c.text for c in paper.chunks)  # references are excluded


def test_parse_is_deterministic(sample_pdfs):
    a, b = parse_pdf(sample_pdfs[1]), parse_pdf(sample_pdfs[1])
    assert a.id == b.id
    assert [(c.id, c.text) for c in a.chunks] == [(c.id, c.text) for c in b.chunks]


def test_parse_rejects_bad_input(tmp_path):
    with pytest.raises(IngestionError):
        parse_pdf(tmp_path / "missing.pdf")
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf at all")
    with pytest.raises(IngestionError):
        parse_pdf(bad)
    txt = tmp_path / "notes.txt"
    txt.write_text("hello")
    with pytest.raises(IngestionError):
        parse_pdf(txt)


def test_heuristic_extraction(sample_pdfs):
    paper = parse_pdf(sample_pdfs[0])
    x = HeuristicExtractor().extract(paper)
    methods = {m.text for m in x.methods}
    datasets = {d.text for d in x.datasets}
    assert "Graph Attention Network" in methods
    assert {"DAVIS", "BindingDB"} <= datasets
    assert "KIBA" not in datasets  # only mentioned as future work, not used
    assert any("0.91" in f.text for f in x.findings)
    assert any(l.kind == "future_work" for l in x.limitations)
    chunk_text = {c.id: c.text for c in paper.chunks}
    for item in x.methods + x.datasets + x.claims + x.findings + x.limitations:
        assert quote_in_chunk(item.quote, chunk_text[item.chunk_id]), item  # every item has real evidence


def test_slug_aliases():
    assert slug("GAT") == slug("Graph Attention Network") == slug("graph attention networks")
    assert slug("DAVIS dataset") == slug("DAVIS")

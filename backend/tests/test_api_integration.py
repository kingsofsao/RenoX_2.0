"""INTEGRATION tests: real FalkorDB engine, real HTTP stack (FastAPI TestClient), real PDFs.

Uses FALKORDB_TEST_URL (or FALKORDB_URL) and the throwaway graph `researchmind_pytest_api`.
Skipped automatically when no FalkorDB is reachable.
"""

import io
import os

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from pdf_fixtures import encrypted_pdf
from researchmind.config import get_settings
from researchmind.graph import GraphConnectionError, GraphStore

pytestmark = pytest.mark.integration
API_GRAPH = "researchmind_pytest_api"


@pytest.fixture(scope="module")
def client():
    url = os.getenv("FALKORDB_TEST_URL") or get_settings().falkordb_url
    if not url:
        pytest.skip("No FALKORDB_TEST_URL / FALKORDB_URL configured")
    try:
        store = GraphStore(url=url, graph_name=API_GRAPH)
    except GraphConnectionError as e:
        pytest.skip(f"FalkorDB not reachable: {e}")
    store.reset()
    mp = pytest.MonkeyPatch()
    mp.setenv("FALKORDB_URL", url)
    mp.setenv("FALKORDB_GRAPH", API_GRAPH)
    database.reset_store()
    with TestClient(app) as c:
        yield c
    database.reset_store()
    mp.undo()
    store.graph.delete()
    store.close()


def upload(client, *paths_or_files):
    files = []
    for item in paths_or_files:
        if isinstance(item, tuple):
            files.append(("files", item))
        else:
            files.append(("files", (item.name, open(item, "rb"), "application/pdf")))
    r = client.post("/api/papers/upload", files=files)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_reports_connected(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == {**body["database"], "status": "connected", "graph": API_GRAPH}


def test_multi_upload_and_listing(client, sample_pdfs, tmp_path):
    bad = encrypted_pdf(tmp_path / "locked.pdf")
    body = upload(client, *sample_pdfs, bad, ("readme.txt", io.BytesIO(b"hi"), "text/plain"))
    assert body["summary"] == {"received": 5, "processed": 3, "duplicate": 0, "failed": 1, "rejected": 1}
    failed = next(r for r in body["results"] if r["status"] == "failed")
    assert failed["error_code"] == "encrypted" and failed["filename"] == "locked.pdf"

    listing = client.get("/api/papers").json()
    assert listing["counts"] == {"total": 4, "processed": 3, "failed": 1}
    processed = [p for p in listing["papers"] if p["status"] == "processed"]
    assert all(p["title"] and p["page_count"] == 2 and p["filename"].startswith("sample_") for p in processed)
    assert client.get("/api/papers?status=failed").json()["papers"][0]["error_code"] == "encrypted"
    assert client.get("/api/papers?search=protein").json()["total_matching"] == 1


def test_duplicate_upload_creates_no_new_nodes(client, sample_pdfs):
    before = client.get("/api/graph/stats").json()
    body = upload(client, sample_pdfs[0], (f"copy-of-{sample_pdfs[0].name}", open(sample_pdfs[0], "rb"), "application/pdf"))
    assert [r["status"] for r in body["results"]] == ["duplicate", "duplicate"]
    assert client.get("/api/graph/stats").json() == before
    assert client.get("/api/papers").json()["counts"]["processed"] == 3


def test_paper_detail_with_paginated_text(client):
    papers = client.get("/api/papers?status=processed").json()["papers"]
    pid = next(p["id"] for p in papers if "Graph Attention" in p["title"])
    page1 = client.get(f"/api/papers/{pid}?page=1&page_size=1").json()
    assert page1["paper"]["authors"] == ["Maya Chen", "Arjun Patel"]
    assert page1["paper"]["sha256"].startswith(pid[2:])
    assert page1["pagination"] == {"page": 1, "page_size": 1, "total_pages": 2}
    assert page1["pages"][0]["page"] == 1 and "Abstract" in page1["pages"][0]["text"]
    page2 = client.get(f"/api/papers/{pid}?page=2&page_size=1").json()
    assert page2["pages"][0]["page"] == 2 and "Limitations" in page2["pages"][0]["text"]
    knowledge = page1["paper"]["knowledge"]
    assert {m["name"] for m in knowledge["methods"]} >= {"Graph Attention Network"}
    assert knowledge["chunks"] > 0 and "Limitations" in knowledge["sections"]
    assert client.get(f"/api/papers/{pid}/file").headers["content-type"] == "application/pdf"


def test_failed_paper_detail(client):
    failed = client.get("/api/papers?status=failed").json()["papers"][0]
    detail = client.get(f"/api/papers/{failed['id']}").json()
    assert detail["paper"]["status"] == "failed" and detail["text_available"] is False and detail["pages"] == []


def test_search_is_parameterized(client):
    before = client.get("/api/graph/stats").json()
    r = client.get("/api/papers", params={"search": "x' OR 1=1 WITH p DETACH DELETE p //"})
    assert r.status_code == 200 and r.json()["total_matching"] == 0
    assert client.get("/api/graph/stats").json() == before


def test_graph_overview(client):
    ov = client.get("/api/graph/overview").json()
    types = {n["type"] for n in ov["nodes"]}
    assert types == {"paper", "method", "dataset"}
    assert any(e["type"] == "CONTRADICTS" for e in ov["edges"])


def test_delete_paper(client, tmp_path):
    from pdf_fixtures import untitled_pdf
    body = upload(client, untitled_pdf(tmp_path / "untitled-notes.pdf"))
    res = body["results"][0]
    assert res["status"] == "processed" and res["title"] is None  # unknown title is not invented
    detail = client.get(f"/api/papers/{res['paper_id']}").json()["paper"]
    assert detail["title"] is None and detail["display_title"] == "untitled-notes.pdf"
    assert client.delete(f"/api/papers/{res['paper_id']}").status_code == 204
    assert client.get(f"/api/papers/{res['paper_id']}").status_code == 404

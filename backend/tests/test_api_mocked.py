"""MOCKED tests: no database needed.

The FalkorDB dependency is either unconfigured, pointed at a closed port, or replaced
with a stand-in object, so these exercise validation, error handling and parsing only.
"""

import io
import time
from unittest.mock import MagicMock

import pytest

from app import database
from app.config import get_api_settings
from app.main import app
from authclient import sign_up
from pdf_fixtures import blank_pdf, encrypted_pdf, scanned_pdf, untitled_pdf
from researchmind.ingest import IngestionError, parse_pdf


@pytest.fixture
def signed_in(monkeypatch):
    """(client, project id) of a freshly signed-up user."""
    database.reset_store()
    client, _, pid = sign_up()
    yield client, pid
    for dep in (database.get_store,):
        app.dependency_overrides.pop(dep, None)
    database.reset_store()


@pytest.fixture
def client(signed_in):
    return signed_in[0]


@pytest.fixture
def papers_url(signed_in):
    return f"/api/projects/{signed_in[1]}/papers"


def test_health_without_database_config(client, monkeypatch):
    monkeypatch.delenv("FALKORDB_URL", raising=False)
    monkeypatch.setattr("researchmind.config.load_dotenv", lambda *a, **k: None)
    r = client.get("/api/health")
    assert r.status_code == 200  # the backend itself is up
    body = r.json()
    assert body["status"] == "degraded"
    assert body["backend"]["status"] == "ok"
    assert body["database"]["status"] == "not_configured"


def test_health_database_unreachable_hides_credentials(client, monkeypatch):
    monkeypatch.setenv("FALKORDB_URL", "falkor://default:SuperSecret123@localhost:1")
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["database"]["status"] == "unavailable"
    assert "SuperSecret123" not in r.text and "localhost:1" not in r.text


def test_routes_return_503_without_database(client, papers_url, monkeypatch):
    monkeypatch.setenv("FALKORDB_URL", "falkor://default:SuperSecret123@localhost:1")
    r = client.get(papers_url)
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "database_unavailable"
    assert "SuperSecret123" not in r.text and "Traceback" not in r.text


def test_upload_rejects_invalid_files_before_touching_database(client, papers_url):
    fake_store = MagicMock()
    app.dependency_overrides[database.get_store] = lambda: fake_store
    files = [
        ("files", ("notes.txt", io.BytesIO(b"plain text"), "text/plain")),
        ("files", ("renamed.pdf", io.BytesIO(b"this is not a pdf"), "application/pdf")),
        ("files", ("empty.pdf", io.BytesIO(b""), "application/pdf")),
    ]
    r = client.post(f"{papers_url}/upload", files=files)
    assert r.status_code == 200
    codes = [x["error_code"] for x in r.json()["results"]]
    assert codes == ["not_pdf", "not_pdf", "empty_file"]
    assert r.json()["summary"]["rejected"] == 3
    fake_store.query.assert_not_called()


def test_upload_enforces_size_limit(client, papers_url, monkeypatch):
    app.dependency_overrides[database.get_store] = lambda: MagicMock()
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_api_settings.cache_clear()
    try:
        big = b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10)
        r = client.post(f"{papers_url}/upload", files=[("files", ("big.pdf", io.BytesIO(big), "application/pdf"))])
        assert r.json()["results"][0]["error_code"] == "too_large"
        leftovers = list(get_api_settings().upload_dir.parent.rglob("*.part"))
        assert leftovers == []  # partial file cleaned up
    finally:
        monkeypatch.delenv("MAX_UPLOAD_MB")
        get_api_settings.cache_clear()


def test_upload_limits_file_count(client, papers_url, monkeypatch):
    app.dependency_overrides[database.get_store] = lambda: MagicMock()
    files = [("files", (f"f{i}.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))
             for i in range(get_api_settings().max_files_per_upload + 1)]
    r = client.post(f"{papers_url}/upload", files=files)
    assert r.status_code == 400 and "Too many files" in r.json()["error"]["message"]


def test_slow_upload_batches_are_streamed(client, papers_url, sample_pdfs, monkeypatch):
    """A batch that outlasts the keep-alive interval sends spaces first, so proxies (Vercel: 120 s) keep the request open."""
    from app.routes import papers

    def slow(staged, store, project):
        time.sleep(0.3)
        return {"filename": staged.filename, "status": "failed", "paper_id": staged.paper_id,
                "message": "Could not read the PDF.", "error_code": "parse_failed"}
    monkeypatch.setattr(papers, "KEEPALIVE_SECONDS", 0.05)
    monkeypatch.setattr(papers, "process_upload", slow)
    app.dependency_overrides[database.get_store] = lambda: MagicMock()
    r = client.post(f"{papers_url}/upload",
                    files=[("files", ("a.pdf", sample_pdfs[0].read_bytes(), "application/pdf"))])
    assert r.status_code == 200 and r.text.startswith(" ")
    body = r.json()
    assert body["summary"]["failed"] == 1 and body["results"][0]["filename"] == "a.pdf"


def test_upload_requires_files(client, papers_url):
    app.dependency_overrides[database.get_store] = lambda: MagicMock()
    r = client.post(f"{papers_url}/upload")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_invalid_paper_id_is_rejected(client, papers_url):
    app.dependency_overrides[database.get_store] = lambda: MagicMock()
    r = client.get(f"{papers_url}/..%2F..%2Fsecrets")
    assert r.status_code in (404, 422)


@pytest.mark.parametrize("maker,code", [(encrypted_pdf, "encrypted"), (scanned_pdf, "no_text"), (blank_pdf, "empty")])
def test_problem_pdfs_are_classified(tmp_path, maker, code):
    path = maker(tmp_path / f"{code}.pdf")
    with pytest.raises(IngestionError) as err:
        parse_pdf(path)
    assert err.value.code == code
    if code == "no_text":
        assert "OCR" in str(err.value)


def test_unknown_metadata_is_not_invented(tmp_path):
    paper = parse_pdf(untitled_pdf(tmp_path / "untitled.pdf"))
    assert paper.title_detected is False
    assert paper.title == "untitled"  # falls back to the file name, flagged as not detected
    assert paper.authors == []


def test_page_text_is_preserved(sample_pdfs):
    paper = parse_pdf(sample_pdfs[0])
    assert len(paper.pages) == paper.num_pages == 2
    assert "Abstract" in paper.pages[0] and "Limitations" in paper.pages[1]

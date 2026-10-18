"""Shared fixtures.

Graph tests need a running FalkorDB. They use FALKORDB_TEST_URL if set, otherwise
FALKORDB_URL, and write to a throwaway graph (`researchmind_pytest`) - never the
main `researchmind` graph. Without a reachable FalkorDB they are skipped.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Keep test output (processed JSON, reports) out of the real data/ folder.
os.environ["RESEARCHMIND_DATA_DIR"] = tempfile.mkdtemp(prefix="researchmind-test-")
# Tests choose their LLM explicitly (mocks); backend/.env's provider must not leak in.
# Live tests (test_ollama_live.py) construct OllamaLLM directly from LLM_MODEL / OLLAMA_BASE_URL.
os.environ["LLM_PROVIDER"] = "none"
# Most mocked tests exercise the offline plan; tests of the AI-required behaviour switch it on explicitly.
os.environ["AI_REQUIRED"] = "false"
# Public forms require a minimum fill time against bots; tests submit immediately.
os.environ["FORM_MIN_SECONDS"] = "0"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

TEST_GRAPH = "researchmind_pytest"


def pytest_collection_modifyitems(items):
    # Anything that touches the real database is an integration test, whether or not it says so.
    for item in items:
        if {"store", "ingested"} & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def sample_pdfs(tmp_path_factory) -> list[Path]:
    from make_sample_pdfs import main as make
    return make(str(tmp_path_factory.mktemp("papers")))


@pytest.fixture(scope="session")
def store():
    from researchmind.config import get_settings
    from researchmind.graph import GraphConnectionError, GraphStore

    url = os.getenv("FALKORDB_TEST_URL") or get_settings().falkordb_url
    if not url:
        pytest.skip("No FALKORDB_TEST_URL / FALKORDB_URL configured")
    try:
        s = GraphStore(url=url, graph_name=TEST_GRAPH)
    except GraphConnectionError as e:
        pytest.skip(f"FalkorDB not reachable: {e}")
    s.reset()
    yield s
    s.reset()
    s.graph.delete()
    s.close()


@pytest.fixture(scope="session")
def ingested(store, sample_pdfs):
    from researchmind.pipeline import ingest_file
    return [ingest_file(p, store, use_llm=False) for p in sample_pdfs]


@pytest.fixture(autouse=True)
def fresh_limits():
    """Rate limits are per process; give every test a clean slate."""
    from app.ratelimit import get_limiters
    get_limiters().reset()
    yield


@pytest.fixture(autouse=True)
def memory_accounts(request):
    """Mocked tests get an in-memory user/session store; integration tests use the real FalkorDB one."""
    if request.node.get_closest_marker("integration") or request.node.get_closest_marker("live_llm"):
        yield None
        return
    from app import auth
    from app.main import app
    from researchmind.accounts import MemoryAccounts
    from researchmind.site import MemorySiteStore
    accounts, site = MemoryAccounts(), MemorySiteStore()
    app.dependency_overrides[auth.get_accounts] = lambda: accounts
    app.dependency_overrides[auth.get_site] = lambda: site
    yield accounts
    app.dependency_overrides.pop(auth.get_accounts, None)
    app.dependency_overrides.pop(auth.get_site, None)


@pytest.fixture(autouse=True)
def memory_registry(request):
    """Mocked tests get an in-memory project registry; integration tests use the real FalkorDB one."""
    if request.node.get_closest_marker("integration") or request.node.get_closest_marker("live_llm"):
        yield None
        return
    from app import database
    from app.main import app
    from app.routes import projects as project_routes
    from researchmind.projects import MemoryRegistry
    registry = MemoryRegistry()
    app.dependency_overrides[database.get_registry] = lambda: registry

    def no_database(project):  # project listings count papers; mocked tests have no database
        raise database.DatabaseUnavailable("not_configured")
    original = project_routes.store_for
    project_routes.store_for = no_database
    yield registry
    project_routes.store_for = original
    app.dependency_overrides.pop(database.get_registry, None)

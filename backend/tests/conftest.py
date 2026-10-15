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

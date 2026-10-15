"""MOCK API server for UI testing without FalkorDB.

Runs the real FastAPI app (routes, validation, investigation manager, MCP bridge, citation
verification) but replaces the graph store and research tools with the in-memory fakes from
`tests/fakes.py`. Nothing here touches a database or an LLM; data is canned and labelled.

    cd backend
    .venv\\Scripts\\python.exe tests\\mock_server.py          # serves on http://127.0.0.1:8001

Point a Vite dev server at it:  $env:VITE_API_PROXY_TARGET="http://127.0.0.1:8001"; npm run dev -- --port 5174
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402

from app import database  # noqa: E402
from app.main import app  # noqa: E402
from app.routes import health  # noqa: E402
from app.services import investigation_service  # noqa: E402
from app.services.investigation_service import InvestigationManager  # noqa: E402
from fakes import FakeStore, FakeTools  # noqa: E402
from researchmind.agent import Investigator  # noqa: E402


class PacedTools(FakeTools):
    """Fake tools with a small delay per call so progress is visible in the UI."""

    def _enter(self, tool, **args):
        time.sleep(0.4)
        super()._enter(tool, **args)


store = FakeStore()
manager = InvestigationManager(2, 60, investigator_factory=lambda s, use_llm=True, time_budget_s=None:
                               Investigator(s, use_llm=False, tools=PacedTools(), time_budget_s=time_budget_s))
app.dependency_overrides[database.get_store] = lambda: store
app.dependency_overrides[investigation_service.get_manager] = lambda: manager
health.check_database = lambda: {"status": "connected", "graph": "MOCK (in-memory fakes)", "latency_ms": 0.1, "message": None}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")

"""Graph statistics and an overview for visualization."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from researchmind.graph import GraphStore

from ..database import get_store
from ..schemas.health import GraphOverview, GraphStats
from ..services import graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/stats", response_model=GraphStats)
def stats(store: GraphStore = Depends(get_store)) -> dict:
    return graph_service.graph_stats(store)


@router.get("/overview", response_model=GraphOverview)
def overview(limit: Annotated[int, Query(ge=1, le=200)] = 60, store: GraphStore = Depends(get_store)) -> dict:
    return graph_service.graph_overview(store, limit=limit)

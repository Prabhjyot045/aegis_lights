from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.mape.monitor import Monitor, get_monitor_singleton

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/snapshot")
async def graph_snapshot(monitor: Monitor = Depends(get_monitor_singleton)) -> Dict[str, Any]:
	"""Expose the runtime graph for visualization clients."""

	return monitor.runtime_graph.to_visualization_snapshot()

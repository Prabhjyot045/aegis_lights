"""
Copilot instructions:

Implement a FastAPI router that exposes a visualization-friendly snapshot of the current
graph and MAPE working state.

Requirements:

- Use APIRouter from fastapi.
- Expose a GET endpoint `/graph/snapshot`.

The response should include:
- a serialization of the RuntimeGraph (nodes and edges) via RuntimeGraph.to_visualization_snapshot()
- optionally, hotspot and bypass information from MAPEWorkingState to help the client highlight them.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import BypassPath, HotspotEdge, MAPEWorkingState

router = APIRouter(prefix="/graph", tags=["graph"])


def _runtime_graph_dependency() -> RuntimeGraph:
  from app.main import get_runtime_graph as _get

  return _get()


def _working_state_dependency() -> MAPEWorkingState:
  from app.main import get_working_state as _get

  return _get()


@router.get("/snapshot")
async def graph_snapshot(
  runtime_graph: RuntimeGraph = Depends(_runtime_graph_dependency),
  working_state: MAPEWorkingState = Depends(_working_state_dependency),
) -> Dict[str, Any]:
  """Expose the runtime graph and working-state overlays for visualization clients."""

  return {
    "graph": runtime_graph.to_visualization_snapshot(),
    "hotspots": [_serialize_hotspot(edge) for edge in working_state.get_hotspots()],
    "bypass_paths": [_serialize_bypass_path(path) for path in working_state.get_bypass_paths()],
    "intersection_contexts": _serialize_intersection_contexts(working_state),
  }


def _serialize_hotspot(edge: HotspotEdge) -> Dict[str, Any]:
  return asdict(edge)


def _serialize_bypass_path(path: BypassPath) -> Dict[str, Any]:
  return asdict(path)


def _serialize_intersection_contexts(working_state: MAPEWorkingState) -> Dict[str, Any]:
  contexts = working_state.get_intersection_contexts()
  return {
    intersection_id: {
      "intersection_id": context.intersection_id,
      "features": context.features,
    }
    for intersection_id, context in contexts.items()
  }

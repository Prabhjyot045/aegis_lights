"""
Copilot instructions:

Create the FastAPI application for the AegisLights controller, focusing on wiring the Monitor.

Requirements:

- Define a FastAPI app instance.
- On startup:
  - create a RuntimeGraph instance
  - initialize the database (or at least create a db_session_factory placeholder)
  - create a single Monitor instance with the shared RuntimeGraph
  - store the Monitor in a module-level variable so it can be used by dependencies

- Provide a dependency function:

  def get_monitor() -> Monitor:
      return the singleton Monitor instance

- Include routers from:
  - app.api.routes.simulator_ingest (for /simulator/snapshot)
  - app.api.routes.health (simple GET /health returning {"status": "ok"})
  - app.api.routes.graph_snapshot (will use RuntimeGraph.to_visualization_snapshot later)

- Expose the FastAPI `app` at module level so `uvicorn app.main:app` works.

Do not implement the full MAPE loop yet; we only need:
- the shared RuntimeGraph singleton
- the Monitor singleton
- the ingest route to be live

This will allow us to:
- start the controller,
- POST a SimulatorSnapshot to /simulator/snapshot,
- and see the RuntimeGraph being updated.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI

from app.api.routes import graph_snapshot, health, simulator_ingest
from app.mape.analyze import Analyzer
from app.mape.monitor import (
  Monitor,
  SessionFactory,
  get_monitor_singleton,
  set_monitor_singleton,
)
from app.models.goals import default_goals
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import MAPEWorkingState

logger = logging.getLogger(__name__)

app = FastAPI(title="AegisLights Controller")

_runtime_graph: Optional[RuntimeGraph] = None
_working_state: Optional[MAPEWorkingState] = None
_analyzer: Optional[Analyzer] = None


@app.on_event("startup")
async def _startup() -> None:
  global _runtime_graph, _working_state, _analyzer

  _runtime_graph = RuntimeGraph()
  _working_state = MAPEWorkingState()
  db_session_factory = _build_db_session_factory()

  _analyzer = Analyzer(runtime_graph=_runtime_graph, working_state=_working_state, goals=default_goals())

  monitor = Monitor(
    runtime_graph=_runtime_graph,
    db_session_factory=db_session_factory,
    post_update_hook=_analyzer.analyze,
  )
  set_monitor_singleton(monitor)


def _build_db_session_factory() -> SessionFactory:
  class _NoopSession:
    def add(self, record) -> None:  # type: ignore[no-untyped-def]
      logger.debug("Persist cycle metric (stub)", extra={"record": record})

    def commit(self) -> None:  # type: ignore[no-untyped-def]
      logger.debug("Commit (stub)")

    def rollback(self) -> None:  # type: ignore[no-untyped-def]
      logger.debug("Rollback (stub)")

    def close(self) -> None:  # type: ignore[no-untyped-def]
      logger.debug("Close (stub)")

  def factory() -> _NoopSession:
    return _NoopSession()

  return factory


def get_monitor() -> Monitor:
  return get_monitor_singleton()


def get_runtime_graph() -> RuntimeGraph:
  if _runtime_graph is None:
    raise RuntimeError("Runtime graph has not been initialized")
  return _runtime_graph


def get_working_state() -> MAPEWorkingState:
  if _working_state is None:
    raise RuntimeError("MAPE working state has not been initialized")
  return _working_state


def get_analyzer() -> Analyzer:
  if _analyzer is None:
    raise RuntimeError("Analyzer has not been initialized")
  return _analyzer


app.include_router(health.router)
app.include_router(simulator_ingest.router)
app.include_router(graph_snapshot.router)

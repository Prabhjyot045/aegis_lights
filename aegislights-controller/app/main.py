from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import FastAPI

from app.adapters.simulator_client import SimulatorAPIContract, SimulatorClient
from app.api.routes import graph_snapshot, health, simulator_ingest
from app.core.config import get_settings
from app.core.db import SessionLocal, init_db
from app.mape.analyze import Analyzer
from app.mape.execute import Executor
from app.mape.loop import MAPELoop, start_mape_loop
from app.mape.monitor import Monitor, get_monitor_singleton, set_monitor_singleton
from app.mape.plan import Planner
from app.models.goals import AdaptationGoals, default_goals
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import MAPEWorkingState, RecentGlobalMetrics
from app.models.phase_library import PhaseLibrary

logger = logging.getLogger(__name__)

app = FastAPI(title="AegisLights Controller")

_settings = get_settings()

_runtime_graph: Optional[RuntimeGraph] = None
_working_state: Optional[MAPEWorkingState] = None
_goals: Optional[AdaptationGoals] = None
_phase_library: Optional[PhaseLibrary] = None
_recent_metrics: Optional[RecentGlobalMetrics] = None
_analyzer: Optional[Analyzer] = None
_planner: Optional[Planner] = None
_executor: Optional[Executor] = None
_monitor: Optional[Monitor] = None
_simulator_client: Optional[SimulatorClient] = None
_mape_loop: Optional[MAPELoop] = None
_mape_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def _startup() -> None:
  global _runtime_graph, _working_state, _goals, _phase_library, _recent_metrics
  global _analyzer, _planner, _executor, _monitor, _simulator_client, _mape_loop, _mape_task

  init_db()
  _runtime_graph = RuntimeGraph()
  _working_state = MAPEWorkingState()
  _goals = default_goals()
  _phase_library = PhaseLibrary()
  _recent_metrics = RecentGlobalMetrics()
  db_session_factory = SessionLocal

  simulator_contract = SimulatorAPIContract(
    base_url=_settings.simulator_base_url,
    snapshot_path=_settings.simulator_snapshot_path,
    plan_path_template=_settings.simulator_plan_path,
    api_key=_settings.simulator_api_key,
  )
  _simulator_client = SimulatorClient(api_contract=simulator_contract)
  _analyzer = Analyzer(runtime_graph=_runtime_graph, working_state=_working_state, goals=_goals)
  _planner = Planner(
    runtime_graph=_runtime_graph,
    working_state=_working_state,
    goals=_goals,
    phase_library=_phase_library,
  )
  _executor = Executor(
    runtime_graph=_runtime_graph,
    simulator_client=_simulator_client,
    goals=_goals,
    recent_metrics=_recent_metrics,
    rollback_threshold=_settings.rollback_utility_threshold,
  )

  _monitor = Monitor(
    runtime_graph=_runtime_graph,
    db_session_factory=db_session_factory,
    recent_metrics=_recent_metrics,
  )
  set_monitor_singleton(_monitor)

  _mape_loop = MAPELoop(
    runtime_graph=_runtime_graph,
    working_state=_working_state,
    goals=_goals,
    analyzer=_analyzer,
    planner=_planner,
    executor=_executor,
    monitor=_monitor,
    simulator_client=_simulator_client,
    recent_metrics=_recent_metrics,
    interval_seconds=10.0,
  )
  _mape_task = start_mape_loop(_mape_loop)


@app.on_event("shutdown")
async def _shutdown() -> None:
  global _mape_loop, _mape_task, _simulator_client

  if _mape_loop is not None:
    _mape_loop.stop()
  if _mape_task is not None:
    try:
      await asyncio.wait_for(_mape_task, timeout=5.0)
    except asyncio.TimeoutError:
      logger.warning("MAPE loop task did not shut down cleanly")
  if _simulator_client is not None:
    _simulator_client.close()


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


def get_goals() -> AdaptationGoals:
  if _goals is None:
    raise RuntimeError("Goals have not been initialized")
  return _goals


def get_planner() -> Planner:
  if _planner is None:
    raise RuntimeError("Planner has not been initialized")
  return _planner


def get_executor() -> Executor:
  if _executor is None:
    raise RuntimeError("Executor has not been initialized")
  return _executor


def get_mape_loop() -> MAPELoop:
  if _mape_loop is None:
    raise RuntimeError("MAPE loop has not been initialized")
  return _mape_loop


def get_phase_library() -> PhaseLibrary:
  if _phase_library is None:
    raise RuntimeError("Phase library has not been initialized")
  return _phase_library


def get_recent_metrics() -> RecentGlobalMetrics:
  if _recent_metrics is None:
    raise RuntimeError("Recent metrics store has not been initialized")
  return _recent_metrics


app.include_router(health.router)
app.include_router(simulator_ingest.router)
app.include_router(graph_snapshot.router)

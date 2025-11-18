"""
Copilot instructions:

Implement the Monitor component for the MAPE-K loop.

The Monitor is responsible for:
- Receiving snapshots from the simulator (SimulatorSnapshot).
- Updating the shared RuntimeGraph with fresh dynamic edge metrics.
- Optionally smoothing noisy signals (e.g., queue length, delay) over a small window.
- Recording global metrics into the database.

Constraints:
- The Monitor must only use information that the simulator can realistically provide:
  - per-edge EdgeMetrics (queue_length_veh, mean_delay_s, spillback, incident, throughput_veh)
  - optional global metrics (avg_trip_time_s, p95_trip_time_s, etc.)
- The Monitor does NOT compute edge costs w_e(t); that is the job of Analyze.

Implementation details:

1) Define a Monitor class:

   class Monitor:
       def __init__(self, runtime_graph: RuntimeGraph, db_session_factory):
           - store the runtime_graph (shared RuntimeGraph instance)
           - store a db_session_factory (callable that returns a SQLAlchemy session)

       async def handle_snapshot(self, snapshot: SimulatorSnapshot) -> None:
           - For each EdgeMetrics in snapshot.edges:
               - map edge_id to the edge in RuntimeGraph
               - call runtime_graph.update_edge_metrics(...) with:
                   queue = edge_metrics.queue_length_veh
                   delay = edge_metrics.mean_delay_s
                   spillback = edge_metrics.spillback
                   incident = edge_metrics.incident
                   throughput = edge_metrics.throughput_veh
           - If snapshot.globals is not None:
               - open a db session from db_session_factory
               - persist the global metrics into a simple "cycle_metrics" table
                 (you can create a placeholder ORM model or TODO for now)
               - commit and close the session
           - Do not compute costs or make planning decisions here.

2) For now, implement only simple "last value wins" updates (no smoothing).
   We can add smoothing windows later in Analyze or an extended Monitor.

3) Expose a helper function:

   def get_monitor_singleton() -> Monitor:
       - This can be wired up from FastAPI startup to share a single Monitor instance.

Make sure to import:
- RuntimeGraph from app.models.graph_runtime
- SimulatorSnapshot from app.adapters.simulator_client
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

import logging

from app.adapters.simulator_client import SimulatorSnapshot
from app.models.graph_runtime import RuntimeGraph

logger = logging.getLogger(__name__)


@dataclass
class CycleMetricRecord:
    """Minimal record representing a row in the cycle_metrics table."""

    __tablename__ = "cycle_metrics"

    timestamp: datetime
    avg_trip_time_s: Optional[float]
    p95_trip_time_s: Optional[float]
    total_spillbacks: Optional[int]
    incident_count: Optional[int]


SessionFactory = Callable[[], Any]


class Monitor:
    def __init__(
        self,
        runtime_graph: RuntimeGraph,
        db_session_factory: Optional[SessionFactory],
        *,
        post_update_hook: Optional[Callable[[], None]] = None,
    ) -> None:
        self._runtime_graph = runtime_graph
        self._db_session_factory = db_session_factory
        self._logger = logger
        self._post_update_hook = post_update_hook

    @property
    def runtime_graph(self) -> RuntimeGraph:
        return self._runtime_graph

    async def handle_snapshot(self, snapshot: SimulatorSnapshot) -> None:
        """Process a simulator snapshot and update the runtime graph and metrics store."""

        for edge_metrics in snapshot.edges:
            self._runtime_graph.update_edge_metrics(
                edge_metrics.edge_id,
                queue=edge_metrics.queue_length_veh,
                delay=edge_metrics.mean_delay_s,
                spillback=edge_metrics.spillback,
                incident=edge_metrics.incident,
                throughput=edge_metrics.throughput_veh,
            )

        if snapshot.globals is not None:
            self._persist_global_metrics(snapshot)

        self._run_post_update_hook()

    def register_post_update_hook(self, hook: Callable[[], None]) -> None:
        self._post_update_hook = hook

    def _run_post_update_hook(self) -> None:
        if self._post_update_hook is None:
            return
        try:
            self._post_update_hook()
        except Exception:  # pragma: no cover - defensive guard
            self._logger.exception("Post-update hook failed")

    def _persist_global_metrics(self, snapshot: SimulatorSnapshot) -> None:
        if snapshot.globals is None:
            return

        if self._db_session_factory is None:
            self._logger.debug("No DB session factory configured; skipping global metric persistence")
            return

        try:
            session = self._db_session_factory()
        except Exception:  # pragma: no cover - defensive guard
            self._logger.exception("Failed to create DB session")
            return

        snapshot_globals = snapshot.globals
        record = CycleMetricRecord(
            timestamp=snapshot.timestamp,
            avg_trip_time_s=snapshot_globals.avg_trip_time_s,
            p95_trip_time_s=snapshot_globals.p95_trip_time_s,
            total_spillbacks=snapshot_globals.total_spillbacks,
            incident_count=snapshot_globals.incident_count,
        )

        try:
            add = getattr(session, "add", None)
            if callable(add):
                add(record)

            commit = getattr(session, "commit", None)
            if callable(commit):
                commit()
        except Exception:
            rollback = getattr(session, "rollback", None)
            if callable(rollback):
                rollback()
            self._logger.exception("Failed to persist cycle metrics")
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()


_monitor_singleton: Optional[Monitor] = None


def set_monitor_singleton(monitor: Monitor) -> None:
    global _monitor_singleton
    _monitor_singleton = monitor


def get_monitor_singleton() -> Monitor:
    if _monitor_singleton is None:
        raise RuntimeError("Monitor singleton has not been initialized")
    return _monitor_singleton

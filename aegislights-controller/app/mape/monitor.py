from __future__ import annotations

from typing import Callable, Optional

import logging
from sqlalchemy.orm import Session

from app.adapters.simulator_client import SimulatorSnapshot
from app.models.db_models import CycleMetricRecord
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import GlobalMetricsSnapshot, RecentGlobalMetrics

logger = logging.getLogger(__name__)


SessionFactory = Callable[[], Session]


class Monitor:
    def __init__(
        self,
        runtime_graph: RuntimeGraph,
        db_session_factory: Optional[SessionFactory],
        *,
        recent_metrics: Optional[RecentGlobalMetrics] = None,
        post_update_hook: Optional[Callable[[], None]] = None,
    ) -> None:
        self._runtime_graph = runtime_graph
        self._db_session_factory = db_session_factory
        self._logger = logger
        self._recent_metrics = recent_metrics
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
            self._update_recent_metrics(snapshot)
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
        if snapshot.globals is None or self._db_session_factory is None:
            return

        snapshot_globals = snapshot.globals
        session: Session
        try:
            session = self._db_session_factory()
        except Exception:  # pragma: no cover - defensive guard
            self._logger.exception("Failed to create DB session")
            return

        record = CycleMetricRecord(
            timestamp=snapshot.timestamp,
            avg_trip_time_s=snapshot_globals.avg_trip_time_s,
            p95_trip_time_s=snapshot_globals.p95_trip_time_s,
            total_spillbacks=snapshot_globals.total_spillbacks,
            incident_count=snapshot_globals.incident_count,
        )

        try:
            session.add(record)
            session.commit()
        except Exception:
            session.rollback()
            self._logger.exception("Failed to persist cycle metrics")
        finally:
            session.close()

    def _update_recent_metrics(self, snapshot: SimulatorSnapshot) -> None:
        if self._recent_metrics is None or snapshot.globals is None:
            return
        globals_payload = snapshot.globals
        snapshot_obj = GlobalMetricsSnapshot(
            timestamp=snapshot.timestamp,
            avg_trip_time_s=globals_payload.avg_trip_time_s,
            p95_trip_time_s=globals_payload.p95_trip_time_s,
            total_spillbacks=globals_payload.total_spillbacks,
            incident_count=globals_payload.incident_count,
        )
        self._recent_metrics.update(snapshot_obj)


_monitor_singleton: Optional[Monitor] = None


def set_monitor_singleton(monitor: Monitor) -> None:
    global _monitor_singleton
    _monitor_singleton = monitor


def get_monitor_singleton() -> Monitor:
    if _monitor_singleton is None:
        raise RuntimeError("Monitor singleton has not been initialized")
    return _monitor_singleton

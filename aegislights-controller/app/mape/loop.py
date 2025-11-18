from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.adapters.simulator_client import SimulatorClient
from app.mape.analyze import Analyzer
from app.mape.execute import Executor
from app.mape.monitor import Monitor
from app.mape.plan import Planner
from app.models.goals import AdaptationGoals
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import MAPEWorkingState, RecentGlobalMetrics

logger = logging.getLogger(__name__)


class MAPELoop:
    """Coordinates the Monitor→Analyze→Plan→Execute cycle."""

    def __init__(
        self,
        runtime_graph: RuntimeGraph,
        working_state: MAPEWorkingState,
        goals: AdaptationGoals,
        analyzer: Analyzer,
        planner: Planner,
        executor: Executor,
        *,
        monitor: Optional[Monitor] = None,
        simulator_client: Optional[SimulatorClient] = None,
        recent_metrics: Optional[RecentGlobalMetrics] = None,
        interval_seconds: float = 10.0,
    ) -> None:
        self._runtime_graph = runtime_graph
        self._working_state = working_state
        self._goals = goals
        self._analyzer = analyzer
        self._planner = planner
        self._executor = executor
        self._monitor = monitor
        self._simulator_client = simulator_client
        self._recent_metrics = recent_metrics
        self._interval_seconds = interval_seconds
        self._running = False

    async def step(self) -> None:
        try:
            await self._poll_simulator()
            self._observe_reward()
            self._analyzer.analyze()
            actions = self._planner.plan()
            self._executor.apply_actions(actions)
            self._executor.rollback_if_needed()
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("MAPE loop step failed")

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            await self.step()
            await asyncio.sleep(self._interval_seconds)

    def stop(self) -> None:
        self._running = False

    async def _poll_simulator(self) -> None:
        if self._simulator_client is None or self._monitor is None:
            return
        snapshot = self._simulator_client.fetch_snapshot()
        if snapshot is None:
            return
        await self._monitor.handle_snapshot(snapshot)

    def _observe_reward(self) -> None:
        if self._recent_metrics is None:
            return
        metrics = self._recent_metrics.to_metric_dict()
        if not metrics:
            return
        self._planner.observe_outcome(metrics)


def start_mape_loop(loop: MAPELoop) -> asyncio.Task:
    return asyncio.create_task(loop.run_forever())

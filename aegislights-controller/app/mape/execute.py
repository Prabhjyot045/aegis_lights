"""
Copilot instructions:

Implement the Execute component for the MAPE-K loop.

Purpose:
- Take the plan decisions from the Planner (IntersectionPlanAction objects).
- Apply them to the simulator via the SimulatorClient.
- Enforce simple safety/rollback behavior on the controller side.

Constraints:
- Execute should NOT recompute plans or metrics.
- It should not directly mutate the RuntimeGraph beyond optional bookkeeping
  (e.g., storing "current_plan_id" on intersections).
- It must only talk to the simulator through the SimulatorClient interface.

Assumptions:
- The simulator exposes an actuation API that can be called once per control cycle:
    SimulatorClient.apply_signal_plan(intersection_id: str, plan_id: str) -> None
  For now, this method can be a stub or simple logger.

Implementation details:

1) Import:
   - dataclass IntersectionPlanAction from app.mape.plan
   - RuntimeGraph from app.models.graph_runtime
   - SimulatorClient from app.adapters.simulator_client
   - typing: list
   - logging

2) Implement an Executor class:

   class Executor:
       def __init__(self, runtime_graph: RuntimeGraph, simulator_client: SimulatorClient):
           - store references
           - maintain a simple in-memory dict:
               self._last_applied_plan: dict[str, str]  # intersection_id -> plan_id

       def apply_actions(self, actions: list[IntersectionPlanAction]) -> None:
           - For each action:
               - Call simulator_client.apply_signal_plan(action.intersection_id, action.plan_id)
               - Update self._last_applied_plan[intersection_id] = plan_id
               - Optionally, set a node attribute on the graph:
                   runtime_graph.graph.nodes[intersection_id]["current_plan_id"] = plan_id
           - This corresponds to applying the new configuration at the next cycle boundary.

       def rollback_if_needed(self) -> None:
           - Placeholder for rollback logic:
               - For now, just log that rollback is not implemented or
                 provide a stub method that can be called from the MAPE loop.
               - Later, this method could:
                   - inspect recent utility / metrics
                   - if degraded, call apply_signal_plan with previous plan_ids from
                     self._last_applied_plan or a known "safe" plan.

3) Do NOT introduce delays or blocking behavior here.
   Timing (control-cycle synchronization) will be handled by the MAPE loop orchestrator.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.adapters.simulator_client import SimulatorClient
from app.models.goals import AdaptationGoals
from app.mape.plan import IntersectionPlanAction
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import RecentGlobalMetrics

logger = logging.getLogger(__name__)


class Executor:
  def __init__(
    self,
    runtime_graph: RuntimeGraph,
    simulator_client: SimulatorClient,
    *,
    goals: AdaptationGoals,
    recent_metrics: Optional[RecentGlobalMetrics] = None,
    rollback_threshold: float = 0.25,
    rollback_patience_cycles: int = 2,
  ) -> None:
    self._runtime_graph = runtime_graph
    self._simulator_client = simulator_client
    self._last_applied_plan: Dict[str, str] = {}
    self._last_safe_plan: Dict[str, str] = {}
    self._goals = goals
    self._recent_metrics = recent_metrics
    self._rollback_threshold = rollback_threshold
    self._rollback_patience_cycles = max(1, rollback_patience_cycles)
    self._low_utility_streak = 0

  def apply_actions(self, actions: List[IntersectionPlanAction]) -> None:
    for action in actions:
      logger.info(
        "Applying plan", extra={"intersection_id": action.intersection_id, "plan_id": action.plan_id, "score": action.score}
      )
      self._simulator_client.apply_signal_plan(action.intersection_id, action.plan_id)
      self._last_applied_plan[action.intersection_id] = action.plan_id
      graph = self._runtime_graph.graph
      if not graph.has_node(action.intersection_id):
        graph.add_node(action.intersection_id)
      graph.nodes[action.intersection_id]["current_plan_id"] = action.plan_id
      if action.reason:
        graph.nodes[action.intersection_id]["plan_reason"] = action.reason

  def rollback_if_needed(self) -> None:
    utility = self._current_utility()
    if utility is None:
      return
    if utility >= self._rollback_threshold:
      self._low_utility_streak = 0
      if self._last_applied_plan:
        self._last_safe_plan = dict(self._last_applied_plan)
      return

    self._low_utility_streak += 1
    logger.warning(
      "Utility below rollback threshold",
      extra={
        "utility": utility,
        "threshold": self._rollback_threshold,
        "streak": self._low_utility_streak,
      },
    )
    if self._low_utility_streak < self._rollback_patience_cycles:
      return
    self._perform_rollback(reason=f"Utility {utility:.3f} < {self._rollback_threshold:.3f}")
    self._low_utility_streak = 0

  def get_last_applied_plans(self) -> Dict[str, str]:
    return dict(self._last_applied_plan)

  def _current_utility(self) -> Optional[float]:
    if self._recent_metrics is None:
      return None
    metrics = self._recent_metrics.to_metric_dict()
    if not metrics:
      return None
    try:
      return self._goals.compute_utility(metrics)
    except Exception:  # pragma: no cover - defensive guard
      logger.exception("Failed to compute utility for rollback check")
      return None

  def _perform_rollback(self, *, reason: str) -> None:
    if not self._last_safe_plan:
      logger.warning("Rollback requested but no safe plan recorded")
      return
    logger.error("Rolling back to last safe plan", extra={"reason": reason, "count": len(self._last_safe_plan)})
    for intersection_id, plan_id in self._last_safe_plan.items():
      try:
        self._simulator_client.apply_signal_plan(intersection_id, plan_id)
      except Exception:  # pragma: no cover - defensive guard
        logger.exception(
          "Failed to rollback intersection",
          extra={"intersection_id": intersection_id, "plan_id": plan_id},
        )
        continue
      graph = self._runtime_graph.graph
      if not graph.has_node(intersection_id):
        graph.add_node(intersection_id)
      graph.nodes[intersection_id]["current_plan_id"] = plan_id
      graph.nodes[intersection_id]["plan_reason"] = "rollback"
    self._last_applied_plan = dict(self._last_safe_plan)

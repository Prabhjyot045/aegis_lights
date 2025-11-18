"""
Copilot instructions:

Implement the Adaptation Goals model for the AegisLights controller.

Purpose:
- Represent the system's adaptation goals (minimize avg trip time, p95 trip time, etc.).
- Provide a utility function that maps observed metrics to a [0, 1] utility score.
- This will be used later by Analyze and Plan to evaluate performance.

Requirements:

1) Define an enum or string constants for metric identifiers:
   - "avg_trip_time_s"
   - "p95_trip_time_s"
   - "incident_clear_time_s" (optional)
   - "spillbacks_per_hour"
   - "avg_stops_per_trip" (optional / placeholder)

2) Define a Pydantic model or dataclass `GoalDefinition`:
   - metric_id: str
   - weight: float (0..1, sum of weights should be 1 across all goals)
   - target: float | None (desired value, e.g., 600.0 seconds)
   - direction: Literal["minimize", "maximize"]

3) Implement a class `AdaptationGoals` with:
   - an internal list of GoalDefinition objects.
   - a constructor that can either:
       - accept the list directly, or
       - create a default set of goals with reasonable weights and targets.
   - a method `compute_utility(metrics: dict[str, float]) -> float`:
       - metrics is a mapping from metric_id to observed value.
       - For each goal:
           - If direction == "minimize":
               - map metric value to a normalized "goodness" in [0,1], where:
                   - values <= target -> near 1
                   - values >> target -> closer to 0
           - If direction == "maximize": reverse the mapping.
       - Combine individual utilities with a weighted sum:
           U = sum(weight_i * u_i)
       - If a metric is missing from `metrics`, skip it or treat its utility as 0.

4) Provide a helper `default_goals()` function that returns an AdaptationGoals instance
   with a reasonable default configuration for:
   - avg_trip_time_s
   - p95_trip_time_s
   - spillbacks_per_hour

5) Keep the implementation simple and deterministic. Do NOT access the database here.
   This class should be a pure in-memory model that other components can instantiate
   and use.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Literal, Mapping, Optional, Sequence


MetricDirection = Literal["minimize", "maximize"]


class MetricId(str, Enum):
    AVG_TRIP_TIME_S = "avg_trip_time_s"
    P95_TRIP_TIME_S = "p95_trip_time_s"
    INCIDENT_CLEAR_TIME_S = "incident_clear_time_s"
    SPILLBACKS_PER_HOUR = "spillbacks_per_hour"
    AVG_STOPS_PER_TRIP = "avg_stops_per_trip"


@dataclass(frozen=True)
class GoalDefinition:
    metric_id: str
    weight: float
    target: Optional[float]
    direction: MetricDirection


class AdaptationGoals:
    """Utility aggregation for adaptation goals."""

    def __init__(self, goals: Optional[Sequence[GoalDefinition]] = None) -> None:
        self._goals: List[GoalDefinition] = list(goals) if goals else []

    @property
    def goals(self) -> Sequence[GoalDefinition]:
        return tuple(self._goals)

    def compute_utility(self, metrics: Mapping[str, float]) -> float:
        if not self._goals:
            return 0.0

        applicable_goals = [goal for goal in self._goals if goal.weight > 0]
        if not applicable_goals:
            return 0.0

        weight_sum = sum(goal.weight for goal in applicable_goals)
        if weight_sum == 0:
            return 0.0

        utility_accum = 0.0
        for goal in applicable_goals:
            metric_value = metrics.get(goal.metric_id)
            if metric_value is None:
                continue
            goal_utility = self._goal_utility(goal, metric_value)
            utility_accum += goal.weight * goal_utility

        return utility_accum / weight_sum

    def _goal_utility(self, goal: GoalDefinition, value: float) -> float:
        if goal.direction == "minimize":
            return self._minimize_utility(value, goal.target)
        return self._maximize_utility(value, goal.target)

    @staticmethod
    def _minimize_utility(value: float, target: Optional[float]) -> float:
        if target is None:
            return 0.5
        if value <= target:
            return 1.0
        if target <= 0:
            return 0.0
        ratio = target / max(value, 1e-9)
        return max(0.0, min(1.0, ratio))

    @staticmethod
    def _maximize_utility(value: float, target: Optional[float]) -> float:
        if target is None:
            return 0.5
        if value >= target:
            return 1.0
        if target <= 0:
            return 1.0
        ratio = value / target
        return max(0.0, min(1.0, ratio))


def default_goals() -> AdaptationGoals:
    defaults = [
        GoalDefinition(metric_id=MetricId.AVG_TRIP_TIME_S.value, weight=0.4, target=600.0, direction="minimize"),
        GoalDefinition(metric_id=MetricId.P95_TRIP_TIME_S.value, weight=0.4, target=900.0, direction="minimize"),
        GoalDefinition(metric_id=MetricId.SPILLBACKS_PER_HOUR.value, weight=0.2, target=2.0, direction="minimize"),
    ]
    return AdaptationGoals(defaults)

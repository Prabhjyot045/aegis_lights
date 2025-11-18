from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.models.goals import AdaptationGoals
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import IntersectionContext, MAPEWorkingState
from app.models.phase_library import PhaseLibrary, PhasePlan


@dataclass(frozen=True)
class IntersectionPlanAction:
  intersection_id: str
  plan_id: str
  score: float | None = None
  reason: str | None = None


class FeatureEncoder:
  """Stable feature-to-vector encoder for intersection contexts."""

  def __init__(self) -> None:
    self._feature_index: Dict[str, int] = {}

  def encode(self, features: Dict[str, float | int | bool]) -> np.ndarray:
    if not features:
      return np.zeros(0, dtype=float)
    for key in sorted(features.keys()):
      if key not in self._feature_index:
        self._feature_index[key] = len(self._feature_index)
    vec = np.zeros(len(self._feature_index), dtype=float)
    for key, value in features.items():
      index = self._feature_index[key]
      if isinstance(value, bool):
        vec[index] = 1.0 if value else 0.0
      else:
        vec[index] = float(value)
    return vec


class BanditPolicy:
  def select_action(self, intersection_id: str, context_vec: np.ndarray, candidate_ids: List[str]) -> str:
    raise NotImplementedError

  def observe(
    self,
    intersection_id: str,
    context_vec: np.ndarray,
    action_id: str,
    reward: float,
  ) -> None:
    raise NotImplementedError


class EpsilonGreedyBandit(BanditPolicy):
  """Intersection-level epsilon-greedy policy with incremental value updates."""

  def __init__(self, epsilon: float = 0.1) -> None:
    self.epsilon = epsilon
    self._values: Dict[Tuple[str, str], Tuple[int, float]] = {}

  def select_action(self, intersection_id: str, context_vec: np.ndarray, candidate_ids: List[str]) -> str:
    import random

    if not candidate_ids:
      raise ValueError("candidate_ids must not be empty")
    if random.random() < self.epsilon:
      return random.choice(candidate_ids)
    best_id = candidate_ids[0]
    best_value = float("-inf")
    for plan_id in candidate_ids:
      count, value = self._values.get((intersection_id, plan_id), (0, 0.0))
      if value > best_value:
        best_value = value
        best_id = plan_id
    return best_id

  def observe(self, intersection_id: str, context_vec: np.ndarray, action_id: str, reward: float) -> None:
    key = (intersection_id, action_id)
    count, value = self._values.get(key, (0, 0.0))
    new_count = count + 1
    new_value = value + (reward - value) / float(new_count)
    self._values[key] = (new_count, new_value)


class Planner:
  def __init__(
    self,
    runtime_graph: RuntimeGraph,
    working_state: MAPEWorkingState,
    goals: AdaptationGoals,
    phase_library: PhaseLibrary,
    bandit: Optional[BanditPolicy] = None,
  ) -> None:
    self._runtime_graph = runtime_graph
    self._working_state = working_state
    self._goals = goals
    self._phase_library = phase_library
    self._bandit: BanditPolicy = bandit or EpsilonGreedyBandit()
    self._feature_encoder = FeatureEncoder()
    self._last_actions: List[Tuple[str, np.ndarray, str]] = []

  def plan(self) -> List[IntersectionPlanAction]:
    contexts = self._working_state.get_intersection_contexts()
    self._last_actions.clear()
    actions: List[IntersectionPlanAction] = []
    for intersection_id, context in contexts.items():
      plans = self._phase_library.get_plans_for_intersection(intersection_id)
      if not plans:
        continue
      context_vec = self._feature_encoder.encode(context.features)
      candidate_ids = [plan.plan_id for plan in plans]
      chosen_id = self._bandit.select_action(intersection_id, context_vec, candidate_ids)
      actions.append(
        IntersectionPlanAction(
          intersection_id=intersection_id,
          plan_id=chosen_id,
          score=self._estimate_score(chosen_id, context, plans),
          reason=None,
        )
      )
      self._last_actions.append((intersection_id, context_vec.copy(), chosen_id))
    return actions

  def observe_outcome(self, metrics: Dict[str, float]) -> None:
    if not self._last_actions:
      return
    reward_value = self._goals.compute_utility(metrics)
    if reward_value is None:
      self._last_actions.clear()
      return
    reward = float(reward_value)
    for intersection_id, context_vec, action_id in self._last_actions:
      self._bandit.observe(intersection_id, context_vec, action_id, reward)
    self._last_actions.clear()

  def _estimate_score(
    self,
    plan_id: str,
    context: IntersectionContext,
    plans: Sequence[PhasePlan],
  ) -> float:
    features = context.features
    queue_sum = float(features.get("incoming_queue_sum", 0.0) or 0.0)
    delay_sum = float(features.get("incoming_delay_sum", 0.0) or 0.0)
    incidents = int(features.get("incoming_incidents", 0) or 0)
    spillbacks = int(features.get("incoming_spillbacks", 0) or 0)
    score = 0.0
    plan_tags = self._plan_tags(plan_id, plans)
    if "incident_mode" in plan_tags and (incidents > 0 or spillbacks > 0):
      score += 2.0
    if "main_arterial_bias" in plan_tags:
      score += queue_sum * 0.02
    if "default" in plan_tags:
      score += 0.1 + min(delay_sum, 60.0) * 0.002
    return score

  @staticmethod
  def _plan_tags(plan_id: str, plans: Sequence[PhasePlan]) -> Sequence[str]:
    for plan in plans:
      if plan.plan_id == plan_id:
        return plan.tags
    return ()

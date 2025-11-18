"""
Copilot instructions:

Implement a simple in-memory Phase / Plan library for the AegisLights controller.

Purpose:
- Represent the set of safe, pre-verified signal timing plans for each intersection.
- Provide a query API for the Planner to fetch candidate plan_ids for a given intersection.
- Keep this in-memory and configuration-based for now (no DB I/O here).

Additional refinement:
- The Planner will use this library instead of hard-coded plan IDs, and the
   bandit policy will consume its plan identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class PhasePlan:
   plan_id: str
   intersection_id: str
   description: Optional[str] = None
   tags: List[str] = field(default_factory=list)
   metadata: Dict[str, Any] = field(default_factory=dict)


class PhaseLibrary:
   def __init__(self, plans: Optional[Iterable[PhasePlan]] = None) -> None:
      self._plans_by_intersection: Dict[str, List[PhasePlan]] = {}
      self._plans_by_id: Dict[str, PhasePlan] = {}
      initial_plans = list(plans) if plans is not None else self._default_plans()
      for plan in initial_plans:
         self._add_plan(plan)

   def get_plans_for_intersection(self, intersection_id: str) -> List[PhasePlan]:
      plans = self._plans_by_intersection.get(intersection_id)
      if plans:
         return list(plans)
      fallback = PhasePlan(
         plan_id=f"{intersection_id}_default",
         intersection_id=intersection_id,
         description="Fallback default plan",
         tags=["default"],
         metadata={"cycle_length_s": 90},
      )
      return [fallback]

   def get_plan(self, plan_id: str) -> Optional[PhasePlan]:
      return self._plans_by_id.get(plan_id)

   def _add_plan(self, plan: PhasePlan) -> None:
      self._plans_by_intersection.setdefault(plan.intersection_id, []).append(plan)
      self._plans_by_id[plan.plan_id] = plan

   @staticmethod
   def _default_plans() -> List[PhasePlan]:
      defaults: List[PhasePlan] = []
      for intersection_id in ("I1", "I2", "I3"):
         defaults.extend(
            [
               PhasePlan(
                  plan_id=f"{intersection_id}_default",
                  intersection_id=intersection_id,
                  description="Baseline timing plan",
                  tags=["default"],
                  metadata={"cycle_length_s": 90},
               ),
               PhasePlan(
                  plan_id=f"{intersection_id}_main_road_bias",
                  intersection_id=intersection_id,
                  description="Favor main arterial throughput",
                  tags=["main_arterial_bias"],
                  metadata={"cycle_length_s": 100},
               ),
               PhasePlan(
                  plan_id=f"{intersection_id}_incident_mode",
                  intersection_id=intersection_id,
                  description="Incident management plan",
                  tags=["incident_mode"],
                  metadata={"cycle_length_s": 120},
               ),
            ]
         )
      return defaults
"""
Copilot instructions:

Implement a simple in-memory Phase / Plan library for the AegisLights controller.

Purpose:
- Represent the set of safe, pre-verified signal timing plans for each intersection.
- Provide a query API for the Planner to fetch candidate plan_ids for a given intersection.
- Keep this in-memory and configuration-based for now (no DB I/O here).

Requirements:

1) Define a data model `PhasePlan` using @dataclass or Pydantic:
   - plan_id: str
   - intersection_id: str
   - description: str | None
   - tags: list[str]  # e.g. ["default"], ["main_arterial_bias"], ["incident_mode"]
   - metadata: dict[str, Any] | None  # optional, can hold cycle length, green splits, etc.

2) Implement a class `PhaseLibrary`:

   class PhaseLibrary:
       def __init__(self, plans: list[PhasePlan] | None = None):
           - store plans in an internal dict keyed by intersection_id.
           - if plans is None, create a small default set of plans for a few example intersections,
             e.g. "I1", "I2" with plans:
               - "<intersection>_default"
               - "<intersection>_main_road_bias"
               - "<intersection>_incident_mode"

       def get_plans_for_intersection(self, intersection_id: str) -> list[PhasePlan]:
           - return all PhasePlan objects for that intersection_id.
           - if none exist, return a fallback list with a single default-like plan:
               PhasePlan(plan_id=f"{intersection_id}_default", intersection_id=intersection_id, tags=["default"], ...)

       def get_plan(self, plan_id: str) -> PhasePlan | None:
           - look up a plan by id across all intersections.

3) This module should not import FastAPI, SQLAlchemy, or any MAPE components.
   It is purely a domain model and simple in-memory repository.

4) Later we can replace the internal list with DB-backed initialization, but the interface
   (get_plans_for_intersection, get_plan) should remain stable.
"""

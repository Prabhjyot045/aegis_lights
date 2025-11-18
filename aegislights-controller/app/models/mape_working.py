"""
Copilot instructions:

Implement MAPE working models for the AegisLights controller.

These are runtime models shared across Analyze, Plan, and Execute. They do NOT replace
the graph, but are derived views of it.

Requirements:

1) Define simple Pydantic or dataclass models:

   - HotspotEdge:
       edge_id: str
       cost: float
       queue: float
       delay: float
       spillback: bool
       incident: bool

   - BypassPath:
       id: str
       source: str  # upstream intersection id
       target: str  # downstream intersection id
       edge_ids: list[str]
       total_cost: float

   - IntersectionContext:
       intersection_id: str
       features: dict[str, float | int | bool]
       # features may include local queues, delays, hotspot flags, incident flags, etc.

2) Implement a container class `MAPEWorkingState` that stores:

   - hotspots: list[HotspotEdge]
   - bypass_paths: list[BypassPath]
   - intersection_contexts: dict[str, IntersectionContext]

   Methods:
   - `update_hotspots(hotspots: list[HotspotEdge])`
   - `update_bypass_paths(paths: list[BypassPath])`
   - `update_intersection_contexts(contexts: dict[str, IntersectionContext])`

3) This class should be in-memory only and thread-safe enough for simple use:
   - use a threading.Lock around updates to the collections.

4) The Analyze component will populate MAPEWorkingState.
   The Plan and visualization layers may read from it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, MutableMapping, Sequence, Union


FeatureValue = Union[float, int, bool]


@dataclass(frozen=True)
class HotspotEdge:
   edge_id: str
   cost: float
   queue: float
   delay: float
   spillback: bool
   incident: bool


@dataclass(frozen=True)
class BypassPath:
   id: str
   source: str
   target: str
   edge_ids: List[str]
   total_cost: float


@dataclass(frozen=True)
class IntersectionContext:
   intersection_id: str
   features: Dict[str, FeatureValue] = field(default_factory=dict)


class MAPEWorkingState:
   def __init__(self) -> None:
      self._hotspots: List[HotspotEdge] = []
      self._bypass_paths: List[BypassPath] = []
      self._intersection_contexts: Dict[str, IntersectionContext] = {}
      self._lock = Lock()

   def update_hotspots(self, hotspots: Sequence[HotspotEdge]) -> None:
      with self._lock:
         self._hotspots = list(hotspots)

   def update_bypass_paths(self, paths: Sequence[BypassPath]) -> None:
      with self._lock:
         self._bypass_paths = list(paths)

   def update_intersection_contexts(self, contexts: MutableMapping[str, IntersectionContext]) -> None:
      with self._lock:
         self._intersection_contexts = dict(contexts)

   def get_hotspots(self) -> List[HotspotEdge]:
      with self._lock:
         return list(self._hotspots)

   def get_bypass_paths(self) -> List[BypassPath]:
      with self._lock:
         return list(self._bypass_paths)

   def get_intersection_contexts(self) -> Dict[str, IntersectionContext]:
      with self._lock:
         return dict(self._intersection_contexts)

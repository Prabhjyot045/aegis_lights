from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Dict, List, MutableMapping, Optional, Sequence, Union


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


@dataclass(frozen=True)
class GlobalMetricsSnapshot:
   timestamp: datetime
   avg_trip_time_s: Optional[float] = None
   p95_trip_time_s: Optional[float] = None
   total_spillbacks: Optional[int] = None
   incident_count: Optional[int] = None


class RecentGlobalMetrics:
   def __init__(self) -> None:
      self._latest: Optional[GlobalMetricsSnapshot] = None
      self._lock = Lock()

   def update(self, snapshot: GlobalMetricsSnapshot) -> None:
      with self._lock:
         self._latest = snapshot

   def get_latest(self) -> Optional[GlobalMetricsSnapshot]:
      with self._lock:
         return self._latest

   def to_metric_dict(self) -> Dict[str, float]:
      with self._lock:
         snapshot = self._latest
      if snapshot is None:
         return {}
      metrics: Dict[str, float] = {}
      metrics["avg_trip_time_s"] = float(snapshot.avg_trip_time_s or 0.0)
      metrics["p95_trip_time_s"] = float(snapshot.p95_trip_time_s or 0.0)
      metrics["spillbacks_per_hour"] = float(snapshot.total_spillbacks or 0.0)
      metrics["incident_count"] = float(snapshot.incident_count or 0.0)
      return metrics

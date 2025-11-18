"""
Copilot instructions:

Define data models for snapshots coming from the traffic simulator into the controller.

We assume a PUSH model, where the simulator POSTs a snapshot to a FastAPI endpoint.

Requirements:

1) Use Pydantic BaseModel classes to describe the snapshot:

- EdgeMetrics:
  - edge_id: str
    - unique identifier that matches the edge_id used in RuntimeGraph
  - queue_length_veh: float
  - mean_delay_s: float
  - spillback: bool
  - incident: bool
  - throughput_veh: float

These are all directly measurable from the simulator.

- GlobalMetrics (optional):
  - avg_trip_time_s: float | None
  - p95_trip_time_s: float | None
  - total_spillbacks: int | None
  - incident_count: int | None

These are aggregated by the simulator over a recent time window.

- SimulatorSnapshot:
  - timestamp: datetime
  - edges: list[EdgeMetrics]
  - globals: GlobalMetrics | None

2) Also define a small interface class `SimulatorClient` that encapsulates communication with the simulator.
   For now this class can be a thin wrapper with methods like:
   - `apply_signal_plan(...)` (will be implemented later in Execute)
   - `acknowledge_snapshot(snapshot: SimulatorSnapshot)` (no-op or logging)

The Monitor will only depend on the Pydantic models and not make outbound HTTP calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

import logging
from pydantic import BaseModel


class EdgeMetrics(BaseModel):
  edge_id: str
  queue_length_veh: float
  mean_delay_s: float
  spillback: bool
  incident: bool
  throughput_veh: float


class GlobalMetrics(BaseModel):
  avg_trip_time_s: Optional[float] = None
  p95_trip_time_s: Optional[float] = None
  total_spillbacks: Optional[int] = None
  incident_count: Optional[int] = None


class SimulatorSnapshot(BaseModel):
  timestamp: datetime
  edges: List[EdgeMetrics]
  globals: Optional[GlobalMetrics] = None


class SimulatorClient:
  """Thin wrapper for interacting with the traffic simulator."""

  def __init__(self, *, logger: Optional[logging.Logger] = None) -> None:
    self._logger = logger or logging.getLogger(__name__)

  async def apply_signal_plan(self, plan: Any) -> None:
    """Placeholder for pushing a signal plan back to the simulator."""
    self._logger.info("apply_signal_plan called", extra={"plan": plan})

  def acknowledge_snapshot(self, snapshot: SimulatorSnapshot) -> None:
    """Confirm receipt of a snapshot (currently a no-op)."""
    self._logger.debug("Snapshot acknowledged", extra={"edge_count": len(snapshot.edges)})

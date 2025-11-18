"""
Copilot instructions:

Implement a FastAPI router that exposes an endpoint for the simulator to send snapshots
into the controller.

Requirements:

- Use APIRouter from fastapi.
- Define a dependency or global accessor to get the shared Monitor instance.
- Expose a POST endpoint `/simulator/snapshot` that accepts a SimulatorSnapshot body.

Example shape:

router = APIRouter(prefix="/simulator", tags=["simulator"])

@router.post("/snapshot", status_code=202)
async def ingest_snapshot(snapshot: SimulatorSnapshot, monitor: Monitor = Depends(get_monitor)):
    - Call await monitor.handle_snapshot(snapshot)
    - Return a simple JSON payload like {"status": "accepted"}

Implementation details:

- Import:
  - APIRouter, Depends from fastapi
  - SimulatorSnapshot from app.adapters.simulator_client
  - Monitor and get_monitor_singleton (or similar) from app.mape.monitor

- This route is the "sensor" side of the MAPE loop: simulator -> Monitor -> RuntimeGraph.

The simulator only needs to know:
- the URL /simulator/snapshot
- the JSON schema for SimulatorSnapshot (already defined in simulator_client.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.simulator_client import SimulatorSnapshot
from app.mape.monitor import Monitor, get_monitor_singleton

router = APIRouter(prefix="/simulator", tags=["simulator"])


@router.post("/snapshot", status_code=202)
async def ingest_snapshot(
  snapshot: SimulatorSnapshot,
  monitor: Monitor = Depends(get_monitor_singleton),
) -> dict[str, str]:
  """Receive a simulator snapshot and hand it to the Monitor."""

  _validate_snapshot(snapshot)
  await monitor.handle_snapshot(snapshot)
  return {"status": "accepted"}


def _validate_snapshot(snapshot: SimulatorSnapshot) -> None:
  if not snapshot.edges:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
      detail="Snapshot must include at least one edge metric",
    )

  for idx, edge in enumerate(snapshot.edges):
    if edge.queue_length_veh < 0 or edge.mean_delay_s < 0 or edge.throughput_veh < 0:
      raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Edge metrics must be non-negative (edge index {idx})",
      )

  if snapshot.globals is None:
    return

  globals_payload = snapshot.globals
  non_negative_fields = (
    "avg_trip_time_s",
    "p95_trip_time_s",
    "total_spillbacks",
    "incident_count",
  )
  for field_name in non_negative_fields:
    value = getattr(globals_payload, field_name)
    if value is not None and value < 0:
      raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Global metric '{field_name}' must be non-negative",
      )

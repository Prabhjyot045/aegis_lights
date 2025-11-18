from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import logging
from urllib.parse import urljoin

import requests
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


@dataclass(frozen=True)
class SimulatorAPIContract:
  """Describes HTTP endpoints exposed by the simulator."""

  base_url: str
  snapshot_path: str
  plan_path_template: str
  api_key: Optional[str] = None

  def snapshot_url(self) -> str:
    return urljoin(self.base_url, self.snapshot_path)

  def plan_url(self, intersection_id: str) -> str:
    path = self.plan_path_template.format(intersection_id=intersection_id)
    return urljoin(self.base_url, path)


class SimulatorClient:
  """Thin wrapper for interacting with the traffic simulator."""

  def __init__(
    self,
    *,
    logger: Optional[logging.Logger] = None,
    fetch_snapshot_fn: Optional[Callable[[], Optional[SimulatorSnapshot]]] = None,
    apply_plan_fn: Optional[Callable[[str, str], None]] = None,
    api_contract: Optional[SimulatorAPIContract] = None,
    request_timeout_s: float = 5.0,
  ) -> None:
    self._logger = logger or logging.getLogger(__name__)
    self._fetch_snapshot_fn = fetch_snapshot_fn
    self._apply_plan_fn = apply_plan_fn
    self._api_contract = api_contract
    self._request_timeout_s = request_timeout_s
    self._http_session: Optional[requests.Session] = None
    if api_contract is not None:
      self._http_session = requests.Session()

  def fetch_snapshot(self) -> Optional[SimulatorSnapshot]:
    """Return the latest simulator snapshot or None if not available."""
    if self._fetch_snapshot_fn is not None:
      snapshot = self._fetch_snapshot_fn()
      if snapshot is None:
        self._logger.debug("Simulator returned no snapshot")
      return snapshot

    if self._api_contract is None or self._http_session is None:
      self._logger.warning("fetch_snapshot called but no simulator transport configured")
      return None

    try:
      response = self._http_session.get(
        self._api_contract.snapshot_url(),
        headers=self._build_headers(),
        timeout=self._request_timeout_s,
      )
      response.raise_for_status()
      payload = response.json()
      snapshot = SimulatorSnapshot.model_validate(payload)
      return snapshot
    except requests.RequestException:
      self._logger.exception("Snapshot fetch failed")
      return None
    except Exception:
      self._logger.exception("Snapshot payload validation failed")
      return None

  def apply_signal_plan(self, intersection_id: str, plan_id: str) -> None:
    """Push a signal plan decision back to the simulator."""
    if self._apply_plan_fn is not None:
      self._apply_plan_fn(intersection_id, plan_id)
      return

    if self._api_contract is None or self._http_session is None:
      self._logger.info(
        "apply_signal_plan invoked (noop)",
        extra={"intersection_id": intersection_id, "plan_id": plan_id},
      )
      return

    url = self._api_contract.plan_url(intersection_id)
    body = {"plan_id": plan_id}
    try:
      response = self._http_session.post(
        url,
        json=body,
        headers=self._build_headers(),
        timeout=self._request_timeout_s,
      )
      response.raise_for_status()
    except requests.RequestException:
      self._logger.exception(
        "Failed to apply plan", extra={"intersection_id": intersection_id, "plan_id": plan_id}
      )

  def acknowledge_snapshot(self, snapshot: SimulatorSnapshot) -> None:
    """Confirm receipt of a snapshot (currently a no-op)."""
    self._logger.debug("Snapshot acknowledged", extra={"edge_count": len(snapshot.edges)})

  def describe_api_contract(self) -> Optional[Dict[str, Any]]:
    if self._api_contract is None:
      return None
    return {
      "base_url": self._api_contract.base_url,
      "snapshot_endpoint": self._api_contract.snapshot_path,
      "plan_endpoint_template": self._api_contract.plan_path_template,
      "api_key_configured": bool(self._api_contract.api_key),
    }

  def close(self) -> None:
    if self._http_session is not None:
      self._http_session.close()
      self._http_session = None

  def _build_headers(self) -> Dict[str, str]:
    headers = {"accept": "application/json"}
    if self._api_contract is not None and self._api_contract.api_key:
      headers["x-api-key"] = self._api_contract.api_key
    return headers

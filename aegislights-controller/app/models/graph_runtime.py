"""
Copilot instructions:

Implement a shared runtime graph model for the AegisLights controller.

Requirements:
- Use networkx.DiGraph internally to represent the traffic network.
- Each node represents an intersection (signal).
- Each directed edge represents an approach/link between intersections.

Static edge attributes (configured at startup, not changed by Monitor):
- capacity: float (vehicles per second)
- free_flow_time: float (seconds at free flow)

Dynamic edge attributes (updated each control cycle by the Monitor):
- queue: float (current queue length in vehicles)
- delay: float (mean delay per vehicle in seconds over the last control interval)
- spillback: bool (True if queue exceeds a spillback threshold)
- incident: bool (True if an incident currently affects this edge)
- throughput: float (vehicles that left the edge per control interval)
- cost: float (edge cost w_e(t), initially 0.0; will be computed in Analyze)

Implement a RuntimeGraph class with:
- an internal DiGraph called `graph`.
- a constructor that starts with an empty graph.
- a method `add_intersection` to add a node with intersection_id and optional attributes.
- a method `add_edge` to add a directed edge with static attributes (capacity, free_flow_time).
- a method `ensure_edge` that creates the edge if it does not exist.
- a method `update_edge_metrics(edge_id: str, *, queue: float, delay: float, spillback: bool, incident: bool, throughput: float)`:
  - edge_id is a string that uniquely identifies the edge (e.g., "A->B").
  - store all dynamic attributes on the edge.
  - if the edge does not exist, create it with default static attributes (capacity=0, free_flow_time=0).

Also implement:
- a method `get_edge_ids()` that returns all edge ids (for convenience).
- a method `to_visualization_snapshot()` that returns a dict with:
  - "nodes": list of { "id": <intersection_id>, **node_attrs }
  - "edges": list of { "id": <edge_id>, "source": from_node, "target": to_node, **edge_attrs }

Make sure RuntimeGraph is thread-safe enough for simple use:
- Use a standard threading.Lock to guard mutations on the networkx graph.
"""

from __future__ import annotations

from threading import Lock
from typing import Any, Dict, Iterable, Tuple

import networkx as nx


def _format_edge_id(source: str, target: str) -> str:
  return f"{source}->{target}"


def _parse_edge_id(edge_id: str) -> Tuple[str, str]:
  try:
    source, target = edge_id.split("->", maxsplit=1)
  except ValueError as exc:  # pragma: no cover - defensive guard
    raise ValueError(f"Invalid edge_id format: {edge_id}") from exc
  return source.strip(), target.strip()


STATIC_EDGE_DEFAULTS = {
  "capacity": 0.0,
  "free_flow_time": 0.0,
}

DYNAMIC_EDGE_DEFAULTS = {
  "queue": 0.0,
  "delay": 0.0,
  "spillback": False,
  "incident": False,
  "throughput": 0.0,
  "cost": 0.0,
}


class RuntimeGraph:
  """Shared runtime representation of the traffic network."""

  def __init__(self) -> None:
    self.graph = nx.DiGraph()
    self._lock = Lock()

  def add_intersection(self, intersection_id: str, **attrs: Any) -> None:
    with self._lock:
      self.graph.add_node(intersection_id, **attrs)

  def add_edge(
    self,
    source: str,
    target: str,
    *,
    capacity: float,
    free_flow_time: float,
    **extra_attrs: Any,
  ) -> None:
    with self._lock:
      self._add_edge_locked(
        source,
        target,
        capacity=capacity,
        free_flow_time=free_flow_time,
        extra_attrs=extra_attrs,
      )

  def ensure_edge(
    self,
    source: str,
    target: str,
    *,
    capacity: float = 0.0,
    free_flow_time: float = 0.0,
  ) -> None:
    with self._lock:
      if self.graph.has_edge(source, target):
        return
      self._add_edge_locked(
        source,
        target,
        capacity=capacity,
        free_flow_time=free_flow_time,
        extra_attrs={},
      )

  def update_edge_metrics(
    self,
    edge_id: str,
    *,
    queue: float,
    delay: float,
    spillback: bool,
    incident: bool,
    throughput: float,
  ) -> None:
    source, target = _parse_edge_id(edge_id)
    with self._lock:
      if not self.graph.has_edge(source, target):
        self._add_edge_locked(
          source,
          target,
          capacity=STATIC_EDGE_DEFAULTS["capacity"],
          free_flow_time=STATIC_EDGE_DEFAULTS["free_flow_time"],
          extra_attrs={"id": edge_id},
        )

      edge_attrs = self.graph[source][target]
      edge_attrs.update(
        {
          "queue": queue,
          "delay": delay,
          "spillback": spillback,
          "incident": incident,
          "throughput": throughput,
        }
      )
      edge_attrs.setdefault("cost", 0.0)

  def get_edge_ids(self) -> Iterable[str]:
    with self._lock:
      return [data.get("id", _format_edge_id(u, v)) for u, v, data in self.graph.edges(data=True)]

  def to_visualization_snapshot(self) -> Dict[str, Any]:
    with self._lock:
      nodes = [{"id": node_id, **attrs} for node_id, attrs in self.graph.nodes(data=True)]
      edges = []
      for source, target, attrs in self.graph.edges(data=True):
        edge_entry = {
          "id": attrs.get("id", _format_edge_id(source, target)),
          "source": source,
          "target": target,
          **attrs,
        }
        edges.append(edge_entry)
    return {"nodes": nodes, "edges": edges}

  def _add_edge_locked(
    self,
    source: str,
    target: str,
    *,
    capacity: float,
    free_flow_time: float,
    extra_attrs: Dict[str, Any],
  ) -> None:
    # Caller must hold _lock.
    self.graph.add_node(source)
    self.graph.add_node(target)
    attrs = {
      **STATIC_EDGE_DEFAULTS,
      **DYNAMIC_EDGE_DEFAULTS,
      "capacity": capacity,
      "free_flow_time": free_flow_time,
      "id": _format_edge_id(source, target),
      **extra_attrs,
    }
    # cost remains writable by Analyze yet defaults to zero here.
    attrs.setdefault("cost", 0.0)
    self.graph.add_edge(source, target, **attrs)

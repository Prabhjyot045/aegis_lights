"""
Copilot instructions:

Implement the Analyze component for the MAPE-K loop.

The Analyze component is responsible for:
- Computing per-edge costs w_e(t) based on dynamic metrics from the RuntimeGraph.
- Identifying hotspot edges (high-cost edges).
- Finding bypass paths around hotspots using k-shortest paths in the graph.
- Building per-intersection context vectors (IntersectionContext) from the graph state.
- Updating the MAPEWorkingState with hotspots, bypass paths, and contexts.

Constraints:
- Analyze must only use data that is available in the RuntimeGraph:
  - dynamic edge attributes: queue, delay, spillback, incident, throughput
  - static attributes: capacity, free_flow_time
- It must NOT query the simulator directly.
- It must NOT perform planning or actuation; it only prepares information.

Implementation details:

1) Import:
   - RuntimeGraph from app.models.graph_runtime
   - MAPEWorkingState, HotspotEdge, BypassPath, IntersectionContext from app.models.mape_working
   - AdaptationGoals (optional, for utility estimation later)
   - networkx as nx

2) Define a configuration dataclass or simple class for cost coefficients:

   class EdgeCostConfig:
       def __init__(self, a: float = 1.0, b: float = 1.0, c: float = 10.0, d: float = 20.0):
           self.a = a  # weight for delay
           self.b = b  # weight for queue
           self.c = c  # penalty for spillback
           self.d = d  # penalty for incident

3) Implement an Analyze class:

   class Analyzer:
       def __init__(self, runtime_graph: RuntimeGraph, working_state: MAPEWorkingState, cost_config: EdgeCostConfig | None = None):
           - store runtime_graph, working_state, cost_config (default if None)

       def compute_edge_costs(self) -> None:
           - For each edge in runtime_graph.graph:
               - read delay, queue, spillback, incident from edge attributes (default to 0 / False)
               - compute:
                   cost = a * delay + b * queue + c * int(spillback) + d * int(incident)
               - store cost on the edge as attribute "cost"
           - This method only updates the graph, not the working_state.

       def detect_hotspots(self, top_k: int = 10, cost_threshold: float | None = None) -> list[HotspotEdge]:
           - Collect all edges with a non-null "cost".
           - Sort by cost descending.
           - If cost_threshold is provided, filter by cost >= threshold.
           - Else take the top_k.
           - Build and return a list[HotspotEdge].

       def find_bypass_paths(self, max_paths_per_hotspot: int = 3) -> list[BypassPath]:
           - For each HotspotEdge in the current hotspots:
               - Identify source and target intersections (edge endpoints).
               - Use networkx to compute up to k-shortest paths between source and target, using "cost" as weight.
               - For each path that does NOT consist solely of the hotspot edge:
                   - compute total_cost as sum of edge "cost" along the path.
                   - create a BypassPath instance.
           - Return the list of BypassPath.

       def build_intersection_contexts(self) -> dict[str, IntersectionContext]:
           - For each intersection node in the graph:
               - Gather basic features:
                   - sum of incoming queue
                   - sum of incoming delay
                   - number of incoming spillback edges
                   - number of incoming incident edges
                   - maybe a boolean "is_on_hotspot_path"
               - Store these in a features dict.
               - Create an IntersectionContext.
           - Return mapping intersection_id -> IntersectionContext.

       def analyze(self) -> None:
           - High-level function that:
               - calls compute_edge_costs()
               - computes hotspots
               - computes bypass paths
               - builds intersection contexts
               - updates the MAPEWorkingState with these results

4) Do NOT reference Plan or Execute from this module.
   Analyzer should be usable independently for testing.

5) Keep the implementation deterministic and side-effect free except for:
   - writing "cost" attributes on the graph
   - updating the MAPEWorkingState.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional, Sequence

import networkx as nx

from app.models.graph_runtime import RuntimeGraph
from app.models.goals import AdaptationGoals, MetricId, default_goals
from app.models.mape_working import (
    BypassPath,
    HotspotEdge,
    IntersectionContext,
    MAPEWorkingState,
)


def _edge_id(source: str, target: str) -> str:
    return f"{source}->{target}"


def _parse_edge_id(edge_id: str) -> tuple[str, str]:
    source, target = edge_id.split("->", maxsplit=1)
    return source, target


@dataclass
class EdgeCostConfig:
    a: float = 1.0  # delay weight
    b: float = 1.0  # queue weight
    c: float = 10.0  # spillback penalty
    d: float = 20.0  # incident penalty


class Analyzer:
    def __init__(
        self,
        runtime_graph: RuntimeGraph,
        working_state: MAPEWorkingState,
        cost_config: Optional[EdgeCostConfig] = None,
        goals: Optional[AdaptationGoals] = None,
    ) -> None:
        self._runtime_graph = runtime_graph
        self._working_state = working_state
        self._cost_config = cost_config or EdgeCostConfig()
        self._goals = goals or default_goals()
        self._last_utility: float = 0.0

    @property
    def last_utility(self) -> float:
        return self._last_utility

    def compute_edge_costs(self) -> None:
        graph = self._runtime_graph.graph
        for source, target, data in graph.edges(data=True):
            delay = float(data.get("delay", 0.0) or 0.0)
            queue = float(data.get("queue", 0.0) or 0.0)
            spillback = 1.0 if data.get("spillback") else 0.0
            incident = 1.0 if data.get("incident") else 0.0

            cost = (
                self._cost_config.a * delay
                + self._cost_config.b * queue
                + self._cost_config.c * spillback
                + self._cost_config.d * incident
            )
            data["cost"] = cost

    def detect_hotspots(
        self,
        *,
        top_k: int = 10,
        cost_threshold: Optional[float] = None,
    ) -> List[HotspotEdge]:
        graph = self._runtime_graph.graph
        scored_edges = []
        for source, target, data in graph.edges(data=True):
            cost = data.get("cost")
            if cost is None:
                continue
            scored_edges.append((cost, source, target, data))

        scored_edges.sort(key=lambda item: item[0], reverse=True)

        hotspots: List[HotspotEdge] = []
        for cost, source, target, attrs in scored_edges:
            if cost_threshold is not None and cost < cost_threshold:
                continue
            edge = HotspotEdge(
                edge_id=_edge_id(source, target),
                cost=cost,
                queue=float(attrs.get("queue", 0.0) or 0.0),
                delay=float(attrs.get("delay", 0.0) or 0.0),
                spillback=bool(attrs.get("spillback", False)),
                incident=bool(attrs.get("incident", False)),
            )
            hotspots.append(edge)
            if cost_threshold is None and len(hotspots) >= top_k:
                break
        return hotspots

    def find_bypass_paths(
        self,
        hotspots: Sequence[HotspotEdge],
        *,
        max_paths_per_hotspot: int = 3,
    ) -> List[BypassPath]:
        graph = self._runtime_graph.graph
        bypass_paths: List[BypassPath] = []
        for hotspot in hotspots:
            try:
                source, target = _parse_edge_id(hotspot.edge_id)
            except ValueError:
                continue

            try:
                path_generator = nx.shortest_simple_paths(graph, source, target, weight="cost")
            except (nx.NetworkXNoPath, nx.NodeNotFound, nx.NetworkXError):
                continue

            path_count = 0
            for path in path_generator:
                if len(path) <= 2:
                    continue  # skip trivial hotspot edge
                edge_ids: List[str] = []
                total_cost = 0.0
                valid_path = True
                for idx in range(len(path) - 1):
                    edge_source, edge_target = path[idx], path[idx + 1]
                    edge_attrs = graph.get_edge_data(edge_source, edge_target)
                    if edge_attrs is None:
                        valid_path = False
                        break
                    edge_ids.append(_edge_id(edge_source, edge_target))
                    total_cost += float(edge_attrs.get("cost", 0.0) or 0.0)
                if not valid_path:
                    continue

                bypass_paths.append(
                    BypassPath(
                        id=f"bp_{hotspot.edge_id}_{path_count}",
                        source=source,
                        target=target,
                        edge_ids=edge_ids,
                        total_cost=total_cost,
                    )
                )
                path_count += 1
                if path_count >= max_paths_per_hotspot:
                    break
        return bypass_paths

    def build_intersection_contexts(
        self,
        hotspots: Sequence[HotspotEdge],
        bypass_paths: Sequence[BypassPath],
    ) -> Dict[str, IntersectionContext]:
        graph = self._runtime_graph.graph
        hotspot_edges = {hotspot.edge_id for hotspot in hotspots}
        bypass_edge_ids = {edge_id for path in bypass_paths for edge_id in path.edge_ids}

        contexts: Dict[str, IntersectionContext] = {}
        for intersection_id in graph.nodes:
            incoming = list(graph.in_edges(intersection_id, data=True))
            queue_sum = sum(float(attrs.get("queue", 0.0) or 0.0) for _, _, attrs in incoming)
            delay_sum = sum(float(attrs.get("delay", 0.0) or 0.0) for _, _, attrs in incoming)
            spillbacks = sum(1 for _, _, attrs in incoming if attrs.get("spillback"))
            incidents = sum(1 for _, _, attrs in incoming if attrs.get("incident"))

            incoming_edge_ids = {_edge_id(src, dst) for src, dst, _ in incoming}
            features = {
                "incoming_queue_sum": queue_sum,
                "incoming_delay_sum": delay_sum,
                "incoming_spillbacks": spillbacks,
                "incoming_incidents": incidents,
                "is_hotspot_node": 1 if incoming_edge_ids & hotspot_edges else 0,
                "is_on_bypass_path": 1 if incoming_edge_ids & bypass_edge_ids else 0,
            }
            contexts[intersection_id] = IntersectionContext(intersection_id=intersection_id, features=features)
        return contexts

    def analyze(self) -> None:
        self.compute_edge_costs()
        hotspots = self.detect_hotspots()
        bypass_paths = self.find_bypass_paths(hotspots)
        contexts = self.build_intersection_contexts(hotspots, bypass_paths)
        self._working_state.update_hotspots(hotspots)
        self._working_state.update_bypass_paths(bypass_paths)
        self._working_state.update_intersection_contexts(contexts)
        self._last_utility = self._goals.compute_utility(self._collect_goal_metrics())

    def _collect_goal_metrics(self) -> Dict[str, float]:
        graph = self._runtime_graph.graph
        delays: List[float] = []
        spillbacks = 0
        for _, _, attrs in graph.edges(data=True):
            delay = attrs.get("delay")
            if delay is not None:
                delays.append(float(delay))
            if attrs.get("spillback"):
                spillbacks += 1

        metrics: Dict[str, float] = {}
        if delays:
            metrics[MetricId.AVG_TRIP_TIME_S.value] = mean(delays)
            metrics[MetricId.P95_TRIP_TIME_S.value] = max(delays)
        metrics[MetricId.SPILLBACKS_PER_HOUR.value] = float(spillbacks)
        return metrics

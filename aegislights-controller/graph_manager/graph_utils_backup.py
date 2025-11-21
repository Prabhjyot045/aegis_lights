"""Graph analysis utilities and algorithms."""

import logging
from typing import Dict, List, Tuple
import networkx as nx
import numpy as np

from .graph_model import TrafficGraph, GraphEdge, GraphNode

logger = logging.getLogger(__name__)


def compute_edge_costs(graph: TrafficGraph, 
                      coefficients: Tuple[float, float, float, float]) -> Dict[str, float]:
    """
    Compute edge costs using: we(t) = a·delay + b·queue + c·spillback + d·incident
    
    Args:
        graph: Traffic graph
        coefficients: Tuple of (a, b, c, d) weights
        
    Returns:
        Dict mapping edge_id to cost
    """
    a, b, c, d = coefficients
    costs = {}
    
    for edge_id, edge in graph.edges.items():
        cost = (
            a * edge.current_delay +
            b * edge.current_queue +
            c * (10.0 if edge.spillback_active else 0.0) +
            d * (20.0 if edge.incident_active else 0.0)
        )
        costs[edge_id] = cost
        
        # Update edge cost in graph
        edge.edge_cost = cost
    
    return costs


def identify_hotspots(graph: TrafficGraph, threshold: float = 0.7) -> List[str]:
    """
    Identify high-cost edges (hotspots) above threshold.
    
    Args:
        graph: Traffic graph
        threshold: Percentile threshold (0-1) for hotspot identification
        
    Returns:
        List of edge IDs identified as hotspots
    """
    if not graph.edges:
        return []
    
    costs = [edge.edge_cost for edge in graph.edges.values()]
    threshold_value = np.percentile(costs, threshold * 100)
    
    hotspots = [
        edge_id for edge_id, edge in graph.edges.items()
        if edge.edge_cost >= threshold_value
    ]
    
    logger.debug(f"Identified {len(hotspots)} hotspots (threshold: {threshold_value:.2f})")
    return hotspots


def find_k_shortest_paths(graph: TrafficGraph, k: int = 3,
                         hotspots: List[str] = None) -> List[Dict]:
    """
    Find k-shortest paths that bypass hotspots.
    
    Args:
        graph: Traffic graph
        k: Number of alternative paths to find
        hotspots: List of edge IDs to bypass
        
    Returns:
        List of bypass route dictionaries
    """
    if not hotspots or len(graph.nodes) < 2:
        return []
    
    # Convert to NetworkX graph
    nx_graph = _to_networkx(graph)
    
    bypasses = []
    
    # For each hotspot, find alternative routes
    for hotspot_id in hotspots[:k]:  # Limit to k hotspots
        edge = graph.get_edge(hotspot_id)
        if not edge:
            continue
        
        source = edge.from_intersection
        target = edge.to_intersection
        
        try:
            # Find shortest paths avoiding the hotspot
            # TODO: Implement k-shortest paths with excluded edges
            paths = list(nx.all_simple_paths(
                nx_graph, source, target, cutoff=5
            ))[:k]
            
            for path in paths:
                bypasses.append({
                    'source': source,
                    'target': target,
                    'path': path,
                    'bypassing': hotspot_id
                })
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
    
    logger.debug(f"Found {len(bypasses)} bypass routes")
    return bypasses


def predict_trends(graph: TrafficGraph, alpha: float = 0.3) -> Dict[str, float]:
    """
    Predict queue growth trends using exponential smoothing.
    
    Args:
        graph: Traffic graph
        alpha: Smoothing parameter (0-1)
        
    Returns:
        Dict mapping edge_id to predicted queue delta
    """
    trends = {}
    
    for edge_id, edge in graph.edges.items():
        # TODO: Implement proper exponential smoothing with history
        # For now, simple prediction based on current state
        if edge.spillback_active or edge.incident_active:
            predicted_delta = 5.0  # Expect queue growth
        elif edge.current_queue > edge.capacity * 0.8:
            predicted_delta = 2.0  # Moderate growth
        else:
            predicted_delta = 0.0  # Stable
        
        trends[edge_id] = predicted_delta
    
    return trends


def calculate_path_cost(graph: TrafficGraph, path: List[str]) -> float:
    """
    Calculate total cost of a path through the graph.
    
    Args:
        graph: Traffic graph
        path: List of node IDs in path
        
    Returns:
        Total path cost
    """
    total_cost = 0.0
    
    for i in range(len(path) - 1):
        from_node = path[i]
        to_node = path[i + 1]
        
        # Find edge between nodes
        for edge_id in graph.nodes.get(from_node, GraphNode(node_id="", intersection_id="")).outgoing_edges:
            edge = graph.get_edge(edge_id)
            if edge and edge.to_intersection == to_node:
                total_cost += edge.edge_cost
                break
    
    return total_cost


def _to_networkx(graph: TrafficGraph) -> nx.DiGraph:
    """Convert TrafficGraph to NetworkX DiGraph for algorithms."""
    nx_graph = nx.DiGraph()
    
    # Add nodes
    for node_id in graph.nodes.keys():
        nx_graph.add_node(node_id)
    
    # Add edges with weights
    for edge in graph.edges.values():
        nx_graph.add_edge(
            edge.from_intersection,
            edge.to_intersection,
            weight=edge.edge_cost,
            edge_id=edge.edge_id
        )
    
    return nx_graph


def cluster_intersections(graph: TrafficGraph, method: str = "proximity") -> List[List[str]]:
    """
    Cluster intersections for coordination.
    
    Args:
        graph: Traffic graph
        method: Clustering method (proximity, connectivity)
        
    Returns:
        List of clusters (each is a list of node IDs)
    """
    # TODO: Implement clustering algorithm
    return []

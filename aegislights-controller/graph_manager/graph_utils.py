"""Graph analysis utilities and algorithms."""

import logging
from typing import Dict, List, Tuple, Optional
import networkx as nx
import numpy as np

from .graph_model import TrafficGraph, GraphEdge, GraphNode
from api.data_schemas import IntersectionData, RoadSegment

logger = logging.getLogger(__name__)


# CityFlow network topology constants
SIGNALIZED_INTERSECTIONS = ['A', 'B', 'C', 'D', 'E']
VIRTUAL_NODES = ['1', '2', '3', '4', '5', '6', '7', '8']

# CityFlow edge definitions (28 total: 12 signalized + 16 virtual)
CITYFLOW_EDGES = {
    # Signalized to signalized (12 edges)
    'AB': ('A', 'B'), 'BA': ('B', 'A'),
    'AC': ('A', 'C'), 'CA': ('C', 'A'),
    'BC': ('B', 'C'), 'CB': ('C', 'B'),
    'BD': ('B', 'D'), 'DB': ('D', 'B'),
    'CE': ('C', 'E'), 'EC': ('E', 'C'),
    'DE': ('D', 'E'), 'ED': ('E', 'D'),
    # Virtual edges (16 edges: 2 per virtual node)
    'A1': ('A', '1'), '1A': ('1', 'A'),
    'A2': ('A', '2'), '2A': ('2', 'A'),
    'B3': ('B', '3'), '3B': ('3', 'B'),
    'B4': ('B', '4'), '4B': ('4', 'B'),
    'C5': ('C', '5'), '5C': ('5', 'C'),
    'C6': ('C', '6'), '6C': ('6', 'C'),
    'D7': ('D', '7'), '7D': ('7', 'D'),
    'E8': ('E', '8'), '8E': ('8', 'E'),
}


def build_network_from_cityflow(cityflow_data: Dict) -> Dict:
    """
    Transform CityFlow raw snapshot into NetworkSnapshot format.
    
    CityFlow provides lane-level data (e.g., AB_0, AB_1). This function:
    1. Aggregates lane data into edge-level metrics
    2. Groups edges by source intersection
    3. Identifies virtual vs signalized nodes
    4. Creates IntersectionData for each node
    
    CityFlow format:
    {
        "time": 123.5,
        "vehicles_count": 150,
        "lane_vehicle_count": {"AB_0": 5, "AB_1": 3, ...},
        "lane_waiting_vehicle_count": {"AB_0": 2, "AB_1": 1, ...},
        "lane_vehicles": [[lane_id, vehicle_id], ...],
        "current_time": 123.5,
        "current_phase": {"A": 0, "B": 2, ...},
        "accident": ["", 0]
    }
    
    Args:
        cityflow_data: Raw data from CityFlow API
        
    Returns:
        Dict with:
            - intersections: Dict[str, IntersectionData]
            - cycle_number: int (derived from time)
            - timestamp: float
    """
    lane_vehicle_count = cityflow_data.get('lane_vehicle_count', {})
    lane_waiting_count = cityflow_data.get('lane_waiting_vehicle_count', {})
    current_phases = cityflow_data.get('current_phase', {})
    current_time = cityflow_data.get('time', cityflow_data.get('current_time', 0.0))
    
    # Aggregate lane data into edges
    edge_data = _aggregate_lane_data_to_edges(lane_vehicle_count, lane_waiting_count)
    
    # Group edges by source intersection
    intersection_edges = _group_edges_by_source(edge_data)
    
    # Build IntersectionData for each node
    intersections = {}
    
    for node_id in SIGNALIZED_INTERSECTIONS + VIRTUAL_NODES:
        outgoing_edges = intersection_edges.get(node_id, [])
        is_virtual = node_id in VIRTUAL_NODES
        current_phase = current_phases.get(node_id) if not is_virtual else None
        
        intersections[node_id] = IntersectionData(
            intersection_id=node_id,
            is_virtual=is_virtual,
            outgoing_roads=outgoing_edges,
            current_phase=current_phase,
            timestamp=current_time
        )
    
    # Derive cycle number from time (assuming 60s cycles)
    cycle_number = int(current_time / 60.0)
    
    logger.debug(f"Transformed CityFlow data: {len(intersections)} nodes, "
                f"{sum(len(i.outgoing_roads) for i in intersections.values())} edges")
    
    return {
        'intersections': intersections,
        'cycle_number': cycle_number,
        'timestamp': current_time
    }


def _aggregate_lane_data_to_edges(lane_vehicle_count: Dict[str, int],
                                  lane_waiting_count: Dict[str, int]) -> Dict[str, Dict]:
    """
    Aggregate lane-level data into edge-level metrics.
    
    CityFlow lanes are named like "AB_0", "AB_1". We sum them into "AB".
    
    Args:
        lane_vehicle_count: Dict of lane_id -> vehicle count
        lane_waiting_count: Dict of lane_id -> waiting vehicle count
        
    Returns:
        Dict of edge_id -> {queue, waiting, delay, ...}
    """
    edge_aggregates = {}
    
    for lane_id, vehicle_count in lane_vehicle_count.items():
        # Extract edge_id from lane_id (e.g., "AB_0" -> "AB")
        edge_id = lane_id.rsplit('_', 1)[0] if '_' in lane_id else lane_id
        
        waiting_count = lane_waiting_count.get(lane_id, 0)
        
        if edge_id not in edge_aggregates:
            edge_aggregates[edge_id] = {
                'total_vehicles': 0,
                'total_waiting': 0,
                'lane_count': 0
            }
        
        edge_aggregates[edge_id]['total_vehicles'] += vehicle_count
        edge_aggregates[edge_id]['total_waiting'] += waiting_count
        edge_aggregates[edge_id]['lane_count'] += 1
    
    return edge_aggregates


def _group_edges_by_source(edge_data: Dict[str, Dict]) -> Dict[str, List[RoadSegment]]:
    """
    Group edges by their source intersection.
    
    Args:
        edge_data: Dict of edge_id -> aggregated metrics
        
    Returns:
        Dict of intersection_id -> List[RoadSegment]
    """
    intersection_edges = {node: [] for node in SIGNALIZED_INTERSECTIONS + VIRTUAL_NODES}
    
    for edge_id, metrics in edge_data.items():
        if edge_id not in CITYFLOW_EDGES:
            logger.warning(f"Unknown edge_id in CityFlow data: {edge_id}")
            continue
        
        from_int, to_int = CITYFLOW_EDGES[edge_id]
        
        # Estimate delay based on waiting vehicles (simplified)
        # Assume each waiting vehicle adds ~2s delay
        avg_waiting = metrics['total_waiting'] / max(metrics['lane_count'], 1)
        estimated_delay = avg_waiting * 2.0
        
        # Default capacity and free_flow_time (should be from config)
        capacity = 100.0
        free_flow_time = 30.0
        length = 300.0  # Default length in meters
        
        road_segment = RoadSegment(
            edge_id=edge_id,
            from_intersection=from_int,
            to_intersection=to_int,
            capacity=capacity,
            free_flow_time=free_flow_time,
            current_queue=float(metrics['total_vehicles']),
            current_delay=estimated_delay,
            spillback_active=False,  # CityFlow doesn't provide this directly
            incident_active=False,   # CityFlow doesn't provide this directly
            current_flow=0.0,        # Would need historical data
            length=length
        )
        
        intersection_edges[from_int].append(road_segment)
    
    return intersection_edges


def compute_edge_costs(graph: TrafficGraph, 
                      coefficients: Tuple[float, float, float, float]) -> Dict[Tuple[str, str], float]:
    """
    Compute edge costs using: we(t) = a·delay + b·queue + c·spillback + d·incident
    
    Args:
        graph: Traffic graph
        coefficients: Tuple of (a, b, c, d) weights
        
    Returns:
        Dict mapping (from_intersection, to_intersection) to cost
    """
    a, b, c, d = coefficients
    costs = {}
    
    for edge_key, edge in graph.edges.items():
        cost = (
            a * edge.current_delay +
            b * edge.current_queue +
            c * (10.0 if edge.spillback_active else 0.0) +
            d * (20.0 if edge.incident_active else 0.0)
        )
        costs[edge_key] = cost
        
        # Update edge cost in graph
        edge.edge_cost = cost
    
    return costs


def identify_hotspots(graph: TrafficGraph, threshold: float = 0.7) -> List[Tuple[str, str]]:
    """
    Identify high-cost edges (hotspots) above threshold.
    
    Args:
        graph: Traffic graph
        threshold: Percentile threshold (0-1) for hotspot identification
        
    Returns:
        List of edge tuples (from_intersection, to_intersection) identified as hotspots
    """
    if not graph.edges:
        return []
    
    costs = [edge.edge_cost for edge in graph.edges.values()]
    threshold_value = np.percentile(costs, threshold * 100)
    
    hotspots = [
        edge_key for edge_key, edge in graph.edges.items()
        if edge.edge_cost >= threshold_value
    ]
    
    logger.debug(f"Identified {len(hotspots)} hotspots (threshold: {threshold_value:.2f})")
    return hotspots


def find_k_shortest_paths(graph: TrafficGraph, k: int = 3,
                         hotspots: List[Tuple[str, str]] = None) -> List[Dict]:
    """
    Find k-shortest paths that bypass hotspots.
    
    Uses NetworkX to find alternative routes around congested edges.
    
    Args:
        graph: Traffic graph
        k: Number of alternative paths to find per hotspot
        hotspots: List of edge tuples (from, to) to bypass
        
    Returns:
        List of bypass route dictionaries with:
            - source: origin intersection
            - destination: end intersection  
            - path: list of edge tuples forming the path
            - total_cost: sum of edge costs
            - bypasses: hotspot edge being avoided
            - length: number of edges in path
    """
    if not hotspots or len(graph.nodes) < 2:
        return []
    
    # Convert to NetworkX graph
    nx_graph = _to_networkx(graph)
    
    bypasses = []
    
    # For each hotspot, find alternative routes
    for hotspot_edge in hotspots[:min(len(hotspots), 5)]:  # Limit to avoid too many
        from_int, to_int = hotspot_edge
        
        # Find upstream nodes (predecessors of source)
        upstream_nodes = list(nx_graph.predecessors(from_int))
        if not upstream_nodes:
            continue
        
        # Find downstream nodes (successors of destination)
        downstream_nodes = list(nx_graph.successors(to_int))
        if not downstream_nodes:
            continue
        
        # Try to find paths from upstream to downstream that avoid hotspot
        for upstream in upstream_nodes[:2]:  # Limit upstream candidates
            for downstream in downstream_nodes[:2]:  # Limit downstream candidates
                try:
                    # Find k shortest simple paths
                    paths = list(nx.shortest_simple_paths(
                        nx_graph, upstream, downstream, weight='weight'
                    ))
                    
                    # Process up to k paths
                    for path in paths[:k]:
                        # Convert node path to edge path
                        edge_path = []
                        total_cost = 0.0
                        uses_hotspot = False
                        
                        for i in range(len(path) - 1):
                            edge_key = (path[i], path[i+1])
                            edge_path.append(edge_key)
                            
                            # Check if this is the hotspot edge
                            if edge_key == hotspot_edge:
                                uses_hotspot = True
                                break
                            
                            # Accumulate cost
                            edge = graph.get_edge(path[i], path[i+1])
                            if edge:
                                total_cost += edge.edge_cost
                        
                        # Only include if it bypasses the hotspot
                        if not uses_hotspot and len(edge_path) > 0:
                            bypasses.append({
                                'source': upstream,
                                'destination': downstream,
                                'path': edge_path,
                                'total_cost': total_cost,
                                'bypasses': hotspot_edge,
                                'length': len(edge_path)
                            })
                
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                except Exception as e:
                    logger.warning(f"Error finding paths from {upstream} to {downstream}: {e}")
                    continue
    
    logger.debug(f"Found {len(bypasses)} bypass routes for {len(hotspots)} hotspots")
    return bypasses


def predict_trends(graph: TrafficGraph, 
                   cost_history: Dict[Tuple[str, str], List[float]],
                   alpha: float = 0.3) -> Dict[Tuple[str, str], str]:
    """
    Predict traffic trends using exponential smoothing.
    
    Analyzes historical costs to determine if edges are experiencing
    increasing, stable, or decreasing congestion.
    
    Args:
        graph: Traffic graph
        cost_history: Historical costs per edge (from Analyzer)
        alpha: Smoothing factor (0 < alpha < 1), higher = more responsive
        
    Returns:
        Dict mapping edge tuple to trend classification:
            - 'increasing': congestion is growing
            - 'stable': congestion is steady
            - 'decreasing': congestion is reducing
    """
    trends = {}
    
    for edge_key, edge in graph.edges.items():
        # Need at least 3 historical points for trend
        if edge_key not in cost_history or len(cost_history[edge_key]) < 3:
            trends[edge_key] = 'stable'
            continue
        
        history = cost_history[edge_key]
        
        # Apply exponential smoothing
        smoothed = [history[0]]
        for i in range(1, len(history)):
            smoothed_value = alpha * history[i] + (1 - alpha) * smoothed[-1]
            smoothed.append(smoothed_value)
        
        # Compute trend from last 3 smoothed values
        if len(smoothed) >= 3:
            recent_slope = smoothed[-1] - smoothed[-3]
            
            # Classify trend based on slope magnitude
            if recent_slope > 1.0:  # Significant increase
                trends[edge_key] = 'increasing'
            elif recent_slope < -1.0:  # Significant decrease
                trends[edge_key] = 'decreasing'
            else:  # Relatively stable
                trends[edge_key] = 'stable'
        else:
            trends[edge_key] = 'stable'
    
    return trends


def calculate_path_cost(graph: TrafficGraph, path: List[str]) -> float:
    """
    Calculate total cost of a path through the graph.
    
    Args:
        graph: Traffic graph
        path: List of node IDs forming the path
        
    Returns:
        Total path cost (sum of edge costs)
    """
    total_cost = 0.0
    
    for i in range(len(path) - 1):
        from_node = path[i]
        to_node = path[i + 1]
        
        edge = graph.get_edge(from_node, to_node)
        if edge:
            total_cost += edge.edge_cost
    
    return total_cost


def cluster_intersections(graph: TrafficGraph, 
                         intersection_ids: List[str],
                         max_distance: int = 3) -> List[Dict]:
    """
    Cluster intersections for coordinated signal timing.
    
    Groups intersections that are within max_distance hops of each other
    to enable green wave coordination.
    
    Args:
        graph: Traffic graph
        intersection_ids: List of intersection IDs to cluster
        max_distance: Maximum hop distance for grouping
        
    Returns:
        List of coordination group dictionaries with:
            - intersections: list of intersection IDs in group
            - size: number of intersections
            - representative: central intersection (for coordination)
    """
    if len(intersection_ids) < 2:
        return []
    
    # Build NetworkX graph for distance computation (undirected for proximity)
    G = nx.Graph()
    
    for edge_key, edge in graph.edges.items():
        from_int, to_int = edge_key
        G.add_edge(from_int, to_int)
    
    # Compute all-pairs shortest path lengths
    try:
        distances = dict(nx.all_pairs_shortest_path_length(G, cutoff=max_distance))
    except Exception as e:
        logger.warning(f"Error computing distances for clustering: {e}")
        return []
    
    # Group intersections within max_distance
    groups = []
    visited = set()
    
    for int_id in intersection_ids:
        if int_id in visited or int_id not in distances:
            continue
        
        # Find all intersections within max_distance
        group_members = [int_id]
        for other_id in intersection_ids:
            if other_id != int_id and other_id not in visited:
                if other_id in distances.get(int_id, {}):
                    if distances[int_id][other_id] <= max_distance:
                        group_members.append(other_id)
        
        # Mark as visited
        for member in group_members:
            visited.add(member)
        
        # Add group if it has at least 2 members
        if len(group_members) >= 2:
            groups.append({
                'intersections': group_members,
                'size': len(group_members),
                'representative': group_members[0]  # First as representative
            })
    
    logger.debug(f"Clustered {len(intersection_ids)} intersections into {len(groups)} coordination groups")
    return groups


def _to_networkx(graph: TrafficGraph) -> nx.DiGraph:
    """
    Convert TrafficGraph to NetworkX DiGraph for algorithms.
    
    Args:
        graph: Traffic graph to convert
        
    Returns:
        NetworkX directed graph with edge weights
    """
    nx_graph = nx.DiGraph()
    
    # Add nodes
    for node_id in graph.nodes.keys():
        nx_graph.add_node(node_id)
    
    # Add edges with weights (no tuples for GraphML compatibility)
    for edge_key, edge in graph.edges.items():
        from_int, to_int = edge_key
        nx_graph.add_edge(
            from_int,
            to_int,
            weight=edge.edge_cost
        )
    
    return nx_graph


def get_bottleneck_score(graph: TrafficGraph, edge_key: Tuple[str, str]) -> float:
    """
    Calculate bottleneck score for an edge.
    
    Combines queue ratio, delay, and downstream impact to quantify
    how much an edge is constraining network flow.
    
    Args:
        graph: Traffic graph
        edge_key: Edge tuple (from_intersection, to_intersection)
        
    Returns:
        Bottleneck score (higher = more severe bottleneck)
    """
    edge = graph.get_edge(edge_key[0], edge_key[1])
    if not edge:
        return 0.0
    
    # Queue ratio component
    queue_ratio = edge.current_queue / edge.capacity if edge.capacity > 0 else 0.0
    
    # Delay component (normalized)
    delay_score = min(edge.current_delay / 20.0, 1.0)  # Cap at 20s
    
    # Downstream impact (how many edges depend on this)
    to_node = edge.to_node
    downstream_count = len(graph.nodes.get(to_node, GraphNode(node_id="")).outgoing_edges)
    downstream_score = min(downstream_count / 4.0, 1.0)  # Cap at 4 edges
    
    # Combined score
    bottleneck_score = (
        0.4 * queue_ratio +
        0.4 * delay_score +
        0.2 * downstream_score
    )
    
    return bottleneck_score


def export_graph_to_json(graph: TrafficGraph, filepath: str) -> None:
    """
    Export traffic graph to JSON format.
    
    Args:
        graph: Traffic graph to export
        filepath: Output file path
    """
    import json
    
    # Build export structure
    export_data = {
        'nodes': [],
        'edges': [],
        'metadata': {
            'total_nodes': len(graph.nodes),
            'total_edges': len(graph.edges),
            'congested_nodes': len(graph.get_congested_nodes()),
            'spillback_edges': len(graph.get_spillback_edges())
        }
    }
    
    # Export nodes
    for node_id, node in graph.nodes.items():
        export_data['nodes'].append({
            'node_id': node.node_id,
            'intersection_type': node.intersection_type,
            'is_congested': node.is_congested,
            'has_spillback': node.has_spillback,
            'incoming_edges': list(node.incoming_edges),
            'outgoing_edges': list(node.outgoing_edges),
            'current_plan_id': node.current_plan_id,
            'cycle_length': node.cycle_length
        })
    
    # Export edges
    for edge_key, edge in graph.edges.items():
        export_data['edges'].append({
            'from_node': edge.from_node,
            'to_node': edge.to_node,
            'edge_id': edge.edge_id,
            'capacity': edge.capacity,
            'free_flow_time': edge.free_flow_time,
            'length': edge.length,
            'num_lanes': edge.num_lanes,
            'current_delay': edge.current_delay,
            'current_queue': edge.current_queue,
            'current_flow': edge.current_flow,
            'edge_cost': edge.edge_cost,
            'spillback_active': edge.spillback_active,
            'incident_active': edge.incident_active
        })
    
    # Write to file
    with open(filepath, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    logger.info(f"Graph exported to {filepath}")


def export_graph_to_graphml(graph: TrafficGraph, filepath: str) -> None:
    """
    Export traffic graph to GraphML format (NetworkX compatible).
    
    Args:
        graph: Traffic graph to export
        filepath: Output file path
    """
    nx_graph = _to_networkx(graph)
    
    # Add node attributes
    for node_id, node in graph.nodes.items():
        if node_id in nx_graph:
            nx_graph.nodes[node_id]['intersection_type'] = node.intersection_type
            nx_graph.nodes[node_id]['is_congested'] = node.is_congested
            nx_graph.nodes[node_id]['has_spillback'] = node.has_spillback
            nx_graph.nodes[node_id]['current_plan_id'] = node.current_plan_id if node.current_plan_id else ""
            nx_graph.nodes[node_id]['cycle_length'] = node.cycle_length
    
    # Add edge attributes
    for edge_key, edge in graph.edges.items():
        from_node, to_node = edge_key
        if nx_graph.has_edge(from_node, to_node):
            nx_graph.edges[from_node, to_node]['capacity'] = edge.capacity
            nx_graph.edges[from_node, to_node]['delay'] = edge.current_delay
            nx_graph.edges[from_node, to_node]['queue'] = edge.current_queue
            nx_graph.edges[from_node, to_node]['spillback'] = edge.spillback_active
            nx_graph.edges[from_node, to_node]['incident'] = edge.incident_active
    
    nx.write_graphml(nx_graph, filepath)
    logger.info(f"Graph exported to GraphML: {filepath}")


def export_graph_snapshot(graph: TrafficGraph, output_dir: str, cycle: int) -> None:
    """
    Export graph snapshot with cycle information.
    
    Creates both JSON and GraphML exports with cycle number in filename.
    
    Args:
        graph: Traffic graph to export
        output_dir: Output directory
        cycle: Current MAPE-K cycle number
    """
    from pathlib import Path
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Export both formats
    json_path = output_path / f"graph_cycle_{cycle}.json"
    graphml_path = output_path / f"graph_cycle_{cycle}.graphml"
    
    export_graph_to_json(graph, str(json_path))
    export_graph_to_graphml(graph, str(graphml_path))
    
    logger.info(f"Graph snapshot saved for cycle {cycle}")

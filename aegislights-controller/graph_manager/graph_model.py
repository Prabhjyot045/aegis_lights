"""Traffic graph data structure and runtime model."""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class GraphEdge:
    """Represents a directed road edge in the traffic network."""
    
    from_node: str  # Origin intersection ID
    to_node: str    # Destination intersection ID
    
    # Static attributes
    capacity: float = 0.0  # vehicles/second (normalized)
    free_flow_time: float = 0.0  # seconds
    length: float = 0.0  # meters
    num_lanes: int = 1
    
    # Dynamic attributes (updated by Monitor)
    current_queue: float = 0.0  # vehicles
    current_delay: float = 0.0  # seconds/vehicle
    current_flow: float = 0.0  # vehicles/second
    spillback_active: bool = False
    incident_active: bool = False
    
    # Computed attributes (updated by Analyze)
    edge_cost: float = 0.0
    last_updated_cycle: int = 0
    
    @property
    def edge_id(self) -> str:
        """Generate edge ID from intersection IDs."""
        return f"{self.from_node}_{self.to_node}"


@dataclass
class GraphNode:
    """Represents a signalized intersection in the traffic network."""
    
    node_id: str  # Intersection identifier
    intersection_type: str = "signalized"  # signalized, unsignalized, etc.
    
    # Location
    latitude: float = 0.0
    longitude: float = 0.0
    
    # Current signal configuration
    current_plan_id: Optional[str] = None
    green_splits: Dict[str, float] = field(default_factory=dict)
    cycle_length: float = 90.0  # seconds
    offset: float = 0.0  # seconds
    
    # Connected edges (stored as (from, to) tuples)
    incoming_edges: Set[tuple] = field(default_factory=set)
    outgoing_edges: Set[tuple] = field(default_factory=set)
    
    # State
    is_congested: bool = False
    has_spillback: bool = False


class TrafficGraph:
    """
    Runtime model of the traffic network as directed graph G = (V, E).
    Maintains current state of intersections (nodes) and roads (edges).
    """
    
    def __init__(self):
        """Initialize empty traffic graph."""
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        logger.info("Traffic graph initialized")
    
    def add_node(self, node: GraphNode) -> None:
        """Add an intersection node to the graph."""
        self.nodes[node.node_id] = node
        logger.debug(f"Added node: {node.node_id}")
    
    def has_node(self, node_id: str) -> bool:
        """Check if node exists in graph."""
        return node_id in self.nodes
    
    def add_edge(self, edge: GraphEdge) -> None:
        """Add a road edge to the graph."""
        edge_key = (edge.from_node, edge.to_node)
        self.edges[edge_key] = edge
        
        # Update node connections
        if edge.from_node in self.nodes:
            self.nodes[edge.from_node].outgoing_edges.add(edge_key)
        if edge.to_node in self.nodes:
            self.nodes[edge.to_node].incoming_edges.add(edge_key)
        
        logger.debug(f"Added edge: {edge.from_node} -> {edge.to_node}")
    
    def has_edge(self, from_node: str, to_node: str) -> bool:
        """Check if edge exists in graph."""
        return (from_node, to_node) in self.edges
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID."""
        return self.nodes.get(node_id)
    
    def get_edge(self, from_node: str, to_node: str) -> Optional[GraphEdge]:
        """Get edge by intersection IDs."""
        return self.edges.get((from_node, to_node))
    
    def get_neighbors(self, node_id: str) -> List[str]:
        """Get neighbor nodes connected by outgoing edges."""
        node = self.get_node(node_id)
        if not node:
            return []
        
        neighbors = []
        for edge_key in node.outgoing_edges:
            from_node, to_node = edge_key
            neighbors.append(to_node)
        
        return neighbors
    
    def get_all_nodes(self) -> List[GraphNode]:
        """Get all nodes in the graph."""
        return list(self.nodes.values())
    
    def get_all_edges(self) -> List[GraphEdge]:
        """Get all edges in the graph."""
        return list(self.edges.values())
    
    def update_edge_state(self, from_node: str, to_node: str, **kwargs) -> None:
        """Update dynamic attributes of an edge."""
        edge = self.get_edge(from_node, to_node)
        if edge:
            for key, value in kwargs.items():
                if hasattr(edge, key):
                    setattr(edge, key, value)
    
    def update_node_config(self, node_id: str, **kwargs) -> None:
        """Update signal configuration of a node."""
        node = self.get_node(node_id)
        if node:
            for key, value in kwargs.items():
                if hasattr(node, key):
                    setattr(node, key, value)
    
    def get_congested_nodes(self) -> List[GraphNode]:
        """Get all congested nodes."""
        return [node for node in self.nodes.values() if node.is_congested]
    
    def get_spillback_edges(self) -> List[GraphEdge]:
        """Get all edges with active spillback."""
        return [edge for edge in self.edges.values() if edge.spillback_active]
    
    def get_incident_edges(self) -> List[GraphEdge]:
        """Get all edges with active incidents."""
        return [edge for edge in self.edges.values() if edge.incident_active]
    
    def clear(self) -> None:
        """Clear all nodes and edges."""
        self.nodes.clear()
        self.edges.clear()
        logger.info("Traffic graph cleared")
    
    def __repr__(self) -> str:
        return f"TrafficGraph(nodes={len(self.nodes)}, edges={len(self.edges)})"

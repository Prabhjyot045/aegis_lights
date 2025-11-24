"""
Test script for graph visualizer - verifies WSL compatibility and thread safety.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
import logging
from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from graph_manager.graph_visualizer import GraphVisualizer
from config.visualization import VisualizationConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_graph() -> TrafficGraph:
    """Create a simple test graph mimicking CityFlow topology."""
    graph = TrafficGraph()
    
    # Add signalized intersections (A-E)
    for node_id in ['A', 'B', 'C', 'D', 'E']:
        node = GraphNode(node_id)
        graph.add_node(node)
    
    # Add virtual nodes (1-8)
    for node_id in ['1', '2', '3', '4', '5', '6', '7', '8']:
        node = GraphNode(node_id)
        graph.add_node(node)
    
    # Add some test edges
    test_edges = [
        ('1', 'A', 1000, 30.0, 500),
        ('A', 'B', 1200, 35.0, 600),
        ('B', 'C', 1100, 32.0, 550),
        ('C', 'D', 1000, 30.0, 500),
        ('D', 'E', 1150, 33.0, 575),
        ('E', '2', 1000, 28.0, 500),
        ('A', '3', 900, 25.0, 450),
        ('3', 'C', 950, 27.0, 475),
        ('B', '4', 850, 23.0, 425),
        ('4', 'D', 900, 26.0, 450),
    ]
    
    for from_node, to_node, capacity, free_flow_time, length in test_edges:
        edge = GraphEdge(
            edge_id=f"{from_node}{to_node}",
            from_intersection=from_node,
            to_intersection=to_node,
            capacity=capacity,
            free_flow_time=free_flow_time,
            length=length
        )
        graph.add_edge(edge)
    
    logger.info(f"Created test graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    return graph


def simulate_traffic_changes(graph: TrafficGraph, cycle: int):
    """Simulate traffic state changes for visualization testing."""
    import random
    
    for edge in graph.edges.values():
        # Simulate varying queue lengths and delays
        base_queue = 5 + (cycle % 10) * 2
        base_delay = 10 + (cycle % 10) * 3
        
        edge.current_queue = base_queue + random.randint(-2, 5)
        edge.current_delay = base_delay + random.uniform(-2.0, 8.0)
        edge.current_flow = edge.capacity * random.uniform(0.3, 0.9)
        
        # Simulate occasional spillbacks
        if random.random() < 0.1:
            edge.spillback_active = True
            edge.current_queue += 10
        else:
            edge.spillback_active = False
        
        # Simulate rare incidents
        if random.random() < 0.05:
            edge.incident_active = True
            edge.current_delay += 20
        else:
            edge.incident_active = False
        
        # Update edge cost
        edge.edge_cost = (
            1.0 * edge.current_delay +
            0.5 * edge.current_queue +
            10.0 * (1 if edge.spillback_active else 0) +
            20.0 * (1 if edge.incident_active else 0)
        )
    
    # Update node states based on edges
    for node in graph.nodes.values():
        incoming_edges = [e for e in graph.edges.values() if e.to_intersection == node.node_id]
        if incoming_edges:
            avg_queue = sum(e.current_queue for e in incoming_edges) / len(incoming_edges)
            node.is_congested = avg_queue > 10
            node.has_spillback = any(e.spillback_active for e in incoming_edges)


def test_visualizer():
    """Test the graph visualizer with simulated traffic data."""
    logger.info("=" * 60)
    logger.info("Graph Visualizer Test - WSL Compatibility")
    logger.info("=" * 60)
    
    # Create test graph
    graph = create_test_graph()
    
    # Initialize visualizer
    logger.info("Initializing visualizer...")
    visualizer = GraphVisualizer(
        graph=graph,
        record=True,  # Enable frame generation
        output_dir=Path("output/test_visualizations")
    )
    
    # Start visualizer (non-blocking)
    logger.info("Starting visualizer...")
    visualizer.start()
    
    # Simulate 20 cycles of traffic changes
    num_cycles = 20
    logger.info(f"Simulating {num_cycles} cycles...")
    
    for cycle in range(1, num_cycles + 1):
        logger.info(f"\nCycle {cycle}/{num_cycles}")
        
        # Simulate traffic state changes
        simulate_traffic_changes(graph, cycle)
        
        # Calculate mock metrics
        avg_delay = sum(e.current_delay for e in graph.edges.values()) / len(graph.edges)
        incidents = sum(1 for e in graph.edges.values() if e.incident_active)
        spillbacks = sum(1 for e in graph.edges.values() if e.spillback_active)
        
        logger.info(f"  Avg Delay: {avg_delay:.1f}s | Incidents: {incidents} | Spillbacks: {spillbacks}")
        
        # Update visualizer metrics
        visualizer.update_metrics(
            cycle=cycle,
            incidents=incidents,
            adaptations=cycle % 3,  # Mock adaptations
            avg_delay=avg_delay
        )
        
        # Update visualizer graph (renders frame)
        visualizer.update(graph)
        
        # Small delay to simulate MAPE cycle time
        time.sleep(0.1)
    
    # Stop visualizer
    logger.info("\nStopping visualizer...")
    visualizer.stop()
    
    # Check output
    output_dir = Path("output/test_visualizations")
    frames = list(output_dir.glob("network_cycle_*.png"))
    logger.info(f"Generated {len(frames)} visualization frames")
    
    if len(frames) > 0:
        logger.info(f"Sample frame: {frames[0]}")
        logger.info("\n✅ Visualizer test PASSED!")
        logger.info(f"View frames: explorer.exe {output_dir.absolute()}")
        
        # Optionally create video
        try:
            logger.info("\nAttempting to create video with ffmpeg...")
            visualizer.create_video()
        except Exception as e:
            logger.info(f"Video creation skipped: {e}")
    else:
        logger.error("\n❌ Visualizer test FAILED - no frames generated")
        return 1
    
    logger.info("=" * 60)
    logger.info("Test Complete")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(test_visualizer())

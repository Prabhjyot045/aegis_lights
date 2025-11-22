"""Demo script for graph export and visualization features."""

import time
from pathlib import Path

from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from graph_manager.graph_utils import export_graph_snapshot
from graph_manager.graph_visualizer import GraphVisualizer


def create_demo_graph():
    """Create a demo traffic network."""
    graph = TrafficGraph()
    
    # Create a 4-node network
    nodes = [
        GraphNode(node_id="int1", intersection_type="signalized", latitude=43.4723, longitude=-80.5449),
        GraphNode(node_id="int2", intersection_type="signalized", latitude=43.4735, longitude=-80.5430),
        GraphNode(node_id="int3", intersection_type="signalized", latitude=43.4710, longitude=-80.5420),
        GraphNode(node_id="int4", intersection_type="signalized", latitude=43.4698, longitude=-80.5440),
    ]
    
    for node in nodes:
        graph.add_node(node)
    
    # Create edges connecting the nodes
    edges = [
        # Main corridor (int1 -> int2 -> int3)
        GraphEdge(from_node="int1", to_node="int2", capacity=60.0, length=200, num_lanes=2,
                 current_queue=15.0, current_delay=4.0, current_flow=45.0),
        GraphEdge(from_node="int2", to_node="int3", capacity=55.0, length=180, num_lanes=2,
                 current_queue=25.0, current_delay=8.0, current_flow=50.0, spillback_active=True),
        
        # Alternative routes
        GraphEdge(from_node="int1", to_node="int4", capacity=40.0, length=150, num_lanes=1,
                 current_queue=5.0, current_delay=2.0, current_flow=30.0),
        GraphEdge(from_node="int4", to_node="int3", capacity=45.0, length=160, num_lanes=1,
                 current_queue=8.0, current_delay=3.0, current_flow=35.0),
        
        # Cross connections
        GraphEdge(from_node="int2", to_node="int4", capacity=35.0, length=100, num_lanes=1,
                 current_queue=3.0, current_delay=1.5, current_flow=25.0),
        GraphEdge(from_node="int1", to_node="int3", capacity=50.0, length=250, num_lanes=2,
                 current_queue=20.0, current_delay=10.0, current_flow=40.0, incident_active=True),
    ]
    
    for edge in edges:
        graph.add_edge(edge)
    
    # Mark congested nodes
    graph.nodes["int2"].is_congested = True
    graph.nodes["int3"].has_spillback = True
    
    return graph


def demo_export():
    """Demonstrate graph export functionality."""
    print("=" * 60)
    print("Graph Export Demo")
    print("=" * 60)
    
    # Create demo graph
    graph = create_demo_graph()
    print(f"\n✓ Created demo graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
    
    # Export snapshot
    output_dir = "output/exports"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    export_graph_snapshot(graph, output_dir, cycle=1)
    print(f"✓ Exported graph snapshot to {output_dir}/")
    print(f"  - JSON format: graph_cycle_1.json")
    print(f"  - GraphML format: graph_cycle_1.graphml")
    
    # Show some stats
    congested = len(graph.get_congested_nodes())
    spillbacks = len(graph.get_spillback_edges())
    print(f"\n📊 Graph Statistics:")
    print(f"  - Congested nodes: {congested}")
    print(f"  - Spillback edges: {spillbacks}")
    print(f"  - Total capacity: {sum(e.capacity for e in graph.edges.values()):.1f} veh/s")


def demo_visualizer():
    """Demonstrate graph visualizer with live metrics on nodes and edges."""
    print("\n" + "=" * 60)
    print("Graph Visualizer Demo")
    print("=" * 60)
    print("\n📊 This demo shows:")
    print("   • Color-coded nodes (green=normal, orange=congested, red=spillback)")
    print("   • Color-coded edges (gray=normal, orange=high cost, red=incident)")
    print("   • Edge widths represent queue lengths")
    print("   • Real-time metrics updates\n")
    print("⚠️  The visualization window will update in real-time.")
    print("   Close the window when done viewing.\n")
    
    # Create demo graph
    graph = create_demo_graph()
    
    # Create and start visualizer
    viz = GraphVisualizer(graph, record=False)
    print("✓ Initializing visualizer...")
    viz.start()
    print("✓ Visualizer window opened\n")
    
    # Simulate traffic updates
    print("🔄 Simulating 5 traffic cycles...")
    print("   (Each cycle updates every 1.5 seconds)\n")
    
    for cycle in range(1, 6):
        # Update metrics
        viz.update_metrics(
            cycle=cycle,
            incidents=1 if cycle % 2 == 0 else 0,
            adaptations=cycle - 1,
            avg_delay=5.0 + cycle * 0.5
        )
        
        # Simulate traffic evolution
        for edge in graph.edges.values():
            edge.current_queue = max(0, edge.current_queue + (cycle % 3 - 1) * 2)
            edge.current_delay = max(0, edge.current_delay + (cycle % 3 - 1) * 0.5)
        
        # Change node states dynamically
        if cycle == 2:
            graph.nodes["int1"].is_congested = True
        if cycle == 4:
            graph.nodes["int4"].has_spillback = True
        
        # Refresh the visualization
        viz.update()
        
        print(f"  ✓ Cycle {cycle}: Network state updated")
        time.sleep(1.5)
    
    print("\n✅ Simulation complete!")
    print("   Close the visualization window to continue...\n")
    
    # Keep window open until user closes it
    viz.pause_until_closed()
    viz.stop()
    print("✓ Visualizer closed")


def main():
    """Run all demos."""
    print("\n🚦 AegisLights - Graph Export & Visualization Demo\n")
    
    # Run export demo
    demo_export()
    
    # Ask before showing visualizer
    print("\n" + "=" * 60)
    response = input("Run visualizer demo? (y/n): ").strip().lower()
    
    if response == 'y':
        demo_visualizer()
    else:
        print("Skipping visualizer demo.")
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()

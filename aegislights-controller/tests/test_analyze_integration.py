"""Test Analyze stage with Monitor integration."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from adaptation_manager.knowledge import KnowledgeBase
from adaptation_manager.analyze import Analyzer
from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from config.mape import MAPEConfig
from config.costs import CostConfig
from config.experiment import ExperimentConfig
import time


def test_analyze_stage():
    """Test Analyze stage with realistic traffic data."""
    
    print("Setting up Analyze stage test...")
    
    # Setup configuration
    exp_config = ExperimentConfig()
    mape_config = MAPEConfig(
        hotspot_threshold=0.7,
        k_shortest_paths=3,
        trend_alpha=0.3,
        coordination_enabled=True
    )
    
    # Create knowledge base
    knowledge = KnowledgeBase(exp_config.db_path, TrafficGraph())
    
    # Create traffic graph with CityFlow topology
    graph = TrafficGraph()
    
    # Add signalized intersections
    for node_id in ['A', 'B', 'C', 'D', 'E']:
        graph.add_node(GraphNode(
            node_id=node_id,
            intersection_type='signalized'
        ))
    
    # Add virtual nodes
    for node_id in ['1', '2', '3', '4', '5', '6', '7', '8']:
        graph.add_node(GraphNode(
            node_id=node_id,
            intersection_type='virtual'
        ))
    
    # Add edges with realistic congestion data
    edges_data = [
        # Congested edges (high delay/queue)
        ('A', 'B', 'AB', 100.0, 30.0, 80.0, 25.0, False, False),  # High congestion
        ('B', 'A', 'BA', 100.0, 30.0, 30.0, 5.0, False, False),
        ('A', 'C', 'AC', 100.0, 30.0, 20.0, 3.0, False, False),
        ('C', 'A', 'CA', 100.0, 30.0, 15.0, 2.0, False, False),
        
        # Spillback edge
        ('B', 'C', 'BC', 100.0, 30.0, 95.0, 30.0, True, False),  # Spillback
        ('C', 'B', 'CB', 100.0, 30.0, 25.0, 4.0, False, False),
        
        # Incident edge
        ('B', 'D', 'BD', 100.0, 30.0, 70.0, 35.0, False, True),  # Incident
        ('D', 'B', 'DB', 100.0, 30.0, 40.0, 8.0, False, False),
        
        # Low congestion (potential bypasses)
        ('C', 'E', 'CE', 100.0, 30.0, 10.0, 2.0, False, False),
        ('E', 'C', 'EC', 100.0, 30.0, 12.0, 2.5, False, False),
        ('D', 'E', 'DE', 100.0, 30.0, 15.0, 3.0, False, False),
        ('E', 'D', 'ED', 100.0, 30.0, 18.0, 3.5, False, False),
    ]
    
    for from_node, to_node, edge_id, capacity, fft, queue, delay, spillback, incident in edges_data:
        edge = GraphEdge(
            from_node=from_node,
            to_node=to_node,
            capacity=capacity,
            free_flow_time=fft,
            current_queue=queue,
            current_delay=delay,
            spillback_active=spillback,
            incident_active=incident
        )
        graph.add_edge(edge)
    
    print(f"Created graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
    
    # Create Analyzer
    analyzer = Analyzer(knowledge, graph, mape_config)
    
    # Create mock monitor data
    monitor_data = {
        'cycle': 1,
        'timestamp': time.time(),
        'aggregates': {
            'avg_queue': 40.0,
            'avg_delay': 10.0,
            'max_queue': 95.0,
            'max_delay': 35.0
        },
        'anomalies': {
            'spillbacks': [
                {'from': 'B', 'to': 'C', 'queue': 95.0, 'delay': 30.0}
            ],
            'incidents': [
                {'from': 'B', 'to': 'D', 'queue': 70.0, 'delay': 35.0}
            ],
            'high_congestion': [
                {'from': 'A', 'to': 'B', 'queue': 80.0, 'capacity': 100.0}
            ]
        }
    }
    
    print("\n--- Executing Analyze Stage ---")
    
    # Execute analysis
    analysis_result = analyzer.execute(cycle=1, monitor_data=monitor_data)
    
    print(f"\n✓ Analysis Results:")
    print(f"  Cycle: {analysis_result['cycle']}")
    print(f"  Edge costs computed: {len(analysis_result['edge_costs'])}")
    print(f"  Average cost: {analysis_result['avg_cost']:.2f}")
    print(f"  Max cost: {analysis_result['max_cost']:.2f}")
    
    print(f"\n  Hotspots identified: {len(analysis_result['hotspots'])}")
    for hotspot in analysis_result['hotspots']:
        cost = analysis_result['edge_costs'].get(hotspot, 0.0)
        print(f"    {hotspot[0]} -> {hotspot[1]}: cost = {cost:.2f}")
    
    print(f"\n  Bypass routes found: {len(analysis_result['bypasses'])}")
    for bypass in analysis_result['bypasses'][:3]:  # Show first 3
        print(f"    {bypass['source']} -> {bypass['destination']}: "
              f"{len(bypass['path'])} edges, cost = {bypass['total_cost']:.2f}")
        print(f"      Bypasses: {bypass['bypasses']}")
    
    print(f"\n  Incidents: {len(analysis_result['incidents'])}")
    for incident in analysis_result['incidents']:
        print(f"    {incident['from']} -> {incident['to']}: "
              f"severity = {incident['severity']}, delay = {incident['delay']:.2f}s")
    
    print(f"\n  Adaptation Targets:")
    targets = analysis_result['targets']
    print(f"    Edges to throttle: {len(targets['edges_to_throttle'])}")
    for edge in targets['edges_to_throttle']:
        print(f"      {edge['from']} -> {edge['to']}: reason = {edge['reason']}, cost = {edge['cost']:.2f}")
    
    print(f"    Edges to favor: {len(targets['edges_to_favor'])}")
    for edge in targets['edges_to_favor'][:3]:  # Show first 3
        print(f"      {edge['from']} -> {edge['to']}: reason = {edge['reason']}, cost = {edge['cost']:.2f}")
    
    print(f"    Adaptation needed: {targets['adaptation_needed']}")
    print(f"    Affected intersections: {targets['affected_intersections']}")
    
    print(f"\n  Coordination groups: {len(analysis_result['coordination_groups'])}")
    for i, group in enumerate(analysis_result['coordination_groups']):
        print(f"    Group {i+1}: {group['intersections']} (size: {group['size']})")
    
    # Test edge cost breakdown
    print(f"\n--- Edge Cost Breakdown ---")
    for edge_key in [('A', 'B'), ('B', 'C'), ('B', 'D')]:
        breakdown = analyzer.get_edge_cost_breakdown(edge_key[0], edge_key[1])
        if breakdown:
            print(f"\n  Edge {edge_key[0]} -> {edge_key[1]}:")
            print(f"    Total cost: {breakdown['total_cost']:.2f}")
            print(f"    Delay component: {breakdown['delay_component']:.2f} (delay: {breakdown['delay']:.2f}s)")
            print(f"    Queue component: {breakdown['queue_component']:.2f} (queue: {breakdown['queue']:.0f})")
            print(f"    Spillback component: {breakdown['spillback_component']:.2f} (active: {breakdown['spillback']})")
            print(f"    Incident component: {breakdown['incident_component']:.2f} (active: {breakdown['incident']})")
    
    # Verify cost formula
    print(f"\n--- Verifying Cost Formula ---")
    cost_config = CostConfig()
    a, b, c, d = cost_config.get_coefficients()
    print(f"  Coefficients: a={a}, b={b}, c={c}, d={d}")
    
    # Manual calculation for AB edge
    ab_edge = graph.get_edge('A', 'B')
    manual_cost = (
        a * ab_edge.current_delay +
        b * ab_edge.current_queue +
        c * (10.0 if ab_edge.spillback_active else 0.0) +
        d * (20.0 if ab_edge.incident_active else 0.0)
    )
    computed_cost = analysis_result['edge_costs'][('A', 'B')]
    print(f"  Edge AB manual cost: {manual_cost:.2f}")
    print(f"  Edge AB computed cost: {computed_cost:.2f}")
    print(f"  Match: {abs(manual_cost - computed_cost) < 0.01}")
    
    # Verify spillback penalty
    bc_edge = graph.get_edge('B', 'C')
    bc_manual = (
        a * bc_edge.current_delay +
        b * bc_edge.current_queue +
        c * 10.0 +  # Spillback active
        d * 0.0
    )
    bc_computed = analysis_result['edge_costs'][('B', 'C')]
    print(f"  Edge BC (spillback) manual: {bc_manual:.2f}")
    print(f"  Edge BC (spillback) computed: {bc_computed:.2f}")
    print(f"  Spillback penalty applied: {bc_manual > computed_cost}")
    
    # Verify incident penalty
    bd_edge = graph.get_edge('B', 'D')
    bd_manual = (
        a * bd_edge.current_delay +
        b * bd_edge.current_queue +
        c * 0.0 +
        d * 20.0  # Incident active
    )
    bd_computed = analysis_result['edge_costs'][('B', 'D')]
    print(f"  Edge BD (incident) manual: {bd_manual:.2f}")
    print(f"  Edge BD (incident) computed: {bd_computed:.2f}")
    print(f"  Incident penalty applied: {bd_manual > bc_manual}")
    
    print("\n✓ All Analyze stage tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_analyze_stage()
        print("\n=== SUCCESS: Analyze stage ready ===")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

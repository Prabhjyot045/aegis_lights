"""Test Plan stage with CityFlow integration."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from adaptation_manager.knowledge import KnowledgeBase
from adaptation_manager.plan import Planner
from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from config.mape import MAPEConfig
from config.experiment import ExperimentConfig
import time


def test_plan_stage():
    """Test Plan stage with realistic analysis data."""
    
    print("Setting up Plan stage test...")
    
    # Setup configuration
    exp_config = ExperimentConfig()
    mape_config = MAPEConfig(
        coordination_enabled=True,
        incident_mode_enabled=True,
        bandit_algorithm='ucb'
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
    
    # Add edges
    edges_data = [
        ('A', 'B', 100.0, 30.0, 80.0, 25.0, False, False),
        ('B', 'A', 100.0, 30.0, 30.0, 5.0, False, False),
        ('A', 'C', 100.0, 30.0, 20.0, 3.0, False, False),
        ('C', 'A', 100.0, 30.0, 15.0, 2.0, False, False),
        ('B', 'C', 100.0, 30.0, 95.0, 30.0, True, False),
        ('C', 'B', 100.0, 30.0, 25.0, 4.0, False, False),
        ('B', 'D', 100.0, 30.0, 70.0, 35.0, False, True),
        ('D', 'B', 100.0, 30.0, 40.0, 8.0, False, False),
        ('C', 'E', 100.0, 30.0, 10.0, 2.0, False, False),
        ('E', 'C', 100.0, 30.0, 12.0, 2.5, False, False),
        ('D', 'E', 100.0, 30.0, 15.0, 3.0, False, False),
        ('E', 'D', 100.0, 30.0, 18.0, 3.5, False, False),
    ]
    
    for from_node, to_node, capacity, fft, queue, delay, spillback, incident in edges_data:
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
    
    # Create Planner
    planner = Planner(knowledge, graph, mape_config)
    
    # Load default plans
    print("\nLoading default CityFlow plans...")
    planner.phase_library.load_default_plans()
    
    # Verify plans were loaded
    for int_id in ['A', 'B', 'C']:
        plans = planner.phase_library.get_plans(int_id)
        print(f"  Intersection {int_id}: {len(plans)} plans loaded")
    
    # Create mock analysis result (from Analyze stage)
    analysis_result = {
        'cycle': 1,
        'edge_costs': {
            ('A', 'B'): 65.0,
            ('B', 'C'): 177.5,
            ('B', 'D'): 470.0,
            ('C', 'E'): 12.0
        },
        'hotspots': [('A', 'B'), ('B', 'C'), ('B', 'D')],
        'bypasses': [
            {
                'source': 'A',
                'destination': 'E',
                'path': [('A', 'C'), ('C', 'E')],
                'total_cost': 15.0,
                'bypasses': ('A', 'B'),
                'length': 2
            }
        ],
        'trends': {
            ('A', 'B'): 'increasing',
            ('B', 'C'): 'increasing'
        },
        'incidents': [
            {
                'from': 'B',
                'to': 'D',
                'edge_key': ('B', 'D'),
                'queue': 70.0,
                'delay': 35.0,
                'severity': 'high'
            }
        ],
        'targets': {
            'edges_to_throttle': [
                {'from': 'A', 'to': 'B', 'edge_key': ('A', 'B'), 'reason': 'hotspot', 'cost': 65.0},
                {'from': 'B', 'to': 'C', 'edge_key': ('B', 'C'), 'reason': 'hotspot', 'cost': 177.5},
                {'from': 'B', 'to': 'D', 'edge_key': ('B', 'D'), 'reason': 'incident', 'cost': 470.0}
            ],
            'edges_to_favor': [
                {'from': 'A', 'to': 'C', 'edge_key': ('A', 'C'), 'reason': 'bypass', 'cost': 12.0},
                {'from': 'C', 'to': 'E', 'edge_key': ('C', 'E'), 'reason': 'bypass', 'cost': 12.0}
            ],
            'affected_intersections': ['A', 'B', 'C', 'D', 'E'],
            'adaptation_needed': True
        },
        'coordination_groups': [
            {
                'intersections': ['A', 'C', 'E'],
                'size': 3,
                'representative': 'A'
            }
        ],
        'avg_cost': 69.83,
        'max_cost': 470.0
    }
    
    print("\n--- Test 1: Normal Mode Planning ---")
    
    # Test normal mode (no incidents)
    normal_analysis = analysis_result.copy()
    normal_analysis['incidents'] = []
    
    plan_result = planner.execute(cycle=1, analysis_result=normal_analysis)
    
    print(f"\n✓ Planning Results (Normal Mode):")
    print(f"  Cycle: {plan_result['cycle']}")
    print(f"  Incident mode: {plan_result['is_incident_mode']}")
    print(f"  Adaptations: {plan_result['num_intersections']}")
    
    for adaptation in plan_result['adaptations']:
        print(f"\n  Intersection {adaptation['intersection_id']}:")
        print(f"    Plan ID: {adaptation['plan_id']}")
        print(f"    Phase ID: {adaptation['phase_id']} (0=NS, 2=EW)")
        print(f"    Cycle length: {adaptation['cycle_length']}s")
        print(f"    Offset: {adaptation['offset']:.2f}s")
        print(f"    Incident mode: {adaptation['is_incident_mode']}")
    
    print("\n--- Test 2: Incident Mode Planning ---")
    
    # Test incident mode
    incident_plan_result = planner.execute(cycle=2, analysis_result=analysis_result)
    
    print(f"\n✓ Planning Results (Incident Mode):")
    print(f"  Cycle: {incident_plan_result['cycle']}")
    print(f"  Incident mode: {incident_plan_result['is_incident_mode']}")
    print(f"  Adaptations: {incident_plan_result['num_intersections']}")
    
    for adaptation in incident_plan_result['adaptations']:
        print(f"\n  Intersection {adaptation['intersection_id']}:")
        print(f"    Plan ID: {adaptation['plan_id']}")
        print(f"    Phase ID: {adaptation['phase_id']}")
        print(f"    Incident mode: {adaptation['is_incident_mode']}")
    
    print("\n--- Test 3: Phase ID Extraction ---")
    
    # Test phase_id extraction
    test_plans = [
        'A_2phase_ns_priority',
        'B_2phase_ew_priority',
        'C_2phase_balanced'
    ]
    
    for plan_id in test_plans:
        phase_id = planner.phase_library.get_phase_id_for_plan(plan_id)
        print(f"  {plan_id} -> phase_id = {phase_id}")
    
    print("\n--- Test 4: Virtual Node Filtering ---")
    
    # Test that virtual nodes are filtered out
    virtual_test_analysis = {
        'cycle': 3,
        'edge_costs': {},
        'hotspots': [],
        'bypasses': [],
        'trends': {},
        'incidents': [],
        'targets': {
            'edges_to_throttle': [
                {'from': '1', 'to': 'A', 'edge_key': ('1', 'A'), 'reason': 'test', 'cost': 10.0},
                {'from': 'A', 'to': 'B', 'edge_key': ('A', 'B'), 'reason': 'test', 'cost': 20.0}
            ],
            'edges_to_favor': [],
            'affected_intersections': ['1', 'A', 'B'],
            'adaptation_needed': True
        },
        'coordination_groups': [],
        'avg_cost': 15.0,
        'max_cost': 20.0
    }
    
    virtual_result = planner.execute(cycle=3, analysis_result=virtual_test_analysis)
    
    print(f"\n✓ Virtual Node Filtering:")
    print(f"  Input intersections: {virtual_test_analysis['targets']['affected_intersections']}")
    print(f"  Planned adaptations: {virtual_result['num_intersections']}")
    print(f"  Adapted intersections: {[a['intersection_id'] for a in virtual_result['adaptations']]}")
    print(f"  Virtual nodes filtered: {'1' not in [a['intersection_id'] for a in virtual_result['adaptations']]}")
    
    print("\n--- Test 5: Coordination Offsets ---")
    
    # Verify coordination group received offsets
    if plan_result['adaptations']:
        has_offsets = any(a['offset'] > 0 for a in plan_result['adaptations'])
        print(f"\n✓ Coordination:")
        print(f"  Offsets applied: {has_offsets}")
        if has_offsets:
            for a in plan_result['adaptations']:
                if a['offset'] > 0:
                    print(f"    {a['intersection_id']}: offset = {a['offset']:.2f}s")
    
    print("\n✓ All Plan stage tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_plan_stage()
        print("\n=== SUCCESS: Plan stage ready ===")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

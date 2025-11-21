"""Tests for Analyze stage of MAPE-K loop."""

import logging
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Any

from adaptation_manager.analyze import Analyzer
from adaptation_manager.knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from config.mape import MAPEConfig
from db_manager import initialize_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_db() -> str:
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    initialize_database(db_path)
    return db_path


def create_mock_network() -> TrafficGraph:
    """Create a mock traffic network for testing."""
    graph = TrafficGraph()
    
    # Create intersections
    intersections = ['I1', 'I2', 'I3', 'I4', 'I5']
    for int_id in intersections:
        node = GraphNode(
            node_id=int_id,
            intersection_type="signalized",
            latitude=0.0,
            longitude=0.0
        )
        graph.add_node(node)
    
    # Create edges forming a network with alternative routes
    # Main route: I1 -> I2 -> I3 -> I4
    # Alternative: I1 -> I5 -> I4
    edges_data = [
        ('I1', 'I2', 100, 5.0, 8),   # Main route start
        ('I2', 'I3', 100, 12.0, 25),  # HOTSPOT - high delay and queue
        ('I3', 'I4', 100, 6.0, 10),   # Main route end
        ('I1', 'I5', 100, 4.0, 5),    # Alternative start
        ('I5', 'I4', 100, 5.0, 6),    # Alternative end
        ('I2', 'I5', 100, 3.0, 4),    # Connecting edge
    ]
    
    for from_int, to_int, capacity, delay, queue in edges_data:
        edge = GraphEdge(
            from_node=from_int,
            to_node=to_int,
            capacity=capacity,
            free_flow_time=10.0,
            length=500.0,
            num_lanes=2,
            current_queue=queue,
            current_delay=delay,
            current_flow=5.0,
            spillback_active=False,
            incident_active=False,
            edge_cost=0.0
        )
        graph.add_edge(edge)
        
        # Update outgoing edges
        graph.nodes[from_int].outgoing_edges.add((from_int, to_int))
    
    return graph


def create_mock_monitor_data(cycle: int, has_spillback: bool = False,
                             has_incident: bool = False) -> Dict[str, Any]:
    """Create mock monitor data."""
    return {
        'cycle': cycle,
        'aggregates': {
            'smoothed_edges': {
                ('I1', 'I2'): {'delay': 5.0, 'queue': 8},
                ('I2', 'I3'): {'delay': 12.0, 'queue': 25},
                ('I3', 'I4'): {'delay': 6.0, 'queue': 10},
                ('I1', 'I5'): {'delay': 4.0, 'queue': 5},
                ('I5', 'I4'): {'delay': 5.0, 'queue': 6},
                ('I2', 'I5'): {'delay': 3.0, 'queue': 4},
            }
        },
        'anomalies': {
            'spillbacks': [
                {'from': 'I2', 'to': 'I3', 'queue': 25}
            ] if has_spillback else [],
            'incidents': [
                {'from': 'I2', 'to': 'I3', 'delay': 12.0, 'queue': 25}
            ] if has_incident else []
        },
        'snapshot': None  # Not needed for this test
    }


def test_edge_cost_computation():
    """Test edge cost computation with coefficients."""
    logger.info("\n=== Test 1: Edge Cost Computation ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig()
    analyzer = Analyzer(knowledge, graph, config)
    
    # Execute analyze
    monitor_data = create_mock_monitor_data(cycle=1)
    result = analyzer.execute(cycle=1, monitor_data=monitor_data)
    
    # Verify
    edge_costs = result['edge_costs']
    assert len(edge_costs) == 6, f"Expected 6 edges, got {len(edge_costs)}"
    
    # Check hotspot edge has high cost
    hotspot_key = ('I2', 'I3')
    hotspot_cost = edge_costs.get(hotspot_key, 0.0)
    
    # Cost = 1.0*delay + 0.5*queue + 0*spillback + 0*incident
    # = 1.0*12.0 + 0.5*25 = 12.0 + 12.5 = 24.5
    expected_cost = 24.5
    assert abs(hotspot_cost - expected_cost) < 0.1, \
        f"Hotspot cost: expected {expected_cost}, got {hotspot_cost}"
    
    logger.info(f"✓ Edge costs computed correctly")
    logger.info(f"  Hotspot edge ('I2', 'I3') cost: {hotspot_cost:.2f}")
    logger.info(f"  Average cost: {result['avg_cost']:.2f}")
    logger.info(f"  Max cost: {result['max_cost']:.2f}")
    
    return True


def test_hotspot_identification():
    """Test hotspot identification."""
    logger.info("\n=== Test 2: Hotspot Identification ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig(hotspot_threshold=0.7)  # 70th percentile
    analyzer = Analyzer(knowledge, graph, config)
    
    # Execute
    monitor_data = create_mock_monitor_data(cycle=1)
    result = analyzer.execute(cycle=1, monitor_data=monitor_data)
    
    # Verify
    hotspots = result['hotspots']
    assert len(hotspots) > 0, "Should identify at least one hotspot"
    
    # Hotspot edge should be in the list
    assert ('I2', 'I3') in hotspots, "Expected ('I2', 'I3') to be a hotspot"
    
    logger.info(f"✓ Identified {len(hotspots)} hotspots")
    for hotspot in hotspots:
        logger.info(f"  Hotspot: {hotspot}")
    
    return True


def test_bypass_routes():
    """Test k-shortest path bypass finding."""
    logger.info("\n=== Test 3: Bypass Route Finding ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig(k_shortest_paths=3)
    analyzer = Analyzer(knowledge, graph, config)
    
    # Execute
    monitor_data = create_mock_monitor_data(cycle=1)
    result = analyzer.execute(cycle=1, monitor_data=monitor_data)
    
    # Verify
    bypasses = result['bypasses']
    logger.info(f"✓ Found {len(bypasses)} bypass routes")
    
    for i, bypass in enumerate(bypasses):
        logger.info(f"  Bypass {i+1}:")
        logger.info(f"    Route: {bypass['source']} -> {bypass['destination']}")
        logger.info(f"    Path: {bypass['path']}")
        logger.info(f"    Cost: {bypass['total_cost']:.2f}")
        logger.info(f"    Bypasses: {bypass['bypasses']}")
    
    return True


def test_target_determination():
    """Test adaptation target determination."""
    logger.info("\n=== Test 4: Target Determination ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig()
    analyzer = Analyzer(knowledge, graph, config)
    
    # Execute with incident
    monitor_data = create_mock_monitor_data(cycle=1, has_incident=True)
    result = analyzer.execute(cycle=1, monitor_data=monitor_data)
    
    # Verify
    targets = result['targets']
    assert targets['adaptation_needed'], "Should need adaptation with hotspots"
    
    throttle = targets['edges_to_throttle']
    favor = targets['edges_to_favor']
    
    logger.info(f"✓ Adaptation targets determined")
    logger.info(f"  Edges to throttle: {len(throttle)}")
    for edge in throttle:
        logger.info(f"    {edge['edge_key']}: {edge['reason']} (cost: {edge['cost']:.2f})")
    
    logger.info(f"  Edges to favor: {len(favor)}")
    for edge in favor:
        logger.info(f"    {edge['edge_key']}: {edge['reason']} (cost: {edge['cost']:.2f})")
    
    logger.info(f"  Affected intersections: {targets['affected_intersections']}")
    
    return True


def test_trend_prediction():
    """Test trend prediction with cost history."""
    logger.info("\n=== Test 5: Trend Prediction ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig(trend_alpha=0.3)
    analyzer = Analyzer(knowledge, graph, config)
    
    # Build cost history by running multiple cycles
    for cycle in range(1, 6):
        monitor_data = create_mock_monitor_data(cycle=cycle)
        result = analyzer.execute(cycle=cycle, monitor_data=monitor_data)
    
    # Check trends
    trends = result['trends']
    assert len(trends) > 0, "Should have trend predictions"
    
    logger.info(f"✓ Predicted trends for {len(trends)} edges")
    for edge_key, trend in trends.items():
        logger.info(f"  Edge {edge_key}: {trend}")
    
    return True


def test_coordination_groups():
    """Test intersection coordination grouping."""
    logger.info("\n=== Test 6: Coordination Groups ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig(coordination_enabled=True)
    analyzer = Analyzer(knowledge, graph, config)
    
    # Execute
    monitor_data = create_mock_monitor_data(cycle=1)
    result = analyzer.execute(cycle=1, monitor_data=monitor_data)
    
    # Verify
    groups = result['coordination_groups']
    logger.info(f"✓ Identified {len(groups)} coordination groups")
    
    for i, group in enumerate(groups):
        logger.info(f"  Group {i+1}:")
        logger.info(f"    Intersections: {group['intersections']}")
        logger.info(f"    Size: {group['size']}")
        logger.info(f"    Representative: {group['representative']}")
    
    return True


def test_complete_analyze_cycle():
    """Test complete analyze cycle with multiple scenarios."""
    logger.info("\n=== Test 7: Complete Analyze Cycle ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig()
    analyzer = Analyzer(knowledge, graph, config)
    
    # Run multiple cycles with different conditions
    test_scenarios = [
        (1, False, False, "Normal traffic"),
        (2, True, False, "With spillback"),
        (3, True, True, "With spillback and incident"),
        (4, False, False, "Recovery"),
        (5, False, False, "Stable"),
    ]
    
    for cycle, has_spillback, has_incident, description in test_scenarios:
        logger.info(f"\n  Cycle {cycle}: {description}")
        
        monitor_data = create_mock_monitor_data(cycle, has_spillback, has_incident)
        result = analyzer.execute(cycle=cycle, monitor_data=monitor_data)
        
        logger.info(f"    Hotspots: {len(result['hotspots'])}")
        logger.info(f"    Bypasses: {len(result['bypasses'])}")
        logger.info(f"    Incidents: {len(result['incidents'])}")
        logger.info(f"    Adaptation needed: {result['targets']['adaptation_needed']}")
        logger.info(f"    Avg cost: {result['avg_cost']:.2f}")
    
    logger.info(f"\n✓ Completed {len(test_scenarios)} analyze cycles")
    return True


def test_edge_cost_breakdown():
    """Test detailed edge cost breakdown."""
    logger.info("\n=== Test 8: Edge Cost Breakdown ===")
    
    # Setup
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path=create_test_db(), graph=graph)
    config = MAPEConfig()
    analyzer = Analyzer(knowledge, graph, config)
    
    # Execute
    monitor_data = create_mock_monitor_data(cycle=1)
    analyzer.execute(cycle=1, monitor_data=monitor_data)
    
    # Get breakdown for hotspot edge
    breakdown = analyzer.get_edge_cost_breakdown('I2', 'I3')
    
    assert breakdown is not None, "Should return cost breakdown"
    
    logger.info(f"✓ Cost breakdown for edge ('I2', 'I3'):")
    logger.info(f"  Total cost: {breakdown['total_cost']:.2f}")
    logger.info(f"  Delay component: {breakdown['delay_component']:.2f}")
    logger.info(f"  Queue component: {breakdown['queue_component']:.2f}")
    logger.info(f"  Spillback component: {breakdown['spillback_component']:.2f}")
    logger.info(f"  Incident component: {breakdown['incident_component']:.2f}")
    
    return True


def run_all_tests():
    """Run all Analyze stage tests."""
    logger.info("=" * 60)
    logger.info("Starting Analyze Stage Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Edge Cost Computation", test_edge_cost_computation),
        ("Hotspot Identification", test_hotspot_identification),
        ("Bypass Route Finding", test_bypass_routes),
        ("Target Determination", test_target_determination),
        ("Trend Prediction", test_trend_prediction),
        ("Coordination Groups", test_coordination_groups),
        ("Complete Analyze Cycle", test_complete_analyze_cycle),
        ("Edge Cost Breakdown", test_edge_cost_breakdown),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, True, None))
        except Exception as e:
            logger.error(f"✗ {test_name} failed: {e}")
            results.append((test_name, False, str(e)))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed
    
    for test_name, success, error in results:
        status = "PASS" if success else "FAIL"
        logger.info(f"  [{status}] {test_name}")
        if error:
            logger.info(f"        Error: {error}")
    
    logger.info(f"\nTotal: {len(results)} tests, {passed} passed, {failed} failed")
    logger.info(f"Success rate: {100*passed/len(results):.1f}%")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

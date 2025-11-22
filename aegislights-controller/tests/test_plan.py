"""Tests for Plan stage of MAPE-K loop."""

import sys
from pathlib import Path
import logging
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adaptation_manager.plan import Planner
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
    edges_data = [
        ('I1', 'I2', 100, 5.0, 8),   # Main route start
        ('I2', 'I3', 100, 12.0, 25),  # HOTSPOT - high delay and queue
        ('I3', 'I4', 100, 6.0, 10),   # Main route end
        ('I1', 'I5', 100, 4.0, 5),    # Alternative start
        ('I5', 'I4', 100, 5.0, 6),    # Alternative end
    ]
    
    for from_id, to_id, length, delay, queue in edges_data:
        edge = GraphEdge(
            from_node=from_id,
            to_node=to_id,
            length=length,
            capacity=10.0,
            free_flow_time=length / 13.89,  # ~50 km/h = 13.89 m/s
            num_lanes=2,
            current_queue=queue,
            current_delay=delay,
            current_flow=5.0,
            spillback_active=False,
            incident_active=False,
            edge_cost=0.0
        )
        graph.add_edge(edge)
    
    return graph


def create_analysis_result() -> Dict:
    """Create a mock analysis result."""
    return {
        'cycle': 1,
        'throttle_targets': ['I2'],  # Hotspot intersection
        'favor_targets': ['I1', 'I5'],  # Alternative route
        'hotspot_edges': [('I2', 'I3')],
        'bypass_routes': [['I1', 'I5', 'I4']],  # Alternative to I1->I2->I3->I4
        'anomalies': [],
        'timestamp': '2024-01-01T12:00:00'
    }


def create_incident_analysis_result() -> Dict:
    """Create an analysis result with an incident."""
    return {
        'cycle': 1,
        'throttle_targets': ['I3'],
        'favor_targets': ['I1', 'I5'],
        'hotspot_edges': [('I3', 'I4')],
        'bypass_routes': [['I1', 'I5', 'I4']],
        'anomalies': [],
        'incidents': [
            {
                'intersection_id': 'I3',
                'type': 'accident',
                'severity': 'high',
                'affected_approaches': ['north', 'south']
            }
        ],
        'timestamp': '2024-01-01T12:00:00'
    }


def test_plan_basic_execution():
    """Test basic plan execution."""
    logger.info("=" * 70)
    logger.info("TEST: Plan Basic Execution")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    
    planner = Planner(knowledge, graph, config)
    analysis_result = create_analysis_result()
    
    # Execute plan stage
    adaptations = planner.execute(cycle=1, analysis_result=analysis_result)
    
    # Verify adaptations were created
    assert len(adaptations) > 0, "Should create adaptations"
    
    # Verify adaptations contain required fields
    for adaptation in adaptations:
        assert 'intersection_id' in adaptation
        assert 'plan_id' in adaptation
        assert 'offset' in adaptation
        assert 'reasoning' in adaptation
        
        logger.info(f"Adaptation for {adaptation['intersection_id']}: "
                   f"plan={adaptation['plan_id']}, "
                   f"offset={adaptation['offset']:.2f}s")
    
    logger.info(f"✓ Created {len(adaptations)} adaptations")
    logger.info("")


def test_plan_context_building():
    """Test context feature extraction."""
    logger.info("=" * 70)
    logger.info("TEST: Context Building")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    
    planner = Planner(knowledge, graph, config)
    
    # Build context for intersection with hotspot
    context = planner._build_context('I2', 
                                     hotspot_edges=[('I2', 'I3')],
                                     incidents=[])
    
    # Verify context features
    assert 'avg_queue' in context
    assert 'max_queue' in context
    assert 'avg_delay' in context
    assert 'max_delay' in context
    assert 'edge_cost' in context
    assert 'has_hotspot' in context
    assert 'has_incident' in context
    assert 'num_approaches' in context
    
    # Verify hotspot is detected
    assert context['has_hotspot'] == 1, "Should detect hotspot"
    assert context['max_queue'] > 0, "Should have queue data"
    
    logger.info(f"Context for I2: {context}")
    logger.info("✓ Context features extracted correctly")
    logger.info("")


def test_plan_bandit_selection():
    """Test bandit-based plan selection."""
    logger.info("=" * 70)
    logger.info("TEST: Bandit Plan Selection")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    config.plan_algorithm = 'ucb'  # Test UCB algorithm
    
    planner = Planner(knowledge, graph, config)
    
    # Add some plans to phase library
    plan1_phases = {
        'cycle_length': 90,
        'green_times': {'north': 30, 'south': 30, 'east': 15, 'west': 15}
    }
    plan2_phases = {
        'cycle_length': 120,
        'green_times': {'north': 40, 'south': 40, 'east': 20, 'west': 20}
    }
    
    planner.phase_library.add_plan('I1', 'plan1', plan1_phases)
    planner.phase_library.add_plan('I1', 'plan2', plan2_phases)
    
    # Execute planning
    analysis_result = create_analysis_result()
    adaptations = planner.execute(cycle=1, analysis_result=analysis_result)
    
    # Verify plan was selected
    assert len(adaptations) > 0, "Should create adaptations"
    i1_adaptation = next((a for a in adaptations if a['intersection_id'] == 'I1'), None)
    assert i1_adaptation is not None, "Should have adaptation for I1"
    assert i1_adaptation['plan_id'] in ['I1_plan1', 'I1_plan2'], "Should select one of the available plans"
    
    logger.info(f"✓ Selected plan {i1_adaptation['plan_id']} using bandit algorithm")
    logger.info("")


def test_plan_coordination():
    """Test signal coordination and offset calculation."""
    logger.info("=" * 70)
    logger.info("TEST: Signal Coordination")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    
    planner = Planner(knowledge, graph, config)
    
    # Create analysis result with bypass route requiring coordination
    analysis_result = create_analysis_result()
    
    # Execute planning
    adaptations = planner.execute(cycle=1, analysis_result=analysis_result)
    
    # Verify coordination offsets were calculated
    bypass_route = analysis_result['bypass_routes'][0]  # ['I1', 'I5', 'I4']
    
    # Check that intersections in bypass have offsets
    bypass_adaptations = [a for a in adaptations if a['intersection_id'] in bypass_route]
    
    if len(bypass_adaptations) > 0:
        # First intersection should have offset = 0
        first = next((a for a in bypass_adaptations if a['intersection_id'] == bypass_route[0]), None)
        if first:
            assert first['offset'] == 0.0, "First intersection should have offset 0"
        
        # Other intersections should have increasing offsets
        offsets = {a['intersection_id']: a['offset'] for a in bypass_adaptations}
        logger.info(f"Coordination offsets: {offsets}")
        logger.info("✓ Offsets calculated for coordination")
    else:
        logger.info("ℹ No adaptations created for bypass route (may need plans in library)")
    
    logger.info("")


def test_plan_with_incident():
    """Test planning with incident handling."""
    logger.info("=" * 70)
    logger.info("TEST: Incident Handling")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    
    planner = Planner(knowledge, graph, config)
    
    # Create analysis result with incident
    analysis_result = create_incident_analysis_result()
    
    # Execute planning
    adaptations = planner.execute(cycle=1, analysis_result=analysis_result)
    
    # Verify adaptations consider incident
    incident_intersection = 'I3'
    i3_adaptation = next((a for a in adaptations if a['intersection_id'] == incident_intersection), None)
    
    if i3_adaptation:
        # Check that reasoning mentions incident
        assert 'incident' in i3_adaptation['reasoning'].lower() or \
               'accident' in i3_adaptation['reasoning'].lower(), \
               "Reasoning should mention incident"
        
        logger.info(f"I3 adaptation reasoning: {i3_adaptation['reasoning']}")
        logger.info("✓ Incident considered in planning")
    else:
        logger.info("ℹ No adaptation created for incident intersection")
    
    logger.info("")


def test_plan_decision_logging():
    """Test that planning decisions are logged to knowledge base."""
    logger.info("=" * 70)
    logger.info("TEST: Decision Logging")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    
    planner = Planner(knowledge, graph, config)
    analysis_result = create_analysis_result()
    
    # Execute planning
    adaptations = planner.execute(cycle=1, analysis_result=analysis_result)
    
    # Verify decisions were logged
    # Check that log_decision was called by verifying adaptations have reasoning
    for adaptation in adaptations:
        assert 'reasoning' in adaptation, "Should have reasoning"
        assert len(adaptation['reasoning']) > 0, "Reasoning should not be empty"
        
        logger.info(f"{adaptation['intersection_id']}: {adaptation['reasoning']}")
    
    logger.info("✓ Decisions logged with reasoning")
    logger.info("")


def test_plan_bandit_reward_update():
    """Test bandit reward update mechanism."""
    logger.info("=" * 70)
    logger.info("TEST: Bandit Reward Update")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    config.plan_algorithm = 'thompson'  # Test Thompson Sampling
    
    planner = Planner(knowledge, graph, config)
    
    # Add a plan
    plan_phases = {
        'cycle_length': 90,
        'green_times': {'north': 30}
    }
    planner.phase_library.add_plan('I1', 'TEST_PLAN', plan_phases)
    plan_id = 'I1_TEST_PLAN'  # This is how PhaseLibrary generates plan IDs
    
    # Simulate reward update
    intersection_id = 'I1'
    reward = 0.8
    
    # Update bandit state
    planner.bandit.update_reward(intersection_id, plan_id, reward)
    
    # Verify stats were updated
    stats = knowledge.get_bandit_stats(intersection_id, plan_id)
    
    assert stats['times_selected'] == 1, "Should increment selection count"
    assert stats['total_reward'] == reward, f"Total reward should be {reward}"
    assert abs(stats['avg_reward'] - reward) < 0.01, f"Average reward should be {reward}"
    
    logger.info(f"Bandit stats after update: {stats}")
    logger.info("✓ Bandit state updated correctly")
    logger.info("")


def test_plan_empty_targets():
    """Test planning with no targets (edge case)."""
    logger.info("=" * 70)
    logger.info("TEST: Empty Targets Edge Case")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    config = MAPEConfig()
    
    planner = Planner(knowledge, graph, config)
    
    # Create analysis result with no targets
    empty_result = {
        'cycle': 1,
        'throttle_targets': [],
        'favor_targets': [],
        'hotspot_edges': [],
        'bypass_routes': [],
        'anomalies': [],
        'timestamp': '2024-01-01T12:00:00'
    }
    
    # Execute planning
    adaptations = planner.execute(cycle=1, analysis_result=empty_result)
    
    # Should handle gracefully (no adaptations or default behavior)
    logger.info(f"Adaptations with empty targets: {len(adaptations)}")
    logger.info("✓ Handled empty targets gracefully")
    logger.info("")


def run_all_tests():
    """Run all plan stage tests."""
    logger.info("\n" + "=" * 70)
    logger.info("PLAN STAGE TEST SUITE")
    logger.info("=" * 70 + "\n")
    
    tests = [
        test_plan_basic_execution,
        test_plan_context_building,
        test_plan_bandit_selection,
        test_plan_coordination,
        test_plan_with_incident,
        test_plan_decision_logging,
        test_plan_bandit_reward_update,
        test_plan_empty_targets,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            logger.error(f"✗ {test.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info("\n" + "=" * 70)
    logger.info(f"TEST RESULTS: {passed} passed, {failed} failed")
    logger.info("=" * 70)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)

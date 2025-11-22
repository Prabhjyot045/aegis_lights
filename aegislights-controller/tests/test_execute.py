"""Tests for Execute stage of MAPE-K loop."""

import sys
from pathlib import Path
import logging
import tempfile

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adaptation_manager.execute import Executor
from adaptation_manager.knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from config.mape import MAPEConfig
from config.simulator import SimulatorConfig
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
    intersections = ['I1', 'I2', 'I3']
    for int_id in intersections:
        node = GraphNode(
            node_id=int_id,
            intersection_type="signalized",
            latitude=0.0,
            longitude=0.0
        )
        graph.add_node(node)
    
    # Create edges
    edges_data = [
        ('I1', 'I2', 100, 5.0, 8),
        ('I2', 'I3', 100, 6.0, 10),
    ]
    
    for from_id, to_id, length, delay, queue in edges_data:
        edge = GraphEdge(
            from_node=from_id,
            to_node=to_id,
            length=length,
            capacity=10.0,
            free_flow_time=length / 13.89,
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


def create_plan_result() -> dict:
    """Create a mock plan result."""
    return {
        'cycle': 1,
        'adaptations': [
            {
                'intersection_id': 'I1',
                'plan_id': 'I1_plan1',
                'green_splits': {'north': 30, 'south': 30},
                'cycle_length': 90,
                'offset': 0.0,
                'is_incident_mode': False
            },
            {
                'intersection_id': 'I2',
                'plan_id': 'I2_plan1',
                'green_splits': {'north': 35, 'south': 35},
                'cycle_length': 90,
                'offset': 7.2,
                'is_incident_mode': False
            }
        ],
        'is_incident_mode': False
    }


def test_execute_validation():
    """Test adaptation validation."""
    logger.info("=" * 70)
    logger.info("TEST: Execute Validation")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    mape_config = MAPEConfig()
    sim_config = SimulatorConfig()
    
    executor = Executor(knowledge, graph, sim_config, mape_config)
    
    # Test valid adaptations
    valid_adaptations = [
        {
            'intersection_id': 'I1',
            'plan_id': 'I1_plan1',
            'offset': 0.0
        }
    ]
    
    result = executor._validate_adaptations(valid_adaptations)
    assert result is True, "Valid adaptations should pass validation"
    
    # Test invalid offset
    invalid_adaptations = [
        {
            'intersection_id': 'I1',
            'plan_id': 'I1_plan1',
            'offset': 500.0  # Too large
        }
    ]
    
    result = executor._validate_adaptations(invalid_adaptations)
    assert result is False, "Invalid offset should fail validation"
    
    logger.info("✓ Validation tests passed")
    logger.info("")


def test_execute_basic():
    """Test basic execution flow."""
    logger.info("=" * 70)
    logger.info("TEST: Execute Basic Flow")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    mape_config = MAPEConfig()
    mape_config.enable_rollback = False  # Disable rollback for this test
    sim_config = SimulatorConfig()
    
    executor = Executor(knowledge, graph, sim_config, mape_config)
    plan = create_plan_result()
    
    # Execute (will fail to apply since simulator not running, but should handle gracefully)
    result = executor.execute(cycle=1, plan=plan)
    
    # Verify result structure
    assert 'cycle' in result
    assert 'applied' in result
    assert 'rolled_back' in result
    assert result['cycle'] == 1
    assert result['rolled_back'] is False
    
    logger.info(f"✓ Execute returned result: applied={len(result.get('applied', []))}, rolled_back={result['rolled_back']}")
    logger.info("")


def test_execute_empty_plan():
    """Test execution with no adaptations."""
    logger.info("=" * 70)
    logger.info("TEST: Execute Empty Plan")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    mape_config = MAPEConfig()
    sim_config = SimulatorConfig()
    
    executor = Executor(knowledge, graph, sim_config, mape_config)
    
    # Empty plan
    empty_plan = {
        'cycle': 1,
        'adaptations': [],
        'is_incident_mode': False
    }
    
    result = executor.execute(cycle=1, plan=empty_plan)
    
    # Should handle gracefully
    assert result['cycle'] == 1
    assert len(result['applied']) == 0
    assert result['rolled_back'] is False
    
    logger.info("✓ Empty plan handled gracefully")
    logger.info("")


def test_execute_logging():
    """Test execution logging."""
    logger.info("=" * 70)
    logger.info("TEST: Execute Logging")
    logger.info("=" * 70)
    
    # Setup
    db_path = create_test_db()
    graph = create_mock_network()
    knowledge = KnowledgeBase(db_path, graph)
    mape_config = MAPEConfig()
    sim_config = SimulatorConfig()
    
    executor = Executor(knowledge, graph, sim_config, mape_config)
    
    # Test logging method
    applied = [
        {'intersection_id': 'I1', 'plan_id': 'I1_plan1'},
        {'intersection_id': 'I2', 'plan_id': 'I2_plan1'}
    ]
    metrics = {
        'avg_delay': 5.5,
        'avg_queue': 8.2,
        'network_cost': 150.0
    }
    
    # Should not raise exception
    executor._log_execution(cycle=1, applied=applied, metrics=metrics)
    
    logger.info("✓ Execution logging successful")
    logger.info("")


def run_all_tests():
    """Run all execute stage tests."""
    logger.info("\n" + "=" * 70)
    logger.info("EXECUTE STAGE TEST SUITE")
    logger.info("=" * 70 + "\n")
    
    tests = [
        test_execute_validation,
        test_execute_basic,
        test_execute_empty_plan,
        test_execute_logging,
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

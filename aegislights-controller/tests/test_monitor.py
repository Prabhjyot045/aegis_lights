"""
Test Monitor stage with mock simulator data.
"""

import sys
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adaptation_manager.monitor import Monitor
from adaptation_manager.knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph
from api.data_schemas import NetworkSnapshot, IntersectionData, RoadSegment
from config.mape import MAPEConfig
from config.simulator import SimulatorConfig
from config.experiment import ExperimentConfig
from db_manager import initialize_database, verify_database


def create_mock_snapshot(cycle: int) -> NetworkSnapshot:
    """Create a mock network snapshot for testing."""
    timestamp = time.time()
    
    # Create some test roads with varying congestion
    int_1_roads = [
        RoadSegment(
            to_intersection="int_2",
            capacity=1.5,
            free_flow_time=30.0,
            current_queue=10 + cycle,  # Increasing queue
            spillback_active=False,
            incident_active=False,
            current_delay=5.5,
            current_flow=0.8
        ),
        RoadSegment(
            to_intersection="int_5",
            capacity=1.2,
            free_flow_time=25.0,
            current_queue=3,
            spillback_active=False,
            incident_active=False,
            current_delay=2.1,
            current_flow=0.6
        )
    ]
    
    int_2_roads = [
        RoadSegment(
            to_intersection="int_3",
            capacity=1.5,
            free_flow_time=30.0,
            current_queue=25 if cycle > 2 else 15,  # Spillback at cycle 3
            spillback_active=cycle > 2,
            incident_active=False,
            current_delay=12.3,
            current_flow=0.4
        ),
        RoadSegment(
            to_intersection="int_6",
            capacity=1.3,
            free_flow_time=28.0,
            current_queue=8,
            spillback_active=False,
            incident_active=False,
            current_delay=4.2,
            current_flow=0.7
        )
    ]
    
    int_3_roads = [
        RoadSegment(
            to_intersection="int_4",
            capacity=1.4,
            free_flow_time=32.0,
            current_queue=2,
            spillback_active=False,
            incident_active=cycle > 4,  # Incident at cycle 5
            current_delay=20.5 if cycle > 4 else 3.5,
            current_flow=0.2 if cycle > 4 else 0.9
        )
    ]
    
    return NetworkSnapshot(
        intersections={
            "int_1": IntersectionData(
                intersection_id="int_1",
                outgoing_roads=int_1_roads,
                signal_state="NS_GREEN",
                timestamp=timestamp
            ),
            "int_2": IntersectionData(
                intersection_id="int_2",
                outgoing_roads=int_2_roads,
                signal_state="EW_GREEN",
                timestamp=timestamp
            ),
            "int_3": IntersectionData(
                intersection_id="int_3",
                outgoing_roads=int_3_roads,
                signal_state="NS_GREEN",
                timestamp=timestamp
            )
        },
        cycle_number=cycle,
        timestamp=timestamp
    )


def test_monitor_basic():
    """Test basic Monitor functionality."""
    print("\n" + "=" * 80)
    print("Test 1: Basic Monitor Functionality")
    print("=" * 80)
    
    # Setup
    exp_config = ExperimentConfig()
    db_path = "data/test_monitor.db"
    
    # Clean and initialize database
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
    initialize_database(db_path)
    
    graph = TrafficGraph()
    knowledge = KnowledgeBase(db_path, graph)
    mape_config = MAPEConfig()
    sim_config = SimulatorConfig()
    
    monitor = Monitor(knowledge, graph, sim_config, mape_config)
    
    print("OK Monitor initialized")
    print(f"  - Window size: {monitor.window_size}")
    print(f"  - Rolling windows: {len(monitor.rolling_windows)}")
    
    return monitor, knowledge, graph


def test_monitor_single_cycle(monitor, cycle=1):
    """Test Monitor execution for a single cycle."""
    print(f"\n--- Cycle {cycle} ---")
    
    # Create mock snapshot
    snapshot = create_mock_snapshot(cycle)
    
    # Manually inject the snapshot (simulating successful API call)
    monitor.api.get_network_snapshot = lambda: snapshot
    
    # Execute monitor
    result = monitor.execute(cycle)
    
    print(f"OK Monitor executed")
    print(f"  - Timestamp: {result['timestamp']}")
    print(f"  - Edges updated: {result['edges_updated']}")
    print(f"  - Collection time: {result['collection_time']:.4f}s")
    
    # Check aggregates
    agg = result['aggregates']
    print(f"  - Avg queue: {agg.get('avg_queue', 0):.2f}")
    print(f"  - Avg delay: {agg.get('avg_delay', 0):.2f}")
    print(f"  - Max queue: {agg.get('max_queue', 0):.2f}")
    print(f"  - Total edges: {agg.get('total_edges', 0)}")
    
    # Check anomalies
    anomalies = result['anomalies']
    if anomalies['spillbacks']:
        print(f"  - Spillbacks detected: {len(anomalies['spillbacks'])}")
        for sb in anomalies['spillbacks']:
            print(f"    * {sb['from']} -> {sb['to']}: queue={sb['queue']}")
    
    if anomalies['incidents']:
        print(f"  - Incidents detected: {len(anomalies['incidents'])}")
        for inc in anomalies['incidents']:
            print(f"    * {inc['from']} -> {inc['to']}: delay={inc['delay']}")
    
    if anomalies['high_congestion']:
        print(f"  - High congestion: {len(anomalies['high_congestion'])} edges")
    
    return result


def test_monitor_multiple_cycles(monitor):
    """Test Monitor over multiple cycles."""
    print("\n" + "=" * 80)
    print("Test 2: Multiple Cycles with Rolling Aggregates")
    print("=" * 80)
    
    results = []
    for cycle in range(1, 6):
        result = test_monitor_single_cycle(monitor, cycle)
        results.append(result)
        time.sleep(0.1)  # Small delay between cycles
    
    print("\n--- Summary ---")
    print(f"OK Completed {len(results)} cycles")
    
    # Check that rolling windows are working
    print(f"  - Active rolling windows: {len(monitor.rolling_windows)}")
    
    # Show a sample window
    if monitor.rolling_windows:
        sample_key = list(monitor.rolling_windows.keys())[0]
        window = monitor.rolling_windows[sample_key]
        print(f"  - Sample window ({sample_key[0]} -> {sample_key[1]}):")
        for i, data in enumerate(window):
            print(f"    Cycle {i+1}: queue={data['queue']:.1f}, delay={data['delay']:.1f}")
    
    return results


def test_monitor_graph_updates(monitor, graph):
    """Test that graph model is properly updated."""
    print("\n" + "=" * 80)
    print("Test 3: Graph Model Updates")
    print("=" * 80)
    
    # Check nodes
    nodes = list(graph.nodes.keys())
    print(f"OK Graph nodes: {len(nodes)}")
    for node_id in nodes[:5]:  # Show first 5
        print(f"  - {node_id}")
    
    # Check edges
    edges = graph.get_all_edges()
    print(f"OK Graph edges: {len(edges)}")
    for edge in edges[:5]:  # Show first 5
        print(f"  - {edge.from_node} -> {edge.to_node}:")
        print(f"    queue={edge.current_queue:.1f}, delay={edge.current_delay:.1f}, "
              f"spillback={edge.spillback_active}, incident={edge.incident_active}")
    
    return True


def test_monitor_database_storage(knowledge):
    """Test that data is properly stored in database."""
    print("\n" + "=" * 80)
    print("Test 4: Database Storage")
    print("=" * 80)
    
    # Check snapshots
    from db_manager import get_connection, close_connection
    conn = get_connection(knowledge.db_path)
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM simulation_snapshots")
    snapshot_count = cursor.fetchone()[0]
    print(f"OK Snapshots stored: {snapshot_count}")
    
    cursor.execute("SELECT COUNT(*) FROM graph_state")
    edge_count = cursor.fetchone()[0]
    print(f"OK Edges in graph_state: {edge_count}")
    
    # Show some sample data
    cursor.execute("""
        SELECT cycle_number, from_intersection, to_intersection, queue_length, spillback_flag
        FROM simulation_snapshots
        ORDER BY cycle_number DESC
        LIMIT 5
    """)
    print(f"\nRecent snapshots:")
    for row in cursor.fetchall():
        print(f"  Cycle {row[0]}: {row[1]} -> {row[2]}, queue={row[3]}, "
              f"spillback={bool(row[4])}")
    
    close_connection(conn)
    return True


def test_monitor_statistics(monitor):
    """Test monitoring statistics."""
    print("\n" + "=" * 80)
    print("Test 5: Monitor Statistics")
    print("=" * 80)
    
    stats = monitor.get_statistics()
    
    print(f"OK Total snapshots: {stats['total_snapshots']}")
    print(f"OK Failed collections: {stats['failed_collections']}")
    print(f"OK Success rate: {stats['success_rate']:.2%}")
    print(f"OK Last collection time: {stats['last_collection_time']:.4f}s")
    print(f"OK Active windows: {stats['active_windows']}")
    
    return True


def main():
    """Run all Monitor tests."""
    print("=" * 80)
    print("Monitor Stage Tests")
    print("=" * 80)
    
    try:
        # Test 1: Basic initialization
        monitor, knowledge, graph = test_monitor_basic()
        
        # Test 2: Multiple cycles
        results = test_monitor_multiple_cycles(monitor)
        
        # Test 3: Graph updates
        test_monitor_graph_updates(monitor, graph)
        
        # Test 4: Database storage
        test_monitor_database_storage(knowledge)
        
        # Test 5: Statistics
        test_monitor_statistics(monitor)
        
        print("\n" + "=" * 80)
        print("OK All Monitor tests passed!")
        print("=" * 80)
        
        return 0
        
    except Exception as e:
        print(f"\nFAIL Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

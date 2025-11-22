"""
Test the new intersection-based schema and API data structures.
"""

import sys
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.data_schemas import NetworkSnapshot, IntersectionData, RoadSegment
from api.example_input_format import MINIMAL_EXAMPLE, EXAMPLE_NETWORK_SNAPSHOT
from db_manager import (
    get_connection, close_connection,
    insert_or_update_graph_edge, get_graph_state, get_outgoing_roads,
    insert_snapshot
)
from config.experiment import ExperimentConfig


def test_pydantic_schemas():
    """Test Pydantic schema validation."""
    print("\n" + "=" * 80)
    print("Testing Pydantic Schema Validation")
    print("=" * 80)
    
    # Test with minimal example
    try:
        snapshot = NetworkSnapshot(**MINIMAL_EXAMPLE)
        print(f"✓ Minimal example validated")
        print(f"  - Intersections: {len(snapshot.intersections)}")
        print(f"  - Cycle: {snapshot.cycle_number}")
    except Exception as e:
        print(f"✗ Failed to validate minimal example: {e}")
        return False
    
    # Test with full example
    try:
        snapshot = NetworkSnapshot(**EXAMPLE_NETWORK_SNAPSHOT)
        print(f"✓ Full example validated")
        print(f"  - Intersections: {len(snapshot.intersections)}")
        
        # Check first intersection
        int_1 = snapshot.intersections['int_1']
        print(f"  - int_1 outgoing roads: {len(int_1.outgoing_roads)}")
        
        for road in int_1.outgoing_roads:
            print(f"    * to {road.to_intersection}: queue={road.current_queue}, "
                  f"capacity={road.capacity}, spillback={road.spillback_active}")
    except Exception as e:
        print(f"✗ Failed to validate full example: {e}")
        return False
    
    return True


def test_database_operations():
    """Test database operations with intersection-based schema."""
    print("\n" + "=" * 80)
    print("Testing Database Operations")
    print("=" * 80)
    
    config = ExperimentConfig()
    conn = get_connection(config.db_path)
    
    try:
        # Test 1: Insert graph edges
        print("\n1. Testing insert_or_update_graph_edge...")
        timestamp = time.time()
        
        insert_or_update_graph_edge(
            conn, "int_1", "int_2",
            capacity=1.5, free_flow_time=30.0,
            current_queue=10, current_delay=5.5,
            current_flow=0.8,
            spillback_active=False, incident_active=False,
            edge_cost=15.5, cycle_number=1, timestamp=timestamp
        )
        print("   ✓ Inserted edge (int_1 -> int_2)")
        
        insert_or_update_graph_edge(
            conn, "int_1", "int_5",
            capacity=1.2, free_flow_time=25.0,
            current_queue=3, current_delay=2.1,
            current_flow=0.6,
            spillback_active=False, incident_active=False,
            edge_cost=10.2, cycle_number=1, timestamp=timestamp
        )
        print("   ✓ Inserted edge (int_1 -> int_5)")
        
        insert_or_update_graph_edge(
            conn, "int_2", "int_3",
            capacity=1.5, free_flow_time=30.0,
            current_queue=15, current_delay=12.3,
            current_flow=0.4,
            spillback_active=True, incident_active=False,
            edge_cost=25.8, cycle_number=1, timestamp=timestamp
        )
        print("   ✓ Inserted edge (int_2 -> int_3) with spillback")
        
        # Test 2: Query specific edge
        print("\n2. Testing get_graph_state for specific edge...")
        edge = get_graph_state(conn, "int_1", "int_2")
        if edge and len(edge) > 0:
            print(f"   ✓ Retrieved edge (int_1 -> int_2)")
            print(f"     - Queue: {edge[0]['current_queue']}")
            print(f"     - Delay: {edge[0]['current_delay']}")
            print(f"     - Cost: {edge[0]['edge_cost']}")
            print(f"     - Spillback: {bool(edge[0]['spillback_active'])}")
        else:
            print("   ✗ Failed to retrieve edge")
            return False
        
        # Test 3: Query outgoing roads
        print("\n3. Testing get_outgoing_roads...")
        outgoing = get_outgoing_roads(conn, "int_1")
        print(f"   ✓ Retrieved {len(outgoing)} outgoing roads from int_1")
        for road in outgoing:
            print(f"     - to {road['to_intersection']}: queue={road['current_queue']}, "
                  f"cost={road['edge_cost']}")
        
        # Test 4: Update existing edge
        print("\n4. Testing update on existing edge...")
        insert_or_update_graph_edge(
            conn, "int_1", "int_2",
            capacity=1.5, free_flow_time=30.0,
            current_queue=12,  # Updated
            current_delay=6.5,  # Updated
            current_flow=0.7,  # Updated
            spillback_active=False, incident_active=False,
            edge_cost=17.0,  # Updated
            cycle_number=2, timestamp=timestamp + 60
        )
        
        edge_updated = get_graph_state(conn, "int_1", "int_2")
        if edge_updated[0]['current_queue'] == 12:
            print(f"   ✓ Edge updated successfully")
            print(f"     - New queue: {edge_updated[0]['current_queue']}")
            print(f"     - New cost: {edge_updated[0]['edge_cost']}")
        else:
            print("   ✗ Update failed")
            return False
        
        # Test 5: Insert snapshots
        print("\n5. Testing insert_snapshot with intersection IDs...")
        insert_snapshot(conn, 1, timestamp, "int_1", "int_2",
                       queue=10, delay=5.5, throughput=0.8,
                       spillback=False, incident=False)
        print("   ✓ Inserted snapshot for cycle 1")
        
        insert_snapshot(conn, 2, timestamp + 60, "int_1", "int_2",
                       queue=12, delay=6.5, throughput=0.7,
                       spillback=False, incident=False)
        print("   ✓ Inserted snapshot for cycle 2")
        
        # Query snapshots
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM simulation_snapshots 
            WHERE from_intersection = ? AND to_intersection = ?
            ORDER BY cycle_number
        """, ("int_1", "int_2"))
        snapshots = cursor.fetchall()
        print(f"   ✓ Retrieved {len(snapshots)} snapshots")
        
        # Test 6: Query all edges
        print("\n6. Testing get_graph_state for all edges...")
        all_edges = get_graph_state(conn)
        print(f"   ✓ Total edges in graph: {len(all_edges)}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_connection(conn)


def test_network_snapshot_to_db():
    """Test loading a full network snapshot into the database."""
    print("\n" + "=" * 80)
    print("Testing Network Snapshot to Database")
    print("=" * 80)
    
    config = ExperimentConfig()
    conn = get_connection(config.db_path)
    
    try:
        # Parse network snapshot
        snapshot = NetworkSnapshot(**EXAMPLE_NETWORK_SNAPSHOT)
        print(f"Parsed snapshot with {len(snapshot.intersections)} intersections")
        
        # Load into database
        for int_id, int_data in snapshot.intersections.items():
            for road in int_data.outgoing_roads:
                insert_or_update_graph_edge(
                    conn,
                    from_intersection=int_id,
                    to_intersection=road.to_intersection,
                    capacity=road.capacity,
                    free_flow_time=road.free_flow_time,
                    current_queue=road.current_queue,
                    current_delay=road.current_delay or 0.0,
                    current_flow=road.current_flow or 0.0,
                    spillback_active=road.spillback_active,
                    incident_active=road.incident_active,
                    cycle_number=snapshot.cycle_number,
                    timestamp=snapshot.timestamp
                )
        
        print(f"✓ Loaded network snapshot into database")
        
        # Verify
        all_edges = get_graph_state(conn)
        print(f"✓ Database now contains {len(all_edges)} edges")
        
        # Count edges with incidents/spillbacks
        incidents = sum(1 for e in all_edges if e['incident_active'])
        spillbacks = sum(1 for e in all_edges if e['spillback_active'])
        print(f"  - Edges with incidents: {incidents}")
        print(f"  - Edges with spillbacks: {spillbacks}")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        close_connection(conn)


def main():
    """Run all tests."""
    print("=" * 80)
    print("Testing Intersection-Based Schema")
    print("=" * 80)
    
    results = []
    
    # Test 1: Pydantic schemas
    results.append(("Pydantic Schemas", test_pydantic_schemas()))
    
    # Test 2: Database operations
    results.append(("Database Operations", test_database_operations()))
    
    # Test 3: Full network snapshot
    results.append(("Network Snapshot Loading", test_network_snapshot_to_db()))
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    print("=" * 80)
    if all_passed:
        print("✓ All tests passed! 🎉")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

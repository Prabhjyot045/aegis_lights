"""
Test script for database operations.
Verifies CRUD operations and data integrity.
"""

import sys
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from db_manager import (
    initialize_database,
    verify_database,
    get_database_info,
    get_connection,
    close_connection,
    insert_snapshot,
    update_graph_state,
    get_graph_state,
    insert_signal_config,
    get_last_known_good_config,
    insert_performance_metrics
)
from config.experiment import ExperimentConfig


def test_database_operations():
    """Test all database CRUD operations."""
    print("=" * 80)
    print("Database Operations Test")
    print("=" * 80)
    
    # Use test database
    test_db_path = "data/test_aegis_lights.db"
    
    # Clean up any existing test database
    test_db = Path(test_db_path)
    if test_db.exists():
        test_db.unlink()
        print(f"Cleaned up existing test database")
    
    # 1. Initialize database
    print("\n1. Testing database initialization...")
    try:
        db_path = initialize_database(test_db_path)
        print(f"   ✓ Database created at: {db_path}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # 2. Verify database
    print("\n2. Testing database verification...")
    try:
        verification = verify_database(test_db_path)
        if verification['valid']:
            print(f"   ✓ Verification passed")
            print(f"   - Tables: {len(verification['tables'])}")
            print(f"   - Indices: {len(verification['indices'])}")
        else:
            print(f"   ✗ Verification failed")
            print(f"   - Missing tables: {verification['missing_tables']}")
            print(f"   - Missing indices: {verification['missing_indices']}")
            return False
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # 3. Get database info
    print("\n3. Testing database info...")
    try:
        info = get_database_info(test_db_path)
        print(f"   ✓ Database size: {info['size_bytes']} bytes")
        print(f"   - Tables found: {len(info['tables'])}")
        for table_name, table_info in info['tables'].items():
            print(f"     * {table_name}: {table_info['row_count']} rows, {len(table_info['columns'])} columns")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # 4. Test graph_state operations
    print("\n4. Testing graph_state operations...")
    conn = get_connection(test_db_path)
    try:
        # Insert initial graph state
        conn.execute("""
            INSERT INTO graph_state 
            (edge_id, from_intersection, to_intersection, capacity, free_flow_time)
            VALUES ('edge_1_2', 'int_1', 'int_2', 1.5, 30.0)
        """)
        conn.commit()
        print(f"   ✓ Inserted initial graph state")
        
        # Update graph state
        update_graph_state(conn, 'edge_1_2', {
            'current_queue': 10,
            'current_delay': 5.5,
            'spillback_active': 0,
            'edge_cost': 15.5,
            'last_updated_cycle': 1
        })
        print(f"   ✓ Updated graph state")
        
        # Read graph state
        state = get_graph_state(conn, 'edge_1_2')
        if state and len(state) > 0:
            print(f"   ✓ Retrieved graph state:")
            print(f"     - Queue: {state[0]['current_queue']}")
            print(f"     - Delay: {state[0]['current_delay']}")
            print(f"     - Cost: {state[0]['edge_cost']}")
        else:
            print(f"   ✗ Failed to retrieve graph state")
            return False
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # 5. Test simulation snapshots
    print("\n5. Testing simulation snapshots...")
    try:
        timestamp = time.time()
        insert_snapshot(conn, 1, timestamp, 'edge_1_2', 10, 5.5, 0.8, False, False)
        print(f"   ✓ Inserted snapshot for cycle 1")
        
        insert_snapshot(conn, 2, timestamp + 60, 'edge_1_2', 15, 7.2, 0.6, False, False)
        print(f"   ✓ Inserted snapshot for cycle 2")
        
        # Query snapshots
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM simulation_snapshots")
        count = cursor.fetchone()[0]
        print(f"   ✓ Total snapshots: {count}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # 6. Test signal configurations
    print("\n6. Testing signal configurations...")
    try:
        config_id = insert_signal_config(
            conn, 'int_1', 1, timestamp,
            'plan_2phase',
            {'phase_ns': 40.0, 'phase_ew': 40.0},
            90.0, 0.0, False
        )
        print(f"   ✓ Inserted signal config (id: {config_id})")
        
        # Retrieve last known good
        last_good = get_last_known_good_config(conn, 'int_1')
        if last_good:
            print(f"   ✓ Retrieved last known good config")
            print(f"     - Plan: {last_good['plan_id']}")
            print(f"     - Cycle: {last_good['cycle_number']}")
        else:
            print(f"   ✗ Failed to retrieve last known good")
            return False
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # 7. Test performance metrics
    print("\n7. Testing performance metrics...")
    try:
        metrics = {
            'avg_trip_time': 45.3,
            'p95_trip_time': 78.5,
            'total_spillbacks': 2,
            'total_stops': 25,
            'incident_clearance_time': 0.0,
            'utility_score': -50.3
        }
        insert_performance_metrics(conn, 1, timestamp, metrics)
        print(f"   ✓ Inserted performance metrics")
        
        # Query metrics
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM performance_metrics WHERE cycle_number = 1")
        row = cursor.fetchone()
        if row:
            print(f"   ✓ Retrieved metrics:")
            print(f"     - Avg trip time: {row['avg_trip_time']}")
            print(f"     - P95 trip time: {row['p95_trip_time']}")
            print(f"     - Spillbacks: {row['total_spillbacks']}")
        else:
            print(f"   ✗ Failed to retrieve metrics")
            return False
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # 8. Test phase libraries
    print("\n8. Testing phase libraries...")
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO phase_libraries
            (plan_id, intersection_id, plan_name, phases, pedestrian_compliant, safety_validated)
            VALUES (?, ?, ?, ?, 1, 1)
        """, ('int_1_plan_2phase', 'int_1', 'Two Phase Plan', 
              '{"cycle_length": 90, "phases": ["ns", "ew"]}'))
        conn.commit()
        print(f"   ✓ Inserted phase library plan")
        
        cursor.execute("SELECT COUNT(*) FROM phase_libraries")
        count = cursor.fetchone()[0]
        print(f"   ✓ Total plans: {count}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    # Close connection
    close_connection(conn)
    
    # 9. Final info check
    print("\n9. Final database state...")
    info = get_database_info(test_db_path)
    print(f"   Database size: {info['size_bytes']} bytes")
    print(f"   Table row counts:")
    for table_name, table_info in info['tables'].items():
        if table_info['row_count'] > 0:
            print(f"     - {table_name}: {table_info['row_count']} rows")
    
    print("\n" + "=" * 80)
    print("✓ All database tests passed! 🎉")
    print("=" * 80)
    
    return True


if __name__ == "__main__":
    success = test_database_operations()
    sys.exit(0 if success else 1)

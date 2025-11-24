"""Test Monitor with CityFlow data transformation."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from graph_manager.graph_utils import build_network_from_cityflow
import json


def test_cityflow_transformation():
    """Test CityFlow data transformation into NetworkSnapshot format."""
    
    # Mock CityFlow response
    cityflow_data = {
        "time": 120.5,
        "vehicles_count": 50,
        "lane_vehicle_count": {
            "AB_0": 5, "AB_1": 3,
            "BA_0": 4, "BA_1": 2,
            "AC_0": 2, "AC_1": 1,
            "A1_0": 3,
            "1A_0": 2
        },
        "lane_waiting_vehicle_count": {
            "AB_0": 2, "AB_1": 1,
            "BA_0": 1, "BA_1": 0,
            "AC_0": 0, "AC_1": 0,
            "A1_0": 1,
            "1A_0": 0
        },
        "current_phase": {
            "A": 0,
            "B": 2,
            "C": 0,
            "D": 2,
            "E": 0
        },
        "current_time": 120.5
    }
    
    print("Testing CityFlow data transformation...")
    print(f"Input: {json.dumps(cityflow_data, indent=2)}")
    
    # Transform
    network_data = build_network_from_cityflow(cityflow_data)
    
    print(f"\nTransformation Results:")
    print(f"  Cycle number: {network_data['cycle_number']}")
    print(f"  Timestamp: {network_data['timestamp']}")
    print(f"  Intersections: {len(network_data['intersections'])}")
    
    # Check specific intersections
    print(f"\nIntersection A:")
    int_a = network_data['intersections']['A']
    print(f"  ID: {int_a.intersection_id}")
    print(f"  Is virtual: {int_a.is_virtual}")
    print(f"  Current phase: {int_a.current_phase}")
    print(f"  Outgoing roads: {len(int_a.outgoing_roads)}")
    
    for road in int_a.outgoing_roads:
        print(f"    Edge {road.edge_id}: {road.from_intersection} -> {road.to_intersection}")
        print(f"      Queue: {road.current_queue}, Delay: {road.current_delay:.2f}s")
    
    print(f"\nIntersection 1 (virtual):")
    int_1 = network_data['intersections']['1']
    print(f"  ID: {int_1.intersection_id}")
    print(f"  Is virtual: {int_1.is_virtual}")
    print(f"  Current phase: {int_1.current_phase}")
    print(f"  Outgoing roads: {len(int_1.outgoing_roads)}")
    
    for road in int_1.outgoing_roads:
        print(f"    Edge {road.edge_id}: {road.from_intersection} -> {road.to_intersection}")
        print(f"      Queue: {road.current_queue}, Delay: {road.current_delay:.2f}s")
    
    print("\n✓ Transformation successful!")
    return True


if __name__ == "__main__":
    try:
        test_cityflow_transformation()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

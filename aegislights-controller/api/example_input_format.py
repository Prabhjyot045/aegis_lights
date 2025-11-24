"""
Example data format for CityFlow simulator API responses.

This file documents the expected JSON structure from the CityFlow simulator
and how it gets transformed into the controller's NetworkSnapshot format.
"""

import json

# Raw response from CityFlow /api/v1/snapshots/latest
CITYFLOW_RAW_RESPONSE = {
    "time": 123.5,
    "vehicles_count": 150,
    "running_vehicles": ["veh_1", "veh_2", "veh_3"],
    "all_vehicles": ["veh_1", "veh_2", "veh_3", "veh_4"],
    "vehicles_speed": {
        "veh_1": 10.5,
        "veh_2": 8.3,
        "veh_3": 0.0
    },
    "lane_vehicle_count": {
        "AB_0": 5,
        "AB_1": 3,
        "A1_0": 2,
        "BA_0": 4,
        "BA_1": 6
    },
    "lane_waiting_vehicle_count": {
        "AB_0": 2,
        "AB_1": 1,
        "A1_0": 0,
        "BA_0": 3,
        "BA_1": 4
    },
    "lane_vehicles": {
        "AB_0": ["veh_1", "veh_2"],
        "AB_1": ["veh_3"],
        "A1_0": ["veh_4"]
    },
    "accident": ["", 0]
}

# Transformed NetworkSnapshot format (after processing by controller)
EXAMPLE_NETWORK_SNAPSHOT = {
    "intersections": {
        "A": {
            "intersection_id": "A",
            "is_virtual": False,
            "outgoing_roads": [
                {
                    "edge_id": "AB",
                    "from_intersection": "A",
                    "to_intersection": "B",
                    "capacity": 100.0,  # vehicles
                    "free_flow_time": 30.0,  # seconds
                    "current_queue": 8,  # sum of lane counts
                    "current_delay": 5.5,  # computed from waiting vehicles
                    "spillback_active": False,
                    "incident_active": False,
                    "current_flow": 0.8,
                    "length": 300.0
                },
                {
                    "edge_id": "A1",
                    "from_intersection": "A",
                    "to_intersection": "1",
                    "capacity": 50.0,
                    "free_flow_time": 20.0,
                    "current_queue": 2,
                    "current_delay": 0.0,
                    "spillback_active": False,
                    "incident_active": False,
                    "current_flow": 0.3,
                    "length": 200.0
                }
            ],
            "current_phase": 0,
            "timestamp": 123.5
        },
        "B": {
            "intersection_id": "B",
            "is_virtual": False,
            "outgoing_roads": [
                {
                    "edge_id": "BA",
                    "from_intersection": "B",
                    "to_intersection": "A",
                    "capacity": 100.0,
                    "free_flow_time": 30.0,
                    "current_queue": 10,
                    "current_delay": 8.2,
                    "spillback_active": False,
                    "incident_active": False,
                    "current_flow": 0.7,
                    "length": 300.0
                }
            ],
            "current_phase": 1,
            "timestamp": 123.5
        },
        "1": {
            "intersection_id": "1",
            "is_virtual": True,
            "outgoing_roads": [
                {
                    "edge_id": "1A",
                    "from_intersection": "1",
                    "to_intersection": "A",
                    "capacity": 50.0,
                    "free_flow_time": 20.0,
                    "current_queue": 0,
                    "current_delay": 0.0,
                    "spillback_active": False,
                    "incident_active": False,
                    "current_flow": 0.5,
                    "length": 200.0
                }
            ],
            "timestamp": 123.5
        }
    },
    "cycle_number": 12,
    "timestamp": 123.5
}

# Minimal example for testing (after transformation)
MINIMAL_EXAMPLE = {
    "intersections": {
        "A": {
            "intersection_id": "A",
            "is_virtual": False,
            "outgoing_roads": [
                {
                    "edge_id": "AB",
                    "from_intersection": "A",
                    "to_intersection": "B",
                    "capacity": 100.0,
                    "free_flow_time": 30.0,
                    "current_queue": 10,
                    "current_delay": 5.0,
                    "spillback_active": False,
                    "incident_active": False
                }
            ],
            "current_phase": 0
        }
    },
    "cycle_number": 1,
    "timestamp": 123.5
}

# CityFlow network topology (5 signalized + 8 virtual nodes)
CITYFLOW_TOPOLOGY = {
    "signalized_intersections": ["A", "B", "C", "D", "E"],
    "virtual_nodes": ["1", "2", "3", "4", "5", "6", "7", "8"],
    "edges": [
        # Inter-intersection edges
        {"edge_id": "AB", "from": "A", "to": "B", "lanes": 2},
        {"edge_id": "BA", "from": "B", "to": "A", "lanes": 2},
        {"edge_id": "AC", "from": "A", "to": "C", "lanes": 2},
        {"edge_id": "CA", "from": "C", "to": "A", "lanes": 2},
        {"edge_id": "BC", "from": "B", "to": "C", "lanes": 2},
        {"edge_id": "CB", "from": "C", "to": "B", "lanes": 2},
        {"edge_id": "BD", "from": "B", "to": "D", "lanes": 2},
        {"edge_id": "DB", "from": "D", "to": "B", "lanes": 2},
        {"edge_id": "CE", "from": "C", "to": "E", "lanes": 2},
        {"edge_id": "EC", "from": "E", "to": "C", "lanes": 2},
        {"edge_id": "DE", "from": "D", "to": "E", "lanes": 2},
        {"edge_id": "ED", "from": "E", "to": "D", "lanes": 2},
        # Virtual node connections
        {"edge_id": "1A", "from": "1", "to": "A", "lanes": 2},
        {"edge_id": "A1", "from": "A", "to": "1", "lanes": 2},
        {"edge_id": "2A", "from": "2", "to": "A", "lanes": 2},
        {"edge_id": "A2", "from": "A", "to": "2", "lanes": 2},
        {"edge_id": "3B", "from": "3", "to": "B", "lanes": 2},
        {"edge_id": "B3", "from": "B", "to": "3", "lanes": 2},
        {"edge_id": "4C", "from": "4", "to": "C", "lanes": 2},
        {"edge_id": "C4", "from": "C", "to": "4", "lanes": 2},
        {"edge_id": "5D", "from": "5", "to": "D", "lanes": 2},
        {"edge_id": "D5", "from": "D", "to": "5", "lanes": 2},
        {"edge_id": "6D", "from": "6", "to": "D", "lanes": 2},
        {"edge_id": "D6", "from": "D", "to": "6", "lanes": 2},
        {"edge_id": "7E", "from": "7", "to": "E", "lanes": 2},
        {"edge_id": "E7", "from": "E", "to": "7", "lanes": 2},
        {"edge_id": "8E", "from": "8", "to": "E", "lanes": 2},
        {"edge_id": "E8", "from": "E", "to": "8", "lanes": 2}
    ],
    "phases": {
        "description": "All signalized intersections use 4-phase timing",
        "phase_0": {"time": 30, "description": "Main through movements"},
        "phase_1": {"time": 10, "description": "Left turns from main"},
        "phase_2": {"time": 30, "description": "Cross through movements"},
        "phase_3": {"time": 10, "description": "Left turns from cross"}
    }
}


def print_examples():
    """Print formatted examples."""
    print("=" * 80)
    print("CityFlow Data Format Examples")
    print("=" * 80)
    
    print("\n1. Raw CityFlow Response:")
    print(json.dumps(CITYFLOW_RAW_RESPONSE, indent=2))
    
    print("\n" + "=" * 80)
    print("2. Transformed NetworkSnapshot:")
    print(json.dumps(EXAMPLE_NETWORK_SNAPSHOT, indent=2))
    
    print("\n" + "=" * 80)
    print("3. Minimal Example:")
    print(json.dumps(MINIMAL_EXAMPLE, indent=2))
    
    print("\n" + "=" * 80)
    print("4. CityFlow Network Topology:")
    print(json.dumps(CITYFLOW_TOPOLOGY, indent=2))
    
    print("\n" + "=" * 80)
    print("\nKey Points:")
    print("- CityFlow provides lane-level data (lane_vehicle_count, lane_waiting_vehicle_count)")
    print("- Controller aggregates lanes into edges (AB, BA, etc.)")
    print("- Edges identified by edge_id and (from_intersection, to_intersection)")
    print("- 5 signalized intersections: A, B, C, D, E")
    print("- 8 virtual nodes (sources/sinks): 1, 2, 3, 4, 5, 6, 7, 8")
    print("- 28 total directed edges in the network")
    print("- Phase indices 0-3 for signalized intersections")


if __name__ == "__main__":
    print_examples()

"""
Example data format for simulator API responses.

This file documents the expected JSON structure for the intersection-based
network snapshot that the simulator should provide.
"""

import json

# Example network snapshot with intersection-based structure
EXAMPLE_NETWORK_SNAPSHOT = {
    "intersections": {
        "int_1": {
            "intersection_id": "int_1",
            "outgoing_roads": [
                {
                    "to_intersection": "int_2",
                    "capacity": 1.5,  # vehicles (normalized capacity)
                    "free_flow_time": 30.0,  # seconds
                    "current_queue": 10,  # vehicles
                    "spillback_active": False,
                    "incident_active": False,
                    "current_delay": 5.5,  # seconds
                    "current_flow": 0.8  # vehicles/hour (normalized)
                },
                {
                    "to_intersection": "int_5",
                    "capacity": 1.2,
                    "free_flow_time": 25.0,
                    "current_queue": 3,
                    "spillback_active": False,
                    "incident_active": False,
                    "current_delay": 2.1,
                    "current_flow": 0.6
                }
            ],
            "signal_state": "NS_GREEN",  # Optional: current signal phase
            "timestamp": 1234567890.0
        },
        "int_2": {
            "intersection_id": "int_2",
            "outgoing_roads": [
                {
                    "to_intersection": "int_3",
                    "capacity": 1.5,
                    "free_flow_time": 30.0,
                    "current_queue": 15,
                    "spillback_active": True,  # Congestion detected
                    "incident_active": False,
                    "current_delay": 12.3,
                    "current_flow": 0.4
                },
                {
                    "to_intersection": "int_6",
                    "capacity": 1.3,
                    "free_flow_time": 28.0,
                    "current_queue": 8,
                    "spillback_active": False,
                    "incident_active": False,
                    "current_delay": 4.2,
                    "current_flow": 0.7
                }
            ],
            "signal_state": "EW_GREEN",
            "timestamp": 1234567890.0
        },
        "int_3": {
            "intersection_id": "int_3",
            "outgoing_roads": [
                {
                    "to_intersection": "int_4",
                    "capacity": 1.4,
                    "free_flow_time": 32.0,
                    "current_queue": 2,
                    "spillback_active": False,
                    "incident_active": True,  # Incident on this road
                    "current_delay": 20.5,  # High delay due to incident
                    "current_flow": 0.2
                }
            ],
            "signal_state": "NS_GREEN",
            "timestamp": 1234567890.0
        }
    },
    "cycle_number": 42,
    "timestamp": 1234567890.0
}

# Minimal example for testing
MINIMAL_EXAMPLE = {
    "intersections": {
        "int_1": {
            "intersection_id": "int_1",
            "outgoing_roads": [
                {
                    "to_intersection": "int_2",
                    "capacity": 1.5,
                    "free_flow_time": 30.0,
                    "current_queue": 10,
                    "spillback_active": False,
                    "incident_active": False
                }
            ]
        }
    },
    "cycle_number": 1,
    "timestamp": 1234567890.0
}

# Example of static topology (for initialization)
EXAMPLE_TOPOLOGY = {
    "intersections": {
        "int_1": {
            "intersection_id": "int_1",
            "outgoing_roads": [
                {
                    "to_intersection": "int_2",
                    "capacity": 1.5,
                    "free_flow_time": 30.0,
                    "current_queue": 0,
                    "spillback_active": False,
                    "incident_active": False
                },
                {
                    "to_intersection": "int_5",
                    "capacity": 1.2,
                    "free_flow_time": 25.0,
                    "current_queue": 0,
                    "spillback_active": False,
                    "incident_active": False
                }
            ]
        },
        "int_2": {
            "intersection_id": "int_2",
            "outgoing_roads": [
                {
                    "to_intersection": "int_1",
                    "capacity": 1.5,
                    "free_flow_time": 30.0,
                    "current_queue": 0,
                    "spillback_active": False,
                    "incident_active": False
                },
                {
                    "to_intersection": "int_3",
                    "capacity": 1.5,
                    "free_flow_time": 30.0,
                    "current_queue": 0,
                    "spillback_active": False,
                    "incident_active": False
                }
            ]
        }
    }
}


def print_examples():
    """Print formatted examples."""
    print("=" * 80)
    print("Example Network Snapshot Format")
    print("=" * 80)
    print("\n1. Full Example:")
    print(json.dumps(EXAMPLE_NETWORK_SNAPSHOT, indent=2))
    
    print("\n" + "=" * 80)
    print("2. Minimal Example:")
    print(json.dumps(MINIMAL_EXAMPLE, indent=2))
    
    print("\n" + "=" * 80)
    print("3. Topology Example:")
    print(json.dumps(EXAMPLE_TOPOLOGY, indent=2))
    
    print("\n" + "=" * 80)
    print("\nKey Points:")
    print("- Each intersection has an ID and list of outgoing roads")
    print("- Roads are identified by (from_intersection, to_intersection)")
    print("- Static attributes: capacity, free_flow_time")
    print("- Dynamic attributes: current_queue, spillback_active, incident_active")
    print("- Optional attributes: current_delay, current_flow, signal_state")


if __name__ == "__main__":
    print_examples()

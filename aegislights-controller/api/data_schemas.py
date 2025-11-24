"""Pydantic data schemas for API validation."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List


class RoadSegment(BaseModel):
    """Schema for a road segment (edge) from CityFlow simulator."""
    
    edge_id: str = Field(description="Edge ID (e.g., 'AB', 'A1')")
    from_intersection: str = Field(description="Source intersection/node ID")
    to_intersection: str = Field(description="Destination intersection/node ID")
    capacity: float = Field(ge=0, description="Road capacity (vehicles)")
    free_flow_time: float = Field(ge=0, description="Free flow travel time (seconds)")
    current_queue: float = Field(ge=0, description="Queue length from lane data (vehicles)")
    current_delay: float = Field(ge=0, description="Average delay (seconds)")
    spillback_active: bool = Field(default=False, description="Whether spillback is occurring")
    incident_active: bool = Field(default=False, description="Whether an incident is present")
    current_flow: Optional[float] = Field(None, ge=0, description="Current flow (vehicles/hour)")
    length: Optional[float] = Field(None, ge=0, description="Road length (meters)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "edge_id": "AB",
                "from_intersection": "A",
                "to_intersection": "B",
                "capacity": 100.0,
                "free_flow_time": 30.0,
                "current_queue": 10,
                "current_delay": 5.5,
                "spillback_active": False,
                "incident_active": False,
                "current_flow": 0.8,
                "length": 300.0
            }
        }


class IntersectionData(BaseModel):
    """Schema for intersection data from CityFlow."""
    
    intersection_id: str = Field(description="Unique intersection identifier (A, B, C, D, E, 1-8)")
    is_virtual: bool = Field(default=False, description="True for virtual nodes (1-8), False for signalized (A-E)")
    outgoing_roads: List[RoadSegment] = Field(description="Roads/edges leaving this intersection")
    current_phase: Optional[int] = Field(None, description="Current phase index (0-3 for signalized)")
    timestamp: Optional[float] = Field(None, description="Timestamp of data")
    
    class Config:
        json_schema_extra = {
            "example": {
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
                        "current_delay": 5.5,
                        "spillback_active": False,
                        "incident_active": False
                    }
                ],
                "current_phase": 0,
                "timestamp": 1234567890.0
            }
        }


class NetworkSnapshot(BaseModel):
    """Complete network state snapshot."""
    
    intersections: Dict[str, IntersectionData] = Field(
        description="Map of intersection_id to intersection data"
    )
    cycle_number: int = Field(description="Simulation cycle number")
    timestamp: float = Field(description="Snapshot timestamp")
    average_travel_time: Optional[float] = Field(None, description="Average travel time from simulator (seconds)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "intersections": {
                    "A": {
                        "intersection_id": "A",
                        "is_virtual": False,
                        "outgoing_roads": [],
                        "current_phase": 0
                    },
                    "1": {
                        "intersection_id": "1",
                        "is_virtual": True,
                        "outgoing_roads": []
                    }
                },
                "cycle_number": 1,
                "timestamp": 1234567890.0
            }
        }


class EdgeData(BaseModel):
    """Schema for edge traffic data from simulator."""
    
    edge_id: str
    queue_length: int = Field(ge=0, description="Number of vehicles in queue")
    delay: float = Field(ge=0.0, description="Average delay in seconds per vehicle")
    throughput: float = Field(ge=0.0, description="Vehicles per second")
    spillback_flag: bool = Field(default=False, description="Queue blocking upstream")
    incident_flag: bool = Field(default=False, description="Incident active on edge")
    
    class Config:
        json_schema_extra = {
            "example": {
                "edge_id": "edge_1_2",
                "queue_length": 12,
                "delay": 5.3,
                "throughput": 0.8,
                "spillback_flag": False,
                "incident_flag": False
            }
        }


class SignalConfiguration(BaseModel):
    """Schema for signal timing configuration for CityFlow."""
    
    intersection_id: str = Field(description="Intersection ID (A, B, C, D, E)")
    phase_id: int = Field(ge=0, le=3, description="Phase index (0-3)")
    plan_id: Optional[str] = Field(None, description="Plan ID for tracking (e.g., A_2phase_ns_priority)")
    offset: float = Field(default=0.0, description="Offset for coordination in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "intersection_id": "A",
                "phase_id": 0,
                "plan_id": "A_2phase_ns_priority",
                "offset": 0.0
            }
        }


class IncidentEvent(BaseModel):
    """Schema for incident injection."""
    
    edge_id: str
    incident_type: str = Field(description="Type: crash, closure, stall")
    duration: float = Field(gt=0, description="Duration in seconds")
    severity: float = Field(ge=0.0, le=1.0, description="Severity 0-1")
    
    class Config:
        json_schema_extra = {
            "example": {
                "edge_id": "edge_3_4",
                "incident_type": "crash",
                "duration": 300.0,
                "severity": 0.8
            }
        }


class SimulatorResponse(BaseModel):
    """Generic simulator response schema."""
    
    success: bool
    message: Optional[str] = None
    data: Optional[Dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Signal configuration applied",
                "data": {"applied_at_cycle": 42}
            }
        }


class VehicleData(BaseModel):
    """Schema for vehicle state data."""
    
    vehicle_id: str
    current_edge: str
    speed: float
    position: float
    waiting_time: float = 0.0
    
    class Config:
        json_schema_extra = {
            "example": {
                "vehicle_id": "veh_123",
                "current_edge": "edge_1_2",
                "speed": 8.5,
                "position": 45.2,
                "waiting_time": 12.3
            }
        }

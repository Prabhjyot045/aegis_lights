"""Pydantic data schemas for API validation."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List


class RoadSegment(BaseModel):
    """Schema for a road segment from one intersection to another."""
    
    to_intersection: str = Field(description="Destination intersection ID")
    capacity: float = Field(ge=0, description="Road capacity (vehicles)")
    free_flow_time: float = Field(ge=0, description="Free flow travel time (seconds)")
    current_queue: float = Field(ge=0, description="Current queue length (vehicles)")
    spillback_active: bool = Field(default=False, description="Whether spillback is occurring")
    incident_active: bool = Field(default=False, description="Whether an incident is present")
    current_delay: Optional[float] = Field(None, ge=0, description="Current delay (seconds)")
    current_flow: Optional[float] = Field(None, ge=0, description="Current flow (vehicles/hour)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "to_intersection": "int_2",
                "capacity": 1.5,
                "free_flow_time": 30.0,
                "current_queue": 10,
                "spillback_active": False,
                "incident_active": False,
                "current_delay": 5.5,
                "current_flow": 0.8
            }
        }


class IntersectionData(BaseModel):
    """Schema for intersection and its outgoing roads."""
    
    intersection_id: str = Field(description="Unique intersection identifier")
    outgoing_roads: List[RoadSegment] = Field(description="Roads leaving this intersection")
    signal_state: Optional[str] = Field(None, description="Current signal phase/state")
    timestamp: Optional[float] = Field(None, description="Timestamp of data")
    
    class Config:
        json_schema_extra = {
            "example": {
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
                ],
                "signal_state": "NS_GREEN",
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "intersections": {
                    "int_1": {
                        "intersection_id": "int_1",
                        "outgoing_roads": [],
                        "signal_state": "NS_GREEN"
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
    """Schema for signal timing configuration."""
    
    intersection_id: str
    plan_id: str
    green_splits: Dict[str, float] = Field(description="Phase ID to green time mapping")
    cycle_length: float = Field(gt=0, description="Total cycle length in seconds")
    offset: float = Field(default=0.0, description="Offset for coordination in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "intersection_id": "int_1",
                "plan_id": "plan_2phase",
                "green_splits": {"phase_ns": 40.0, "phase_ew": 40.0},
                "cycle_length": 90.0,
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

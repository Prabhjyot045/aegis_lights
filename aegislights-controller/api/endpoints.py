"""High-level API endpoint methods for simulator interaction."""

import logging
from typing import List, Optional, Dict
import time

from .simulator_client import SimulatorClient
from .data_schemas import (
    EdgeData, SignalConfiguration, IncidentEvent, SimulatorResponse,
    NetworkSnapshot, IntersectionData, RoadSegment
)
from config.simulator import SimulatorConfig

logger = logging.getLogger(__name__)


class SimulatorAPI:
    """High-level API for CityFlow simulator operations."""
    
    def __init__(self, config: SimulatorConfig):
        """
        Initialize simulator API.
        
        Args:
            config: Simulator configuration
        """
        self.config = config
        self.client = SimulatorClient(config)
        
        # Check connection on initialization
        if not self.client.check_connection():
            logger.warning("Unable to connect to simulator at startup")
    
    def get_network_snapshot(self) -> Optional[NetworkSnapshot]:
        """
        Get complete network state snapshot from CityFlow simulator.
        
        CityFlow returns raw vehicle/lane data. This method transforms it into
        the NetworkSnapshot format expected by the controller.
        
        CityFlow response format:
        {
            "time": 123.5,
            "vehicles_count": 150,
            "running_vehicles": [...],
            "lane_vehicle_count": {"AB_0": 5, "AB_1": 3, ...},
            "lane_waiting_vehicle_count": {"AB_0": 2, "AB_1": 1, ...},
            "accident": ["", 0]
        }
        
        Returns:
            NetworkSnapshot object or None if failed
        """
        response = self.client.get(self.config.endpoint_get_network)
        
        if not response:
            logger.error("Failed to get network snapshot from CityFlow")
            return None
        
        try:
            # Transform CityFlow response to NetworkSnapshot
            snapshot = self._transform_cityflow_snapshot(response)
            if snapshot:
                logger.info(f"Retrieved network snapshot with {len(snapshot.intersections)} nodes")
            return snapshot
        except Exception as e:
            logger.error(f"Failed to parse CityFlow snapshot: {e}")
            return None
    
    def _transform_cityflow_snapshot(self, cityflow_data: Dict) -> Optional[NetworkSnapshot]:
        """
        Transform CityFlow raw data into NetworkSnapshot format.
        
        Args:
            cityflow_data: Raw data from CityFlow /api/v1/snapshots/latest
            
        Returns:
            NetworkSnapshot object or None
        """
        from graph_manager.graph_utils import build_network_from_cityflow
        
        try:
            # Use graph utilities to transform the data
            # This will aggregate lane data into edge-level metrics
            network_data = build_network_from_cityflow(cityflow_data)
            
            # Create NetworkSnapshot from transformed data
            snapshot = NetworkSnapshot(
                intersections=network_data['intersections'],
                cycle_number=network_data.get('cycle_number', 0),
                timestamp=cityflow_data.get('time', time.time()),
                average_travel_time=cityflow_data.get('average_travel_time')
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to transform CityFlow data: {e}")
            return None
    
    def update_signal_timing(self, intersection_id: str, phase_id: int, 
                           plan_id: Optional[str] = None) -> bool:
        """
        Update signal timing for an intersection (apply phase to CityFlow).
        
        Args:
            intersection_id: Intersection identifier (A, B, C, D, E)
            phase_id: Phase index (0-3)
            plan_id: Optional plan ID for tracking purposes
            
        Returns:
            True if successful, False otherwise
        """
        config = SignalConfiguration(
            intersection_id=intersection_id,
            phase_id=phase_id,
            plan_id=plan_id
        )
        return self.set_signal_timing(config)
    
    def set_signal_timing(self, config: SignalConfiguration) -> bool:
        """
        Set signal phase for an intersection in CityFlow.
        
        Args:
            config: Signal configuration with intersection_id and phase_id
            
        Returns:
            True if successful, False otherwise
        """
        # CityFlow expects: POST /api/v1/intersections/{id}/plan with {"phase_id": 0}
        response = self.client.post(
            self.config.endpoint_set_signal,
            data={"phase_id": config.phase_id},
            intersection_id=config.intersection_id
        )
        
        if response and response.get('success'):
            logger.info(f"Phase {config.phase_id} applied to intersection {config.intersection_id}")
            return True
        else:
            logger.error(f"Failed to apply phase {config.phase_id} to {config.intersection_id}")
            return False
    
    def get_travel_times(self) -> Optional[Dict]:
        """
        Get average travel times from CityFlow.
        
        Returns:
            Dict with travel time data or None
        """
        response = self.client.get(self.config.endpoint_get_travel_time)
        return response if response else None
    
    def get_file_paths(self) -> Optional[Dict]:
        """
        Get configuration file paths from CityFlow.
        
        Returns:
            Dict with paths to roadnet, flow, replay files or None
        """
        response = self.client.get(self.config.endpoint_get_file_paths)
        return response if response else None
    
    def check_connection(self) -> bool:
        """
        Check if simulator is reachable.
        
        Returns:
            True if connected, False otherwise
        """
        return self.client.check_connection()
    
    def close(self) -> None:
        """Close the API client."""
        self.client.close()

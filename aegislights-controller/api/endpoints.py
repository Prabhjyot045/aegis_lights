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
        Get complete network state snapshot with intersection-based structure.
        
        Expected simulator response format:
        {
            "intersections": {
                "int_1": {
                    "intersection_id": "int_1",
                    "outgoing_roads": [
                        {
                            "to_intersection": "int_2",
                            "capacity": 1.5,
                            "free_flow_time": 30.0,
                            "current_queue": 10,
                            "spillback_active": false,
                            "incident_active": false,
                            "current_delay": 5.5,
                            "current_flow": 0.8
                        },
                        ...
                    ],
                    "signal_state": "NS_GREEN",
                    "timestamp": 1234567890.0
                },
                ...
            },
            "cycle_number": 1,
            "timestamp": 1234567890.0
        }
        
        Returns:
            NetworkSnapshot object or None if failed
        """
        response = self.client.get(self.config.endpoint_get_network)
        
        if not response:
            logger.error("Failed to get network snapshot")
            return None
        
        try:
            snapshot = NetworkSnapshot(**response)
            logger.info(f"Retrieved network snapshot with {len(snapshot.intersections)} intersections")
            return snapshot
        except Exception as e:
            logger.error(f"Failed to parse network snapshot: {e}")
            return None
    
    def get_all_edges(self) -> List[EdgeData]:
        """
        [LEGACY] Get traffic data for all edges.
        Use get_network_snapshot() for new code with intersection-based structure.
        
        Returns:
            List of EdgeData objects
        """
        response = self.client.get(self.config.endpoint_get_edges)
        
        if not response:
            logger.error("Failed to get edge data")
            return []
        
        edges = []
        for edge_dict in response.get('edges', []):
            try:
                edges.append(EdgeData(**edge_dict))
            except Exception as e:
                logger.warning(f"Failed to parse edge data: {e}")
        
        return edges
    
    def get_edge(self, edge_id: str) -> Optional[EdgeData]:
        """
        Get traffic data for a specific edge.
        
        Args:
            edge_id: Edge identifier
            
        Returns:
            EdgeData object or None
        """
        response = self.client.get(
            self.config.endpoint_get_edge,
            edge_id=edge_id
        )
        
        if not response:
            return None
        
        try:
            return EdgeData(**response)
        except Exception as e:
            logger.warning(f"Failed to parse edge data for {edge_id}: {e}")
            return None
    
    def update_signal_timing(self, intersection_id: str, plan_id: str, 
                           offset: float = 0.0) -> bool:
        """
        Update signal timing for an intersection with a specific plan.
        
        Args:
            intersection_id: Intersection identifier
            plan_id: Signal plan identifier
            offset: Signal offset in seconds
            
        Returns:
            True if successful, False otherwise
        """
        config = SignalConfiguration(
            intersection_id=intersection_id,
            plan_id=plan_id,
            offset=offset
        )
        return self.set_signal_timing(config)
    
    def set_signal_timing(self, config: SignalConfiguration) -> bool:
        """
        Set signal timing for an intersection.
        
        Args:
            config: Signal configuration
            
        Returns:
            True if successful, False otherwise
        """
        response = self.client.post(
            self.config.endpoint_set_signal,
            data=config.model_dump(),
            intersection_id=config.intersection_id
        )
        
        if response and response.get('success'):
            logger.info(f"Signal timing applied for {config.intersection_id}")
            return True
        else:
            logger.error(f"Failed to apply signal timing for {config.intersection_id}")
            return False
    
    def inject_incident(self, incident: IncidentEvent) -> bool:
        """
        Inject an incident into the simulation.
        
        Args:
            incident: Incident event details
            
        Returns:
            True if successful, False otherwise
        """
        response = self.client.post(
            self.config.endpoint_inject_incident,
            data=incident.model_dump()
        )
        
        if response and response.get('success'):
            logger.info(f"Incident injected on {incident.edge_id}")
            return True
        else:
            logger.error(f"Failed to inject incident on {incident.edge_id}")
            return False
    
    def get_metrics(self) -> Optional[Dict]:
        """
        Get current simulation metrics.
        
        Returns:
            Dict of metrics or None
        """
        response = self.client.get(self.config.endpoint_get_metrics)
        return response.get('metrics') if response else None
    
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

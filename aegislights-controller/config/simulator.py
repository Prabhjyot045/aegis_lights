"""Simulator connection configuration."""

from dataclasses import dataclass


@dataclass
class SimulatorConfig:
    """Configuration for CityFlow simulator connection."""
    
    # Connection details
    host: str = "localhost"
    port: int = 8080
    base_url: str = "http://localhost:8080"
    
    # API endpoints
    endpoint_get_network: str = "/api/network/snapshot"  # New intersection-based endpoint
    endpoint_get_topology: str = "/api/network/topology"  # Static topology
    endpoint_get_edges: str = "/api/edges"  # Legacy endpoint
    endpoint_get_edge: str = "/api/edges/{edge_id}"
    endpoint_set_signal: str = "/api/signals/{intersection_id}"
    endpoint_inject_incident: str = "/api/incidents"
    endpoint_get_vehicles: str = "/api/vehicles"
    endpoint_get_metrics: str = "/api/metrics"
    
    # Connection parameters
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0
    
    # Simulator settings
    simulation_step_size: float = 1.0  # Seconds per simulation step
    
    # Network configuration file
    network_config_path: str = "config/networks/waterloo_4x4.json"
    
    def get_full_url(self, endpoint: str, **kwargs) -> str:
        """Construct full URL for an endpoint with path parameters."""
        url = f"{self.base_url}{endpoint}"
        for key, value in kwargs.items():
            url = url.replace(f"{{{key}}}", str(value))
        return url

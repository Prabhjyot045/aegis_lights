"""Simulator connection configuration."""

from dataclasses import dataclass


@dataclass
class SimulatorConfig:
    """Configuration for CityFlow simulator connection."""
    
    # Connection details
    host: str = "localhost"
    port: int = 5000
    base_url: str = "http://localhost:5000"
    
    # API endpoints (CityFlow)
    endpoint_get_network: str = "/api/v1/snapshots/latest"  # Get latest traffic snapshot
    endpoint_set_signal: str = "/api/v1/intersections/{intersection_id}/plan"  # Apply signal plan
    endpoint_get_travel_time: str = "/api/v1/gettraveltime"  # Get average travel times
    endpoint_get_file_paths: str = "/api/v1/files/paths"  # Get config file paths
    endpoint_health: str = "/health"  # Health check
    
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

"""Experiment configuration parameters."""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class ExperimentConfig:
    """Configuration for experiment parameters."""
    
    # Experiment identification
    name: str = "aegis_experiment_001"
    description: str = "AegisLights self-adaptive traffic control with CityFlow"
    
    # NOTE: Controller runs continuously, adapting every cycle_period_seconds
    # until it cannot connect to the simulator or max_duration is reached.
    # The actual network topology, traffic conditions, and incident scenarios
    # are all determined by the CityFlow simulator configuration.
    
    # Duration (maximum runtime, or None for indefinite)
    max_duration_seconds: int = None  # Run indefinitely until simulator stops or Ctrl+C
    
    # Database (absolute path relative to aegislights-controller/)
    db_path: str = None
    cleanup_on_exit: bool = False  # Set True to reset DB after run
    
    # Output and logging
    output_dir: Path = Path("output/experiments")
    record_visualization: bool = False  # Set True to record matplotlib video
    enable_web_visualizer: bool = True  # Web-based real-time visualization
    
    def __post_init__(self):
        """Ensure output directory exists and set absolute database path."""
        # Set absolute path for database relative to aegislights-controller/
        if self.db_path is None:
            controller_dir = Path(__file__).parent.parent.absolute()
            self.db_path = str(controller_dir / "data" / "aegis_lights.db")
        
        # Ensure output directory exists
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

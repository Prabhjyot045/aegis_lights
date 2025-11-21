"""Experiment configuration parameters."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExperimentConfig:
    """Configuration for experiment parameters."""
    
    # Experiment identification
    name: str = "aegis_experiment_001"
    description: str = "AegisLights self-adaptive traffic control experiment"
    
    # Duration
    duration_seconds: int = 3600  # 1 hour simulation
    
    # Random seed for reproducibility
    random_seed: int = 42
    
    # Database
    db_path: str = "data/aegis_lights.db"
    cleanup_on_exit: bool = False  # Set True to reset DB after experiment
    
    # Output
    output_dir: Path = Path("output/experiments")
    record_visualization: bool = True
    
    # Scenario
    scenario_type: str = "rush_hour"  # Options: rush_hour, incident, mixed
    num_intersections: int = 4  # Start with 4, scale to 16
    
    # Demand levels
    demand_level: str = "medium"  # Options: light, medium, heavy, extreme
    
    def __post_init__(self):
        """Ensure output directory exists."""
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

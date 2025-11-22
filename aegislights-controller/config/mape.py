"""MAPE-K loop configuration parameters."""

from dataclasses import dataclass


@dataclass
class MAPEConfig:
    """Configuration for MAPE-K control loop."""
    
    # Loop timing
    cycle_period_seconds: int = 60  # Control cycle period
    
    # Monitor parameters
    rolling_window_size: int = 5  # Number of cycles for smoothing
    data_collection_interval: float = 1.0  # Seconds between data polls
    congestion_queue_threshold: int = 20  # Queue threshold for high congestion detection
    
    # Analyze parameters
    k_shortest_paths: int = 3  # Number of alternative routes to consider
    hotspot_threshold: float = 0.7  # Threshold for identifying congested edges
    trend_alpha: float = 0.3  # Exponential smoothing parameter for trends
    
    # Plan parameters
    bandit_algorithm: str = "ucb"  # Options: ucb, thompson_sampling
    exploration_factor: float = 0.2  # Balance exploration vs exploitation
    coordination_enabled: bool = True  # Enable offset coordination
    
    # Execute parameters
    apply_at_cycle_boundary: bool = True  # Safety: only apply at cycle boundaries
    max_rate_of_change: float = 0.15  # Max 15% change per cycle
    
    # Rollback parameters
    rollback_window_size: int = 3  # Cycles to track for performance degradation
    performance_degradation_threshold: float = 0.1  # 10% worse triggers rollback
    enable_rollback: bool = True
    
    # Incident handling
    incident_mode_enabled: bool = True
    incident_detection_threshold: float = 0.9  # High confidence for incident flag
    
    # Performance metrics
    metrics_calculation_interval: int = 1  # Calculate metrics every N cycles

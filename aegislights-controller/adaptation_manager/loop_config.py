"""Additional loop-specific configuration."""

from dataclasses import dataclass


@dataclass
class LoopConfig:
    """Runtime configuration for the MAPE loop."""
    
    # Logging verbosity per stage
    monitor_verbose: bool = True
    analyze_verbose: bool = True
    plan_verbose: bool = True
    execute_verbose: bool = True
    
    # Performance tracking
    track_stage_timing: bool = True
    log_decisions: bool = True
    
    # Emergency stop conditions
    max_consecutive_failures: int = 5
    emergency_stop_on_simulator_disconnect: bool = True

"""Time synchronization utilities."""

import time
from typing import Tuple


def sync_time(cycle_period: float, cycle_start: float) -> float:
    """
    Calculate sleep time to synchronize with cycle boundaries.
    
    Args:
        cycle_period: Length of control cycle in seconds
        cycle_start: Start time of current cycle
        
    Returns:
        Seconds to sleep until next cycle boundary
    """
    elapsed = time.time() - cycle_start
    sleep_time = max(0, cycle_period - elapsed)
    return sleep_time


def get_cycle_time(cycle_number: int, cycle_period: float, 
                  start_time: float) -> Tuple[float, float]:
    """
    Calculate absolute time range for a cycle.
    
    Args:
        cycle_number: Cycle number
        cycle_period: Length of control cycle in seconds
        start_time: Experiment start timestamp
        
    Returns:
        Tuple of (cycle_start_time, cycle_end_time)
    """
    cycle_start = start_time + (cycle_number - 1) * cycle_period
    cycle_end = cycle_start + cycle_period
    return cycle_start, cycle_end


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "1h 23m 45s")
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    
    return " ".join(parts)

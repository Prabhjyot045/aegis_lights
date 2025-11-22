"""Rollback manager for performance degradation detection."""

import logging
from typing import Dict, List, Optional
from collections import deque

from .knowledge import KnowledgeBase
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class RollbackManager:
    """Monitors performance and triggers rollback on degradation."""
    
    def __init__(self, knowledge: KnowledgeBase, mape_config: MAPEConfig):
        """
        Initialize rollback manager.
        
        Args:
            knowledge: Knowledge base interface
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.config = mape_config
        
        # Rolling window of performance metrics
        self.performance_window: deque = deque(
            maxlen=mape_config.rollback_window_size
        )
        self.baseline_utility: Optional[float] = None
        
    def check_for_degradation(self, cycle: int, metrics: Dict) -> bool:
        """
        Check if performance has degraded beyond threshold.
        
        Args:
            cycle: Current cycle number
            metrics: Current performance metrics
            
        Returns:
            True if rollback should be triggered
        """
        # Calculate utility score
        utility = self._calculate_utility(metrics)
        
        # Add to rolling window
        self.performance_window.append({
            'cycle': cycle,
            'utility': utility,
            'metrics': metrics
        })
        
        # Need sufficient data before checking
        if len(self.performance_window) < self.config.rollback_window_size:
            return False
        
        # Establish baseline if not set
        if self.baseline_utility is None:
            self.baseline_utility = utility
            return False
        
        # Check for consistent degradation
        recent_utilities = [w['utility'] for w in self.performance_window]
        avg_recent = sum(recent_utilities) / len(recent_utilities)
        
        degradation = (self.baseline_utility - avg_recent) / self.baseline_utility
        
        if degradation > self.config.performance_degradation_threshold:
            logger.warning(
                f"Performance degraded {degradation:.2%} "
                f"(threshold: {self.config.performance_degradation_threshold:.2%})"
            )
            return True
        
        # Update baseline if performance improved
        if utility > self.baseline_utility:
            self.baseline_utility = utility
        
        return False
    
    def _calculate_utility(self, metrics: Dict) -> float:
        """
        Calculate utility score from metrics.
        Higher is better (lower cost = higher utility).
        
        Args:
            metrics: Performance metrics dict
            
        Returns:
            Utility score (negative of total cost)
        """
        # Components of cost (all negative contributors)
        avg_trip_time = metrics.get('avg_trip_time', 0)
        p95_trip_time = metrics.get('p95_trip_time', 0)
        total_spillbacks = metrics.get('total_spillbacks', 0)
        total_stops = metrics.get('total_stops', 0)
        incident_clearance = metrics.get('incident_clearance_time', 0)
        
        # Weight factors for different cost components
        time_weight = 1.0        # Cost per second of average travel time
        p95_weight = 0.5         # Cost for tail latency
        spillback_penalty = 20.0 # High penalty for spillback events
        stop_cost = 0.1          # Cost per vehicle stop (fuel, emissions)
        incident_weight = 5.0    # Cost for unresolved incidents
        
        # Calculate total cost
        total_cost = (
            avg_trip_time * time_weight +
            p95_trip_time * p95_weight +
            total_spillbacks * spillback_penalty +
            total_stops * stop_cost +
            incident_clearance * incident_weight
        )
        
        # Utility is negative of cost (higher utility = better performance)
        utility = -total_cost
        return utility
    
    def reset(self) -> None:
        """Reset rollback manager state."""
        self.performance_window.clear()
        self.baseline_utility = None
        logger.debug("Rollback manager reset")

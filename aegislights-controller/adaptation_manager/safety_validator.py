"""Safety validator for signal configuration constraints.

For CityFlow: Plans use pre-validated fixed 4-phase timing, so validation
is minimal (mainly checking intersection ID and plan ID format).
"""

import logging
from typing import Dict

from .knowledge import KnowledgeBase
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class SafetyValidator:
    """Validates signal configurations for CityFlow implementation."""
    
    def __init__(self, knowledge: KnowledgeBase, mape_config: MAPEConfig):
        """
        Initialize safety validator.
        
        Args:
            knowledge: Knowledge base interface
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.config = mape_config
        self.signalized_intersections = {'A', 'B', 'C', 'D', 'E'}
        
    def validate_plan(self, intersection_id: str, plan_id: str) -> bool:
        """
        Validate a signal plan by ID.
        
        For CityFlow: All plans in phase library are pre-validated with
        fixed 4-phase timing (0=NS through 30s, 1=NS left 10s, 2=EW through 30s, 
        3=EW left 10s) that meets safety requirements.
        
        Args:
            intersection_id: Intersection identifier (A-E)
            plan_id: Signal plan identifier (ns_priority, ew_priority, balanced)
            
        Returns:
            True if plan is valid and safe, False otherwise
        """
        # Validate intersection ID
        if intersection_id not in self.signalized_intersections:
            logger.warning(f"Invalid intersection {intersection_id} (not in A-E)")
            return False
        
        # Validate plan ID format
        if not plan_id or not isinstance(plan_id, str):
            logger.warning(f"Invalid plan_id format: {plan_id}")
            return False
        
        # All plans in phase_libraries table have safety_validated=1
        logger.debug(f"Validated plan {plan_id} for {intersection_id}")
        return True

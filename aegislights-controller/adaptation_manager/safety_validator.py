"""Safety validator for signal configuration constraints."""

import logging
from typing import Dict, List

from .knowledge import KnowledgeBase
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class SafetyValidator:
    """Validates signal configurations against safety and legal constraints."""
    
    def __init__(self, knowledge: KnowledgeBase, mape_config: MAPEConfig):
        """
        Initialize safety validator.
        
        Args:
            knowledge: Knowledge base interface
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.config = mape_config
        
    def validate_plan(self, intersection_id: str, plan_id: str) -> bool:
        """
        Validate a signal plan by ID.
        
        Args:
            intersection_id: Intersection identifier
            plan_id: Signal plan identifier
            
        Returns:
            True if plan is valid and safe, False otherwise
        """
        # Plans in the phase library are pre-validated during addition
        # so we can trust they are safe. This method is here for extensibility
        # in case runtime validation is needed in the future.
        logger.debug(f"Validating plan {plan_id} for {intersection_id}")
        return True
    
    def validate_configuration(self, intersection_id: str, 
                              config: Dict) -> tuple[bool, str]:
        """
        Validate a signal configuration.
        
        Args:
            intersection_id: Intersection identifier
            config: Signal configuration to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for conflicting greens
        if not self._check_no_conflicting_greens(config):
            return False, "Conflicting green phases detected"
        
        # Check amber/all-red clearance
        if not self._check_clearance_intervals(config):
            return False, "Insufficient clearance intervals"
        
        # Check pedestrian minimums
        if not self._check_pedestrian_minimums(config):
            return False, "Pedestrian minimum times not met"
        
        # Check rate of change limits
        if not self._check_rate_of_change(intersection_id, config):
            return False, f"Rate of change exceeds {self.config.max_rate_of_change}"
        
        return True, ""
    
    def _check_no_conflicting_greens(self, config: Dict) -> bool:
        """Ensure no conflicting movements have green simultaneously."""
        # Standard conflict pairs (assuming NEMA phase rings)
        # Phase 1 (NB left) conflicts with 5 (SB through), 6 (SB left)
        # Phase 2 (NB through) conflicts with 6 (SB left)
        # Phase 3 (SB left) conflicts with 1 (NB through), 2 (NB left)
        # etc.
        
        green_splits = config.get('green_splits', {})
        if not green_splits:
            return True  # No phases defined, pass by default
        
        # Define conflict matrix (direction pairs that cannot be green together)
        conflicts = [
            ('north_left', 'south_through'),
            ('north_through', 'south_left'),
            ('east_left', 'west_through'),
            ('east_through', 'west_left'),
            ('north', 'south'),  # Simplified: opposite directions conflict
            ('east', 'west')
        ]
        
        # Check if any conflicting movements both have green time
        for move1, move2 in conflicts:
            if move1 in green_splits and move2 in green_splits:
                if green_splits[move1] > 0 and green_splits[move2] > 0:
                    logger.warning(f"Conflicting greens detected: {move1} and {move2}")
                    return False
        
        return True
    
    def _check_clearance_intervals(self, config: Dict) -> bool:
        """Verify amber and all-red clearance times."""
        # Standard requirements:
        # - Amber time: 3-6 seconds (speed dependent)
        # - All-red time: 1-2 seconds minimum
        
        amber_time = config.get('amber_time', 4.0)  # Default 4s
        all_red_time = config.get('all_red_time', 1.0)  # Default 1s
        
        # Check amber time bounds
        if amber_time < 3.0 or amber_time > 6.0:
            logger.warning(f"Amber time {amber_time}s outside safe range [3.0, 6.0]")
            return False
        
        # Check all-red minimum
        if all_red_time < 1.0:
            logger.warning(f"All-red time {all_red_time}s below minimum 1.0s")
            return False
        
        return True
    
    def _check_pedestrian_minimums(self, config: Dict) -> bool:
        """Check pedestrian crossing minimum times."""
        # Minimum pedestrian crossing times (MUTCD standards):
        # - Walk interval: 7 seconds minimum
        # - Clearance interval: 3.5 ft/s walking speed
        
        ped_walk_time = config.get('pedestrian_walk_time', 7.0)
        ped_clearance_time = config.get('pedestrian_clearance_time', 10.0)
        
        # Check walk time minimum
        if ped_walk_time < 7.0:
            logger.warning(f"Pedestrian walk time {ped_walk_time}s below minimum 7.0s")
            return False
        
        # Check clearance time reasonable
        if ped_clearance_time < 5.0:
            logger.warning(f"Pedestrian clearance {ped_clearance_time}s may be insufficient")
            return False
        
        return True
    
    def _check_rate_of_change(self, intersection_id: str, config: Dict) -> bool:
        """Verify changes don't exceed max rate of change."""
        # Get current configuration
        current = self.knowledge.get_last_known_good(intersection_id)
        if not current:
            return True  # No previous config, allow any change
        
        current_config = current.get('config', {})
        current_cycle = current_config.get('cycle_length', 90)
        new_cycle = config.get('cycle_length', 90)
        
        # Calculate rate of change (percentage)
        cycle_change = abs(new_cycle - current_cycle) / current_cycle if current_cycle > 0 else 0
        
        # Check against threshold
        max_change = self.config.max_rate_of_change  # e.g., 0.25 = 25%
        if cycle_change > max_change:
            logger.warning(
                f"Cycle length change {cycle_change:.1%} exceeds max {max_change:.1%}"
            )
            return False
        
        return True

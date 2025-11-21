"""Phase library for managing pre-verified signal timing plans."""

import logging
import json
from typing import Dict, List, Optional

from adaptation_manager.knowledge import KnowledgeBase
from db_manager.db_utils import get_connection, close_connection

logger = logging.getLogger(__name__)


class PhaseLibrary:
    """Manages pre-verified signal timing plans for intersections."""
    
    def __init__(self, knowledge: KnowledgeBase):
        """
        Initialize phase library.
        
        Args:
            knowledge: Knowledge base interface
        """
        self.knowledge = knowledge
        self._cache: Dict[str, List[Dict]] = {}
    
    def get_plans(self, intersection_id: str) -> List[Dict]:
        """
        Get all valid plans for an intersection.
        
        Args:
            intersection_id: Intersection identifier
            
        Returns:
            List of valid plan dictionaries
        """
        # Check cache first
        if intersection_id in self._cache:
            return self._cache[intersection_id]
        
        # Query database
        conn = get_connection(self.knowledge.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM phase_libraries 
            WHERE intersection_id = ? AND safety_validated = 1
        """, (intersection_id,))
        
        plans = []
        for row in cursor.fetchall():
            plans.append({
                'plan_id': row['plan_id'],
                'intersection_id': row['intersection_id'],
                'plan_name': row['plan_name'],
                'phases': json.loads(row['phases']) if row['phases'] else {},
                'pedestrian_compliant': bool(row['pedestrian_compliant']),
                'safety_validated': bool(row['safety_validated'])
            })
        
        close_connection(conn)
        
        # Cache the results
        self._cache[intersection_id] = plans
        
        logger.debug(f"Loaded {len(plans)} plans for intersection {intersection_id}")
        return plans
    
    def add_plan(self, intersection_id: str, plan_name: str, 
                phases: Dict, pedestrian_compliant: bool = True) -> str:
        """
        Add a new verified plan to the library.
        
        Args:
            intersection_id: Intersection identifier
            plan_name: Human-readable plan name
            phases: Phase configuration dict
            pedestrian_compliant: Whether plan meets pedestrian requirements
            
        Returns:
            Generated plan_id
        """
        plan_id = f"{intersection_id}_{plan_name}".replace(" ", "_")
        
        conn = get_connection(self.knowledge.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO phase_libraries
            (plan_id, intersection_id, plan_name, phases, pedestrian_compliant, safety_validated)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (plan_id, intersection_id, plan_name, json.dumps(phases), 
              int(pedestrian_compliant)))
        
        conn.commit()
        close_connection(conn)
        
        # Invalidate cache
        if intersection_id in self._cache:
            del self._cache[intersection_id]
        
        logger.info(f"Added plan {plan_id} to library")
        return plan_id
    
    def load_default_plans(self, intersection_ids: List[str] = None) -> None:
        """Load default signal timing plans for standard intersection types."""
        logger.info("Loading default signal timing plans")
        
        # Default 2-phase plan (simple N-S, E-W)
        default_2phase = {
            'cycle_length': 90,
            'green_splits': {
                'north': 35,
                'south': 35,
                'east': 20,
                'west': 20
            },
            'amber_time': 4.0,
            'all_red_time': 1.0,
            'pedestrian_walk_time': 7.0,
            'pedestrian_clearance_time': 10.0
        }
        
        # Default 3-phase plan (with protected left turns)
        default_3phase = {
            'cycle_length': 120,
            'green_splits': {
                'north_through': 30,
                'north_left': 10,
                'south_through': 30,
                'south_left': 10,
                'east': 20,
                'west': 20
            },
            'amber_time': 4.0,
            'all_red_time': 1.0,
            'pedestrian_walk_time': 7.0,
            'pedestrian_clearance_time': 12.0
        }
        
        # If specific intersections provided, load for them
        # Otherwise, this is available for manual addition
        if intersection_ids:
            for int_id in intersection_ids:
                try:
                    # Add 2-phase plan
                    self.add_plan(int_id, 'default_2phase', default_2phase)
                    # Add 3-phase plan
                    self.add_plan(int_id, 'default_3phase', default_3phase)
                    logger.info(f"Loaded default plans for {int_id}")
                except Exception as e:
                    logger.error(f"Failed to load default plans for {int_id}: {e}")
        else:
            logger.info("Default plans ready for manual loading")
        
        logger.info("Loading default phase plans")
        
        # Example: Simple 2-phase plan
        default_2_phase = {
            'cycle_length': 90.0,
            'green_splits': {
                'phase_1_ns': 40.0,  # North-South
                'phase_2_ew': 40.0   # East-West
            },
            'amber': 3.0,
            'all_red': 2.0,
            'min_green': 10.0,
            'max_green': 60.0,
            'pedestrian_time': 15.0
        }
        
        # Add to library for demo intersections
        for i in range(1, 5):
            intersection_id = f"intersection_{i}"
            self.add_plan(intersection_id, "default_2phase", default_2_phase)
    
    def clear_cache(self) -> None:
        """Clear the phase library cache."""
        self._cache.clear()
        logger.debug("Phase library cache cleared")

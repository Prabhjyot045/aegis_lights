"""Phase library for managing CityFlow signal timing plans."""

import logging
import json
from typing import Dict, List, Optional

from db_manager.db_utils import get_connection, close_connection

logger = logging.getLogger(__name__)


class PhaseLibrary:
    """
    Manages signal timing plans for CityFlow intersections.
    
    CityFlow uses fixed 4-phase timing structure:
    - Phase 0 (30s): Main through movements
    - Phase 1 (10s): Left turns from main directions
    - Phase 2 (30s): Cross through movements  
    - Phase 3 (10s): Left turns from cross directions
    
    Plans map to phase indices (0-3) rather than custom green splits.
    """
    
    # CityFlow intersection IDs (only signalized, not virtual nodes)
    SIGNALIZED_INTERSECTIONS = ['A', 'B', 'C', 'D', 'E']
    
    # Phase indices for CityFlow
    PHASE_NS_PRIORITY = 0  # North-South through movements get priority
    PHASE_NS_LEFT = 1      # North-South left turns
    PHASE_EW_PRIORITY = 2  # East-West through movements get priority
    PHASE_EW_LEFT = 3      # East-West left turns
    
    def __init__(self, db_path: str):
        """
        Initialize phase library.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._cache: Dict[str, List[Dict]] = {}
    
    def get_plans(self, intersection_id: str) -> List[Dict]:
        """
        Get all valid plans for an intersection.
        
        Args:
            intersection_id: Intersection identifier (A, B, C, D, E)
            
        Returns:
            List of valid plan dictionaries with phase_id mappings
        """
        # Check cache first
        if intersection_id in self._cache:
            return self._cache[intersection_id]
        
        # Query database
        conn = get_connection(self.db_path)
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
            intersection_id: Intersection identifier (A-E)
            plan_name: Human-readable plan name
            phases: Phase configuration dict with phase_id and timing info
            pedestrian_compliant: Whether plan meets pedestrian requirements
            
        Returns:
            Generated plan_id
        """
        plan_id = f"{intersection_id}_{plan_name}".replace(" ", "_")
        
        conn = get_connection(self.db_path)
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
    
    def load_default_plans(self) -> None:
        """
        Load default CityFlow signal timing plans for all signalized intersections.
        
        Creates 3 plans per intersection:
        1. NS Priority (Phase 0) - North-South gets more green time
        2. EW Priority (Phase 2) - East-West gets more green time  
        3. Balanced (Phase 0/2 alternating) - Equal priority
        """
        logger.info("Loading CityFlow default signal timing plans")
        
        # Plan 1: North-South Priority
        # Uses Phase 0 (30s NS through) as primary
        ns_priority = {
            'primary_phase': 0,
            'phase_id': 0,
            'description': 'North-South through movements prioritized',
            'cycle_length': 80,  # Total: 30+10+30+10
            'timing': {
                'phase_0': 30,  # NS through
                'phase_1': 10,  # NS left
                'phase_2': 30,  # EW through
                'phase_3': 10   # EW left
            },
            'use_cases': ['morning_rush_ns', 'evening_rush_ns', 'default']
        }
        
        # Plan 2: East-West Priority
        # Uses Phase 2 (30s EW through) as primary
        ew_priority = {
            'primary_phase': 2,
            'phase_id': 2,
            'description': 'East-West through movements prioritized',
            'cycle_length': 80,
            'timing': {
                'phase_0': 30,  # NS through
                'phase_1': 10,  # NS left
                'phase_2': 30,  # EW through
                'phase_3': 10   # EW left
            },
            'use_cases': ['morning_rush_ew', 'evening_rush_ew']
        }
        
        # Plan 3: Balanced (Adaptive)
        # Alternates between Phase 0 and 2 based on traffic
        balanced = {
            'primary_phase': 0,  # Start with NS
            'phase_id': 0,
            'description': 'Balanced priority, adapts based on traffic',
            'cycle_length': 80,
            'timing': {
                'phase_0': 30,
                'phase_1': 10,
                'phase_2': 30,
                'phase_3': 10
            },
            'use_cases': ['low_traffic', 'balanced_demand', 'incident_recovery']
        }
        
        # Add plans for all signalized intersections
        for intersection_id in self.SIGNALIZED_INTERSECTIONS:
            try:
                # Add NS priority plan
                self.add_plan(
                    intersection_id, 
                    '2phase_ns_priority', 
                    ns_priority,
                    pedestrian_compliant=True
                )
                
                # Add EW priority plan
                self.add_plan(
                    intersection_id,
                    '2phase_ew_priority',
                    ew_priority,
                    pedestrian_compliant=True
                )
                
                # Add balanced plan
                self.add_plan(
                    intersection_id,
                    '2phase_balanced',
                    balanced,
                    pedestrian_compliant=True
                )
                
                logger.info(f"Loaded 3 default plans for intersection {intersection_id}")
                
            except Exception as e:
                logger.error(f"Failed to load default plans for {intersection_id}: {e}")
        
        logger.info(f"Loaded default plans for {len(self.SIGNALIZED_INTERSECTIONS)} intersections")
    
    def get_phase_id_for_plan(self, plan_id: str) -> int:
        """
        Extract CityFlow phase_id from a plan.
        
        Args:
            plan_id: Plan identifier (e.g., 'A_2phase_ns_priority')
            
        Returns:
            Phase index (0-3)
        """
        # Extract intersection and plan name
        parts = plan_id.split('_', 1)
        if len(parts) < 2:
            logger.warning(f"Invalid plan_id format: {plan_id}, defaulting to phase 0")
            return 0
        
        intersection_id = parts[0]
        plan_name = parts[1]
        
        # Get plan from database/cache
        plans = self.get_plans(intersection_id)
        for plan in plans:
            if plan['plan_id'] == plan_id:
                phases = plan.get('phases', {})
                return phases.get('phase_id', 0)
        
        # Default mapping based on plan name
        if 'ns_priority' in plan_name.lower():
            return self.PHASE_NS_PRIORITY  # 0
        elif 'ew_priority' in plan_name.lower():
            return self.PHASE_EW_PRIORITY  # 2
        elif 'balanced' in plan_name.lower():
            return self.PHASE_NS_PRIORITY  # 0 (start with NS)
        
        logger.warning(f"Could not determine phase_id for {plan_id}, defaulting to 0")
        return 0
    
    def get_plan_by_id(self, plan_id: str) -> Optional[Dict]:
        """
        Get a specific plan by its ID.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            Plan dictionary or None if not found
        """
        # Extract intersection from plan_id (format: "A_2phase_ns_priority")
        intersection_id = plan_id.split('_')[0]
        
        plans = self.get_plans(intersection_id)
        for plan in plans:
            if plan['plan_id'] == plan_id:
                return plan
        
        return None
    
    def clear_cache(self) -> None:
        """Clear the phase library cache."""
        self._cache.clear()
        logger.debug("Phase library cache cleared")
    
    def validate_intersection(self, intersection_id: str) -> bool:
        """
        Validate that an intersection is signalized (not virtual).
        
        Args:
            intersection_id: Intersection to validate
            
        Returns:
            True if signalized, False if virtual or invalid
        """
        is_valid = intersection_id in self.SIGNALIZED_INTERSECTIONS
        if not is_valid:
            logger.warning(f"Invalid intersection for signal control: {intersection_id}")
        return is_valid

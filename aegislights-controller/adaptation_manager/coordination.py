"""Coordination planner for offset calculation and green waves."""

import logging
from typing import Dict, List

from .knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class CoordinationPlanner:
    """Plans signal offsets for coordination and green waves."""
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph,
                 mape_config: MAPEConfig):
        """
        Initialize coordination planner.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.graph = graph
        self.config = mape_config
        
    def apply_coordination(self, adaptations: List[Dict],
                          analysis_result: Dict) -> List[Dict]:
        """
        Apply offset coordination to adaptations based on bypass routes.
        
        Args:
            adaptations: List of planned adaptations
            analysis_result: Analysis results with bypass routes
            
        Returns:
            Updated adaptations with coordinated offsets
        """
        if not self.config.coordination_enabled:
            return adaptations
        
        # Get bypass routes that need coordination
        bypasses = analysis_result.get('bypasses', [])
        
        if not bypasses:
            return adaptations
        
        # Group intersections into coordination zones
        coord_groups = self._identify_coordination_groups(bypasses)
        
        # Calculate offsets for each group
        for group in coord_groups:
            self._calculate_offsets(group, adaptations)
        
        logger.debug(f"Applied coordination to {len(coord_groups)} groups")
        
        return adaptations
    
    def _identify_coordination_groups(self, bypasses: List) -> List[List[str]]:
        """
        Identify groups of intersections that should be coordinated.
        
        Args:
            bypasses: List of bypass routes
            
        Returns:
            List of coordination groups (lists of intersection IDs)
        """
        # Each bypass route is a potential coordination group
        # We want to coordinate signals along these routes for green waves
        groups = []
        
        for bypass in bypasses:
            if len(bypass) >= 2:
                # Only coordinate if there are at least 2 intersections
                groups.append(bypass)
                logger.debug(f"Created coordination group: {bypass}")
        
        return groups
    
    def _calculate_offsets(self, group: List[str], 
                          adaptations: List[Dict]) -> None:
        """
        Calculate optimal offsets for a coordination group.
        Creates green wave progression.
        
        Args:
            group: List of intersection IDs in coordination group
            adaptations: List of adaptations to update
        """
        logger.debug(f"Calculating offsets for group of {len(group)} intersections")
        
        # Start with the first intersection as reference (offset = 0)
        cumulative_offset = 0.0
        
        for i, intersection_id in enumerate(group):
            # Find the adaptation for this intersection
            adaptation = None
            for adapt in adaptations:
                if adapt['intersection_id'] == intersection_id:
                    adaptation = adapt
                    break
            
            if not adaptation:
                logger.warning(f"No adaptation found for intersection {intersection_id} in coordination group")
                continue
            
            # Set offset for this intersection
            adaptation['offset'] = cumulative_offset
            
            # Calculate offset to next intersection if not the last one
            if i < len(group) - 1:
                next_intersection = group[i + 1]
                
                # Get travel time to next intersection
                # Look for edge in graph between these intersections
                edge_key = (intersection_id, next_intersection)
                
                if edge_key in self.graph.edges:
                    edge_data = self.graph.edges[edge_key]
                    # Travel time = distance / speed
                    # Assuming edge has 'length' in meters and 'speed_limit' in m/s
                    travel_time = edge_data.get('travel_time', 0.0)
                    
                    # If travel_time not stored, calculate it
                    if travel_time == 0.0:
                        length = edge_data.get('length', 100.0)  # Default 100m
                        speed = edge_data.get('speed_limit', 13.89)  # Default 50 km/h = 13.89 m/s
                        travel_time = length / speed if speed > 0 else 0.0
                    
                    # Accumulate offset (time in seconds)
                    cumulative_offset += travel_time
                    logger.debug(f"Offset for {intersection_id}: {adaptation['offset']:.2f}s, travel time to next: {travel_time:.2f}s")
                else:
                    logger.debug(f"No edge found between {intersection_id} and {next_intersection}, using default offset")
                    # Use a default offset if no edge exists
                    cumulative_offset += 30.0  # Default 30 seconds
            else:
                # Last intersection in group
                logger.debug(f"Offset for {intersection_id}: {adaptation['offset']:.2f}s (last in group)")

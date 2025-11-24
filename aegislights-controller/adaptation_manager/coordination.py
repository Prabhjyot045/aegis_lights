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
    
    def _identify_coordination_groups(self, bypasses: List[Dict]) -> List[List[str]]:
        """
        Identify groups of intersections that should be coordinated.
        
        Extracts intersection sequences from bypass route paths.
        
        Args:
            bypasses: List of bypass route dictionaries with 'path' field
            
        Returns:
            List of coordination groups (lists of intersection IDs)
        """
        groups = []
        
        for bypass in bypasses:
            # Extract unique intersections from the bypass path
            path = bypass.get('path', [])
            if not path:
                continue
            
            # Get unique intersections in order (from edge tuples)
            intersections = []
            seen = set()
            for edge_tuple in path:
                from_int = edge_tuple[0]
                to_int = edge_tuple[1]
                if from_int not in seen:
                    intersections.append(from_int)
                    seen.add(from_int)
                if to_int not in seen:
                    intersections.append(to_int)
                    seen.add(to_int)
            
            # Only create group if at least 2 signalized intersections
            signalized = [i for i in intersections if i in {'A', 'B', 'C', 'D', 'E'}]
            if len(signalized) >= 2:
                groups.append(signalized)
                logger.debug(f"Created coordination group: {signalized}")
        
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
                edge = self.graph.get_edge(intersection_id, next_intersection)
                
                if edge:
                    # Use free flow time as basis for offset
                    # This creates green wave: signal turns green when platoon arrives
                    travel_time = edge.free_flow_time
                    
                    # Adjust for current delay (conservative: add some buffer)
                    if edge.current_delay > 0:
                        travel_time += edge.current_delay * 0.3  # Add 30% of delay as buffer
                    
                    # Accumulate offset (time in seconds)
                    cumulative_offset += travel_time
                    logger.debug(f"Offset for {intersection_id}: {adaptation['offset']:.2f}s, "
                               f"travel time to next: {travel_time:.2f}s")
                else:
                    logger.debug(f"No edge found between {intersection_id} and {next_intersection}, "
                               f"using default offset")
                    # Use a default offset if no edge exists
                    cumulative_offset += 20.0  # Default 20 seconds
            else:
                # Last intersection in group
                logger.debug(f"Offset for {intersection_id}: {adaptation['offset']:.2f}s (last in group)")

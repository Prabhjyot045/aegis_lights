"""Incident detection and handling."""

import logging
from typing import Dict, List, Any

from .knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class IncidentHandler:
    """Handles incident detection and incident-aware planning."""
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph,
                 mape_config: MAPEConfig):
        """
        Initialize incident handler.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.graph = graph
        self.config = mape_config
        self.active_incidents: List[Dict] = []
        
    def detect_incidents(self, cycle: int, monitor_data: Dict) -> List[Dict]:
        """
        Detect active incidents from monitor data.
        
        Args:
            cycle: Current cycle number
            monitor_data: Data from Monitor stage
            
        Returns:
            List of detected incidents
        """
        incidents = []
        
        for edge_data in monitor_data.get('edges', []):
            if edge_data.get('incident_flag'):
                incidents.append({
                    'edge_id': edge_data['edge_id'],
                    'detected_cycle': cycle,
                    'type': 'incident'
                })
        
        # Update active incidents list
        self.active_incidents = incidents
        
        if incidents:
            logger.warning(f"Detected {len(incidents)} active incidents")
        
        return incidents
    
    def select_incident_plan(self, intersection_id: str, context: Dict,
                           valid_plans: List[Dict], 
                           analysis_result: Dict) -> Dict:
        """
        Select plan for incident mode.
        Prioritizes clearing affected areas and routing around incidents.
        
        For CityFlow:
        - If on bypass route: Select plan that favors bypass direction
        - If has incident: Select balanced plan to clear queues
        - Otherwise: Use default plan selection
        
        Args:
            intersection_id: Intersection identifier
            context: Context features
            valid_plans: Valid plans from phase library
            analysis_result: Analysis results with bypass routes
            
        Returns:
            Selected plan dictionary
        """
        logger.debug(f"Selecting incident plan for {intersection_id}")
        
        if not valid_plans:
            return {}
        
        # Check if this intersection is on a bypass route
        bypasses = analysis_result.get('bypasses', [])
        is_on_bypass = False
        bypass_direction = None
        
        for bypass in bypasses:
            path = bypass.get('path', [])
            for edge_tuple in path:
                if edge_tuple[0] == intersection_id:
                    is_on_bypass = True
                    # Determine which direction the bypass favors
                    to_int = edge_tuple[1]
                    if to_int in {'A', 'C', 'E'}:  # Vertical
                        bypass_direction = 'ns'
                    else:  # Horizontal
                        bypass_direction = 'ew'
                    break
            if is_on_bypass:
                break
        
        # Check if incident affects this intersection's outgoing edges
        incidents = analysis_result.get('incidents', [])
        has_nearby_incident = any(
            incident.get('from') == intersection_id
            for incident in incidents
        )
        
        # Strategy: Select plan based on situation
        if is_on_bypass and bypass_direction:
            # Favor the bypass direction
            if bypass_direction == 'ns':
                # Prefer NS priority plans
                for plan in valid_plans:
                    if 'ns_priority' in plan.get('plan_id', '').lower():
                        logger.info(f"Selected NS-priority plan for bypass at {intersection_id}")
                        return plan
            else:
                # Prefer EW priority plans
                for plan in valid_plans:
                    if 'ew_priority' in plan.get('plan_id', '').lower():
                        logger.info(f"Selected EW-priority plan for bypass at {intersection_id}")
                        return plan
        
        if has_nearby_incident:
            # Use balanced plan to distribute load
            for plan in valid_plans:
                if 'balanced' in plan.get('plan_id', '').lower():
                    logger.info(f"Selected balanced plan for incident at {intersection_id}")
                    return plan
        
        # Fallback: select first available plan
        best_plan = valid_plans[0]
        logger.debug(f"Selected default plan for {intersection_id}")
        return best_plan
    
    def get_affected_edges(self, incident: Dict) -> List[str]:
        """Get edges affected by an incident."""
        affected_edges = []
        
        # Primary affected edge
        if 'edge_id' in incident:
            affected_edges.append(incident['edge_id'])
        
        # Get edges from incident location
        if 'intersection_id' in incident:
            intersection_id = incident['intersection_id']
            # All outgoing edges from incident intersection are affected
            node = self.graph.nodes.get(intersection_id)
            if node:
                for edge_key in self.graph.edges:
                    if edge_key[0] == intersection_id:
                        affected_edges.append(f"{edge_key[0]}_{edge_key[1]}")
        
        # Add upstream/downstream edges if incident causes spillback
        if incident.get('severity') == 'high':
            # High severity incidents affect adjacent edges
            for edge_id in list(affected_edges):
                parts = edge_id.split('_')
                if len(parts) >= 2:
                    from_int = parts[0]
                    # Add upstream edges
                    for edge_key in self.graph.edges:
                        if edge_key[1] == from_int:
                            affected_edges.append(f"{edge_key[0]}_{edge_key[1]}")
        
        return list(set(affected_edges))  # Remove duplicates
    
    def get_clearance_time(self, incident: Dict, current_cycle: int) -> float:
        """Calculate time to clear an incident."""
        detected_cycle = incident.get('detected_cycle', current_cycle)
        duration = current_cycle - detected_cycle
        return duration * self.config.cycle_period_seconds

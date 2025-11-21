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
        
        Args:
            intersection_id: Intersection identifier
            context: Context features
            valid_plans: Valid plans from phase library
            analysis_result: Analysis results with bypass routes
            
        Returns:
            Selected plan
        """
        logger.debug(f"Selecting incident plan for {intersection_id}")
        
        if not valid_plans:
            return {}
        
        # Check if this intersection is on a bypass route
        bypass_routes = analysis_result.get('bypass_routes', [])
        is_on_bypass = any(
            intersection_id in route for route in bypass_routes
        )
        
        # Check if incident affects this intersection
        incidents = analysis_result.get('incidents', [])
        has_nearby_incident = any(
            incident.get('intersection_id') == intersection_id or
            intersection_id in incident.get('affected_intersections', [])
            for incident in incidents
        )
        
        # Strategy: If on bypass route, prefer longer green times
        # If near incident, prefer clearing queues quickly
        if is_on_bypass:
            # Select plan with longer cycle to accommodate more flow
            best_plan = max(valid_plans, key=lambda p: p.get('cycle_length', 90))
            logger.debug(f"Selected bypass-optimized plan for {intersection_id}")
            return best_plan
        elif has_nearby_incident:
            # Select plan with shorter cycle for more responsive clearing
            best_plan = min(valid_plans, key=lambda p: p.get('cycle_length', 90))
            logger.debug(f"Selected incident-clearing plan for {intersection_id}")
            return best_plan
        else:
            # Use first available plan as default
            return valid_plans[0]
    
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

"""Plan stage: Select signal timing plans using contextual bandits."""

import logging
from typing import Dict, List, Any

from .knowledge import KnowledgeBase
from .bandit import ContextualBandit
from .coordination import CoordinationPlanner
from .incident_handler import IncidentHandler
from graph_manager.graph_model import TrafficGraph
from knowledge.phase_library import PhaseLibrary
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class Planner:
    """Plan stage of MAPE-K loop."""
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph,
                 mape_config: MAPEConfig):
        """
        Initialize Planner.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.graph = graph
        self.config = mape_config
        
        # Initialize sub-components
        self.phase_library = PhaseLibrary(knowledge)
        self.bandit = ContextualBandit(knowledge, mape_config)
        self.coordinator = CoordinationPlanner(knowledge, graph, mape_config)
        self.incident_handler = IncidentHandler(knowledge, graph, mape_config)
        
    def execute(self, cycle: int, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute planning: select signal plans using contextual bandits.
        
        Args:
            cycle: Current cycle number
            analysis_result: Results from Analyze stage
            
        Returns:
            Dict containing planned adaptations
        """
        adaptations = []
        is_incident_mode = len(analysis_result.get('incidents', [])) > 0
        
        # Get intersections that need updates
        intersections = self._get_intersections_needing_updates(analysis_result)
        
        for intersection_id in intersections:
            # Get valid plans from phase library
            valid_plans = self.phase_library.get_plans(intersection_id)
            
            # Build context features
            context = self._build_context(intersection_id, analysis_result)
            
            if is_incident_mode:
                # Use incident-aware planning
                plan = self.incident_handler.select_incident_plan(
                    intersection_id, context, valid_plans, analysis_result
                )
            else:
                # Use contextual bandit for normal mode
                plan = self.bandit.select_plan(
                    intersection_id, context, valid_plans
                )
            
            adaptations.append({
                'intersection_id': intersection_id,
                'plan_id': plan['plan_id'],
                'green_splits': plan['green_splits'],
                'cycle_length': plan['cycle_length'],
                'offset': plan.get('offset', 0.0),
                'is_incident_mode': is_incident_mode
            })
        
        # Calculate offsets for coordination if enabled
        if self.config.coordination_enabled and not is_incident_mode:
            adaptations = self.coordinator.apply_coordination(
                adaptations, analysis_result
            )
        
        # Log planning decision
        self._log_decision(cycle, adaptations, analysis_result)
        
        return {
            'cycle': cycle,
            'adaptations': adaptations,
            'is_incident_mode': is_incident_mode
        }
    
    def _get_intersections_needing_updates(self, analysis_result: Dict) -> List[str]:
        """
        Determine which intersections need plan updates.
        
        Strategy:
        - All intersections with throttle/favor edges
        - Intersections in coordination groups
        - Intersections affected by incidents
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            List of intersection IDs needing updates
        """
        intersections = set()
        
        targets = analysis_result.get('targets', {})
        
        # Add intersections with edges to throttle
        for edge_dict in targets.get('edges_to_throttle', []):
            intersections.add(edge_dict['from'])
        
        # Add intersections with edges to favor
        for edge_dict in targets.get('edges_to_favor', []):
            intersections.add(edge_dict['from'])
        
        # Add intersections from coordination groups
        for group in analysis_result.get('coordination_groups', []):
            intersections.update(group['intersections'])
        
        # Add intersections affected by incidents
        for incident in analysis_result.get('incidents', []):
            intersections.add(incident['from'])
        
        # If no specific intersections identified, update all active nodes
        if not intersections:
            intersections = set(self.graph.nodes.keys())
        
        logger.debug(f"Identified {len(intersections)} intersections needing updates")
        return list(intersections)
    
    def _build_context(self, intersection_id: str, 
                      analysis_result: Dict) -> Dict:
        """
        Build context features for contextual bandit.
        
        Features include:
        - Outgoing edge queue lengths
        - Outgoing edge delays
        - Edge costs
        - Hotspot indicators
        - Incident flags
        
        Args:
            intersection_id: Intersection ID
            analysis_result: Analysis results
            
        Returns:
            Context feature dictionary
        """
        context = {
            'intersection_id': intersection_id,
            'cycle': analysis_result['cycle'],
            'avg_queue': 0.0,
            'max_queue': 0.0,
            'avg_delay': 0.0,
            'max_delay': 0.0,
            'avg_cost': analysis_result.get('avg_cost', 0.0),
            'has_hotspot': False,
            'has_incident': False,
            'num_bypasses': len(analysis_result.get('bypasses', []))
        }
        
        # Get node from graph
        node = self.graph.nodes.get(intersection_id)
        if not node:
            return context
        
        # Aggregate features from outgoing edges
        queues = []
        delays = []
        costs = []
        
        for edge_key in node.outgoing_edges:
            edge = self.graph.get_edge(edge_key[0], edge_key[1])
            if edge:
                queues.append(edge.current_queue)
                delays.append(edge.current_delay)
                costs.append(edge.edge_cost)
                
                # Check if this edge is a hotspot
                if edge_key in analysis_result.get('hotspots', []):
                    context['has_hotspot'] = True
                
                # Check for incidents
                if edge.incident_active:
                    context['has_incident'] = True
        
        if queues:
            context['avg_queue'] = sum(queues) / len(queues)
            context['max_queue'] = max(queues)
        
        if delays:
            context['avg_delay'] = sum(delays) / len(delays)
            context['max_delay'] = max(delays)
        
        if costs:
            context['avg_edge_cost'] = sum(costs) / len(costs)
            context['max_edge_cost'] = max(costs)
        
        return context
    
    def _log_decision(self, cycle: int, adaptations: List, 
                     analysis_result: Dict) -> None:
        """
        Log planning decision for explainability.
        
        Args:
            cycle: Current cycle
            adaptations: Planned adaptations
            analysis_result: Analysis results
        """
        reasoning = {
            'num_adaptations': len(adaptations),
            'is_incident_mode': len(analysis_result.get('incidents', [])) > 0,
            'coordination_enabled': self.config.coordination_enabled,
            'bandit_algorithm': self.config.bandit_algorithm
        }
        
        context = {
            'adapted_intersections': [a['intersection_id'] for a in adaptations],
            'plan_ids': [a['plan_id'] for a in adaptations],
            'num_hotspots': len(analysis_result.get('hotspots', [])),
            'num_bypasses': len(analysis_result.get('bypasses', [])),
            'num_incidents': len(analysis_result.get('incidents', []))
        }
        
        self.knowledge.log_decision(
            cycle=cycle,
            stage='plan',
            decision_type='signal_timing_selection',
            reasoning=reasoning,
            context=context
        )
        
        logger.info(f"[Plan] Cycle {cycle}: {len(adaptations)} adaptations planned")

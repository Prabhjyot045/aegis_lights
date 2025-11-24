"""Analyze stage: Identify congestion patterns and find bypasses."""

import logging
from typing import Dict, List, Any, Tuple, Optional

from .knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph, GraphEdge
from graph_manager.graph_utils import (
    compute_edge_costs,
    identify_hotspots,
    find_k_shortest_paths,
    predict_trends,
    cluster_intersections
)
from config.mape import MAPEConfig

logger = logging.getLogger(__name__)


class Analyzer:
    """
    Analyze stage of MAPE-K loop.
    
    Responsibilities:
    - Compute edge costs using we(t) formula
    - Identify congestion hotspots
    - Find alternative bypass routes
    - Detect incident patterns
    - Determine adaptation targets (throttle/favor)
    - Group intersections for coordination
    """
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph,
                 mape_config: MAPEConfig):
        """
        Initialize Analyzer.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.graph = graph
        self.config = mape_config
        
        # Track historical costs for trend analysis
        self.cost_history: Dict[Tuple[str, str], List[float]] = {}
        self.history_window = 10  # Keep last 10 cycles
        
    def execute(self, cycle: int, monitor_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute analysis: compute costs, identify hotspots, find bypasses.
        
        Args:
            cycle: Current cycle number
            monitor_data: Data from Monitor stage containing:
                - aggregates: rolling statistics
                - anomalies: detected spillbacks/incidents
                - snapshot: NetworkSnapshot object
            
        Returns:
            Dict containing analysis results:
                - edge_costs: Dict mapping (from, to) to cost
                - hotspots: List of congested edge tuples
                - bypasses: List of alternative routes
                - trends: Trend predictions per edge
                - incidents: Detected incident information
                - targets: Adaptation targets
                - coordination_groups: Grouped intersections
        """
        logger.info(f"[Analyze] Starting cycle {cycle}")
        
        # Get cost coefficients from knowledge base
        cost_coeffs = self.knowledge.get_cost_coefficients()
        
        # Compute edge costs using we(t) = a·delay + b·queue + c·spillback + d·incident
        edge_costs = compute_edge_costs(self.graph, cost_coeffs)
        
        # Update cost history for trend analysis
        self._update_cost_history(edge_costs)
        
        # Identify high-cost edges (hotspots)
        hotspots = identify_hotspots(
            self.graph, 
            threshold=self.config.hotspot_threshold
        )
        
        # Find alternative routes (k-shortest paths)
        bypasses = find_k_shortest_paths(
            self.graph,
            k=self.config.k_shortest_paths,
            hotspots=hotspots
        )
        
        # Predict trends using exponential smoothing
        trends = predict_trends(
            self.graph,
            cost_history=self.cost_history,
            alpha=self.config.trend_alpha
        )
        
        # Extract incident information from monitor data
        incidents = self._process_incidents(monitor_data)
        
        # Determine edges to throttle and favor
        targets = self._determine_targets(hotspots, bypasses, incidents, edge_costs)
        
        # Group intersections for coordination (green wave)
        coordination_groups = self._identify_coordination_groups(targets)
        
        # Log decision for explainability
        self._log_decision(cycle, targets, edge_costs, incidents)
        
        logger.info(f"[Analyze] Completed: {len(hotspots)} hotspots, "
                   f"{len(bypasses)} bypasses, {len(incidents)} incidents")
        
        # Store analysis results in database for tracking
        import time
        timestamp = time.time()
        
        # Convert edge_costs from (from, to) tuples to edge_id strings
        edge_costs_by_id = {}
        for edge in self.graph.edges.values():
            key = (edge.from_node, edge.to_node)
            if key in edge_costs:
                edge_costs_by_id[edge.edge_id] = edge_costs[key]
        
        # Convert hotspots to edge_id list
        hotspot_ids = []
        for edge in self.graph.edges.values():
            key = (edge.from_node, edge.to_node)
            if key in hotspots:
                hotspot_ids.append(edge.edge_id)
        
        # Convert trends to edge_id dict
        trends_by_id = {}
        for edge in self.graph.edges.values():
            key = (edge.from_node, edge.to_node)
            if key in trends:
                trends_by_id[edge.edge_id] = trends[key]
        
        # Get incident edge_ids
        incident_ids = [inc['edge_id'] for inc in incidents if 'edge_id' in inc]
        
        self.knowledge.store_analysis_result(
            cycle=cycle,
            timestamp=timestamp,
            edge_costs=edge_costs_by_id,
            hotspots=hotspot_ids,
            bypass_routes=bypasses,
            trends=trends_by_id,
            incidents=incident_ids
        )
        
        return {
            'cycle': cycle,
            'edge_costs': edge_costs,
            'hotspots': hotspots,
            'bypasses': bypasses,
            'trends': trends,
            'incidents': incidents,
            'targets': targets,
            'coordination_groups': coordination_groups,
            'avg_cost': sum(edge_costs.values()) / len(edge_costs) if edge_costs else 0.0,
            'max_cost': max(edge_costs.values()) if edge_costs else 0.0
        }
    
    def _update_cost_history(self, edge_costs: Dict[Tuple[str, str], float]) -> None:
        """
        Update cost history for trend analysis.
        
        Args:
            edge_costs: Current edge costs
        """
        for edge_key, cost in edge_costs.items():
            if edge_key not in self.cost_history:
                self.cost_history[edge_key] = []
            
            self.cost_history[edge_key].append(cost)
            
            # Keep only recent history
            if len(self.cost_history[edge_key]) > self.history_window:
                self.cost_history[edge_key].pop(0)
    
    def _process_incidents(self, monitor_data: Dict[str, Any]) -> List[Dict]:
        """
        Process incident information from monitor data.
        
        Args:
            monitor_data: Data from Monitor stage
            
        Returns:
            List of incident dictionaries with edge and severity info
        """
        incidents = []
        anomalies = monitor_data.get('anomalies', {})
        
        # Extract incident edges
        for incident_info in anomalies.get('incidents', []):
            from_int = incident_info['from']
            to_int = incident_info['to']
            
            edge = self.graph.get_edge(from_int, to_int)
            if edge:
                incidents.append({
                    'from': from_int,
                    'to': to_int,
                    'edge_key': (from_int, to_int),
                    'queue': incident_info.get('queue', edge.current_queue),
                    'delay': incident_info.get('delay', edge.current_delay),
                    'severity': 'high' if edge.current_delay > 15.0 else 'medium'
                })
        
        return incidents
    
    def _determine_targets(self, hotspots: List[Tuple[str, str]], 
                          bypasses: List[Dict],
                          incidents: List[Dict],
                          edge_costs: Dict[Tuple[str, str], float]) -> Dict:
        """
        Determine which edges to throttle and which to favor.
        
        Strategy:
        - Throttle: Hotspot edges and edges leading to incidents
        - Favor: Bypass routes with lower costs
        
        Args:
            hotspots: List of congested edge tuples
            bypasses: Alternative routes
            incidents: Detected incidents
            edge_costs: Current edge costs
            
        Returns:
            Dict with throttle/favor lists and affected intersections
        """
        edges_to_throttle = []
        edges_to_favor = []
        affected_intersections = set()
        
        # Throttle hotspots
        for edge_key in hotspots:
            from_int, to_int = edge_key
            edges_to_throttle.append({
                'from': from_int,
                'to': to_int,
                'edge_key': edge_key,
                'reason': 'hotspot',
                'cost': edge_costs.get(edge_key, 0.0)
            })
            affected_intersections.add(from_int)
        
        # Throttle edges leading to incidents
        for incident in incidents:
            edge_key = incident['edge_key']
            if edge_key not in [e['edge_key'] for e in edges_to_throttle]:
                edges_to_throttle.append({
                    'from': incident['from'],
                    'to': incident['to'],
                    'edge_key': edge_key,
                    'reason': 'incident',
                    'severity': incident['severity'],
                    'cost': edge_costs.get(edge_key, 0.0)
                })
                affected_intersections.add(incident['from'])
        
        # Favor bypass routes
        for bypass in bypasses:
            for edge_key in bypass.get('path', []):
                # Only favor if not already a hotspot
                if edge_key not in hotspots:
                    edges_to_favor.append({
                        'from': edge_key[0],
                        'to': edge_key[1],
                        'edge_key': edge_key,
                        'reason': 'bypass',
                        'cost': edge_costs.get(edge_key, 0.0)
                    })
                    affected_intersections.add(edge_key[0])
        
        logger.debug(f"Targets: {len(edges_to_throttle)} to throttle, "
                    f"{len(edges_to_favor)} to favor")
        
        return {
            'edges_to_throttle': edges_to_throttle,
            'edges_to_favor': edges_to_favor,
            'affected_intersections': list(affected_intersections),
            'adaptation_needed': len(edges_to_throttle) > 0 or len(edges_to_favor) > 0
        }
    
    def _identify_coordination_groups(self, targets: Dict) -> List[Dict]:
        """
        Identify groups of intersections for signal coordination.
        
        Uses clustering on affected intersections to form coordination groups
        for green wave optimization.
        
        Args:
            targets: Adaptation targets
            
        Returns:
            List of coordination group dictionaries
        """
        if not self.config.coordination_enabled:
            return []
        
        affected = targets.get('affected_intersections', [])
        if len(affected) < 2:
            return []
        
        # Use clustering to group nearby intersections
        groups = cluster_intersections(self.graph, affected)
        
        logger.debug(f"Identified {len(groups)} coordination groups")
        return groups
    
    def _log_decision(self, cycle: int, targets: Dict, 
                     costs: Dict[Tuple[str, str], float],
                     incidents: List[Dict]) -> None:
        """
        Log analysis decision for explainability.
        
        Args:
            cycle: Current cycle number
            targets: Adaptation targets
            costs: Edge costs
            incidents: Detected incidents
        """
        reasoning = {
            'num_hotspots': len(targets['edges_to_throttle']),
            'num_bypasses': len(targets['edges_to_favor']),
            'num_incidents': len(incidents),
            'avg_cost': sum(costs.values()) / len(costs) if costs else 0.0,
            'max_cost': max(costs.values()) if costs else 0.0,
            'adaptation_needed': targets['adaptation_needed']
        }
        
        context = {
            'hotspot_edges': [e['edge_key'] for e in targets['edges_to_throttle']],
            'favor_edges': [e['edge_key'] for e in targets['edges_to_favor']],
            'incident_edges': [i['edge_key'] for i in incidents]
        }
        
        self.knowledge.log_decision(
            cycle=cycle,
            stage='analyze',
            decision_type='target_identification',
            reasoning=reasoning,
            context=context
        )
    
    def get_edge_cost_breakdown(self, from_int: str, to_int: str) -> Optional[Dict]:
        """
        Get detailed cost breakdown for an edge.
        
        Args:
            from_int: Origin intersection
            to_int: Destination intersection
            
        Returns:
            Dict with cost components or None if edge not found
        """
        edge = self.graph.get_edge(from_int, to_int)
        if not edge:
            return None
        
        coeffs = self.knowledge.get_cost_coefficients()
        a, b, c, d = coeffs
        
        return {
            'total_cost': edge.edge_cost,
            'delay_component': a * edge.current_delay,
            'queue_component': b * edge.current_queue,
            'spillback_component': c * (10.0 if edge.spillback_active else 0.0),
            'incident_component': d * (20.0 if edge.incident_active else 0.0),
            'delay': edge.current_delay,
            'queue': edge.current_queue,
            'spillback': edge.spillback_active,
            'incident': edge.incident_active
        }

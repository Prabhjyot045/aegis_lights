"""Performance metrics calculator."""

import logging
from typing import Dict
import numpy as np

from .knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph
from db_manager.db_utils import get_connection, close_connection, insert_performance_metrics

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculates performance metrics for evaluation and rollback."""
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph):
        """
        Initialize metrics calculator.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
        """
        self.knowledge = knowledge
        self.graph = graph
        
    def calculate(self, cycle: int, timestamp: float, monitor_result: Dict = None) -> Dict[str, float]:
        """
        Calculate performance metrics for current cycle.
        
        Metrics include delay, queue, network cost, and spillbacks.
        
        Args:
            cycle: Current cycle number
            timestamp: Current timestamp
            monitor_result: Optional monitor result with average_travel_time
            
        Returns:
            Dict of metric name to value
        """
        # Get current graph state from database
        graph_state = self.knowledge.get_graph_state()
        
        # Calculate edge-based metrics from graph model
        avg_delay = 0.0
        avg_queue = 0.0
        network_cost = 0.0
        spillback_count = 0
        
        edge_count = len(self.graph.edges)
        
        if edge_count > 0:
            for edge in self.graph.edges.values():
                avg_delay += edge.current_delay
                avg_queue += edge.current_queue
                network_cost += edge.edge_cost
                if edge.spillback_active:
                    spillback_count += 1
            
            avg_delay /= edge_count
            avg_queue /= edge_count
        
        # Get real average travel time from monitor if available
        avg_trip_time = None
        if monitor_result and 'average_travel_time' in monitor_result:
            avg_trip_time = monitor_result['average_travel_time']
        
        # If not available, fall back to delay estimate
        if avg_trip_time is None:
            avg_trip_time = avg_delay
        
        # Calculate metrics
        metrics = {
            'avg_delay': avg_delay,
            'avg_queue': avg_queue,
            'network_cost': network_cost,
            'total_spillbacks': spillback_count,
            'total_edges': edge_count,
            'cycle': cycle,
            'timestamp': timestamp,
            # Database expects these field names
            'avg_trip_time': avg_trip_time,  # Use real value from simulator
            'p95_trip_time': None,  # Could calculate percentile later
            'total_stops': None,  # Not tracked currently
            'incident_clearance_time': None,  # Would need incident tracking
            'utility_score': network_cost  # Use network cost as utility
        }
        
        # Store in database
        conn = get_connection(self.knowledge.db_path)
        insert_performance_metrics(conn, cycle, timestamp, metrics)
        close_connection(conn)
        
        logger.debug(f"Calculated metrics: delay={avg_delay:.2f}, queue={avg_queue:.2f}, cost={network_cost:.2f}")
        
        return metrics
    
    def _calculate_avg_trip_time(self, graph_state: list) -> float:
        """Calculate average trip time across all edges."""
        if not graph_state:
            return 0.0
        
        # Trip time = free flow time + delay + queue delay
        # Queue delay estimated as queue_length / flow rate
        total_time = 0.0
        for edge in graph_state:
            free_flow = edge.get('free_flow_time', 0)
            delay = edge.get('current_delay', 0)
            queue = edge.get('current_queue', 0)
            flow = edge.get('current_flow', 1.0)  # vehicles/second
            
            # Queue processing time
            queue_delay = queue / max(flow, 0.1)  # Avoid division by zero
            
            edge_trip_time = free_flow + delay + queue_delay
            total_time += edge_trip_time
        
        return total_time / len(graph_state) if graph_state else 0.0
    
    def _calculate_p95_trip_time(self, graph_state: list) -> float:
        """Calculate 95th percentile trip time."""
        if not graph_state:
            return 0.0
        
        trip_times = []
        for edge in graph_state:
            free_flow = edge.get('free_flow_time', 0)
            delay = edge.get('current_delay', 0)
            queue = edge.get('current_queue', 0)
            flow = edge.get('current_flow', 1.0)
            
            queue_delay = queue / max(flow, 0.1)
            edge_trip_time = free_flow + delay + queue_delay
            trip_times.append(edge_trip_time)
        
        if trip_times:
            # Sort and get 95th percentile
            sorted_times = sorted(trip_times)
            p95_index = int(len(sorted_times) * 0.95)
            return sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]
        return 0.0
    
    def _count_spillbacks(self, graph_state: list) -> int:
        """Count total spillback events."""
        return sum(
            1 for edge in graph_state 
            if edge.get('spillback_active', 0) == 1
        )
    
    def _estimate_stops(self, graph_state: list) -> int:
        """Estimate total vehicle stops based on queue and delay."""
        # Stops estimated from:
        # 1. Vehicles in queue (currently stopped)
        # 2. Delay-based stops (vehicles that had to slow/stop due to congestion)
        total_stops = 0
        
        for edge in graph_state:
            queue = edge.get('current_queue', 0)
            delay = edge.get('current_delay', 0)
            flow = edge.get('current_flow', 0)
            
            # Queued vehicles are definitely stopped
            total_stops += int(queue)
            
            # Estimate additional stops from delay
            # Assumption: vehicles with >3s delay likely experienced a stop
            if delay > 3.0 and flow > 0:
                # Approximate vehicles affected by delay
                affected_vehicles = int(flow * delay * 0.3)  # 30% of flow during delay period
                total_stops += affected_vehicles
        
        return total_stops
    
    def _get_incident_clearance_time(self) -> float:
        """Get cumulative time for active incidents."""
        # Get active incidents from graph state
        graph_state = self.knowledge.get_graph_state()
        
        incident_time = 0.0
        for edge in graph_state:
            if edge.get('incident_active', 0) == 1:
                # Each active incident contributes to clearance time
                # This could be refined with actual incident duration tracking
                incident_time += 1.0  # Base time unit per incident
        
        return incident_time

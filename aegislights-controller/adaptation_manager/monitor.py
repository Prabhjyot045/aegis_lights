"""Monitor stage: Data ingestion and graph state updates."""

import time
import logging
from typing import Dict, List, Any, Optional
from collections import deque

from .knowledge import KnowledgeBase
from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from api.endpoints import SimulatorAPI
from api.data_schemas import NetworkSnapshot, IntersectionData, RoadSegment
from config.mape import MAPEConfig
from config.simulator import SimulatorConfig

logger = logging.getLogger(__name__)


class Monitor:
    """
    Monitor stage of MAPE-K loop.
    
    Responsibilities:
    - Collect network state from simulator
    - Update runtime graph model
    - Compute rolling aggregates for noise reduction
    - Store snapshots in knowledge base
    """
    
    def __init__(self, knowledge: KnowledgeBase, graph: TrafficGraph,
                 sim_config: SimulatorConfig, mape_config: MAPEConfig):
        """
        Initialize Monitor.
        
        Args:
            knowledge: Knowledge base interface
            graph: Traffic graph model
            sim_config: Simulator configuration
            mape_config: MAPE configuration
        """
        self.knowledge = knowledge
        self.graph = graph
        self.api = SimulatorAPI(sim_config)
        self.config = mape_config
        
        # Rolling window for smoothing (fixed size deque per edge)
        self.rolling_windows: Dict[tuple, deque] = {}
        self.window_size = getattr(mape_config, 'rolling_window_size', 3)
        
        # Statistics tracking
        self.stats = {
            'total_snapshots': 0,
            'failed_collections': 0,
            'last_collection_time': 0.0
        }
        
    def execute(self, cycle: int) -> Dict[str, Any]:
        """
        Execute monitoring: collect data, update graph, compute aggregates.
        
        Args:
            cycle: Current cycle number
            
        Returns:
            Dict containing monitored data with keys:
            - cycle: cycle number
            - timestamp: collection timestamp
            - snapshot: NetworkSnapshot object
            - edges_updated: number of edges updated
            - aggregates: rolling statistics
            - anomalies: detected anomalies (spillbacks, incidents)
        """
        start_time = time.time()
        logger.info(f"[Monitor] Starting cycle {cycle}")
        
        try:
            # Collect network snapshot from simulator
            snapshot = self._collect_network_snapshot()
            
            if snapshot is None:
                logger.error(f"Failed to collect snapshot for cycle {cycle}")
                self.stats['failed_collections'] += 1
                return self._empty_result(cycle)
            
            # Update runtime graph model with current data
            edges_updated = self._update_graph_state(snapshot, cycle)
            
            # Compute rolling aggregates for smoothing
            aggregates = self._compute_rolling_aggregates(snapshot)
            
            # Detect anomalies (spillbacks, incidents)
            anomalies = self._detect_anomalies(snapshot)
            
            # Store snapshot in knowledge base
            self._store_snapshot(snapshot, cycle)
            
            # Update statistics
            self.stats['total_snapshots'] += 1
            self.stats['last_collection_time'] = time.time() - start_time
            
            logger.info(f"[Monitor] Completed cycle {cycle}: {edges_updated} edges updated, "
                       f"{len(anomalies['spillbacks'])} spillbacks, "
                       f"{len(anomalies['incidents'])} incidents")
            
            return {
                'cycle': cycle,
                'timestamp': snapshot.timestamp,
                'snapshot': snapshot,
                'edges_updated': edges_updated,
                'aggregates': aggregates,
                'anomalies': anomalies,
                'collection_time': self.stats['last_collection_time']
            }
            
        except Exception as e:
            logger.error(f"[Monitor] Error in cycle {cycle}: {e}", exc_info=True)
            self.stats['failed_collections'] += 1
            return self._empty_result(cycle)
    
    def _collect_network_snapshot(self) -> Optional[NetworkSnapshot]:
        """
        Collect current network state from simulator.
        
        Returns:
            NetworkSnapshot object or None if failed
        """
        try:
            snapshot = self.api.get_network_snapshot()
            
            if snapshot:
                logger.debug(f"Collected snapshot with {len(snapshot.intersections)} intersections")
                return snapshot
            else:
                logger.warning("Simulator returned no snapshot data")
                return None
                
        except Exception as e:
            logger.error(f"Failed to collect network snapshot: {e}")
            return None
    
    def _update_graph_state(self, snapshot: NetworkSnapshot, cycle: int) -> int:
        """
        Update runtime graph model with snapshot data.
        
        Args:
            snapshot: Network snapshot from simulator
            cycle: Current cycle number
            
        Returns:
            Number of edges updated
        """
        edges_updated = 0
        timestamp = snapshot.timestamp
        
        for int_id, int_data in snapshot.intersections.items():
            # Ensure node exists in graph
            if not self.graph.has_node(int_id):
                self.graph.add_node(GraphNode(
                    node_id=int_id,
                    intersection_type="signalized"
                ))
            
            # Update each outgoing road
            for road in int_data.outgoing_roads:
                from_int = int_id
                to_int = road.to_intersection
                
                # Ensure destination node exists
                if not self.graph.has_node(to_int):
                    self.graph.add_node(GraphNode(
                        node_id=to_int,
                        intersection_type="signalized"
                    ))
                
                # Create or update edge
                edge = self.graph.get_edge(from_int, to_int)
                
                if edge is None:
                    # New edge - add to graph
                    edge = GraphEdge(
                        from_node=from_int,
                        to_node=to_int,
                        capacity=road.capacity,
                        free_flow_time=road.free_flow_time,
                        current_queue=road.current_queue,
                        current_delay=road.current_delay or 0.0,
                        spillback_active=road.spillback_active,
                        incident_active=road.incident_active
                    )
                    self.graph.add_edge(edge)
                else:
                    # Update existing edge
                    edge.current_queue = road.current_queue
                    edge.current_delay = road.current_delay or 0.0
                    edge.current_flow = road.current_flow or 0.0
                    edge.spillback_active = road.spillback_active
                    edge.incident_active = road.incident_active
                
                # Update in database through knowledge base
                self.knowledge.update_edge_state(
                    from_int, to_int,
                    queue=road.current_queue,
                    delay=road.current_delay or 0.0,
                    flow=road.current_flow or 0.0,
                    spillback=road.spillback_active,
                    incident=road.incident_active,
                    cycle=cycle,
                    timestamp=timestamp
                )
                
                edges_updated += 1
        
        logger.debug(f"Updated {edges_updated} edges in graph model")
        return edges_updated
    
    def _compute_rolling_aggregates(self, snapshot: NetworkSnapshot) -> Dict[str, Any]:
        """
        Compute rolling averages for noise reduction.
        
        Uses fixed-size deque for each edge to maintain window.
        
        Args:
            snapshot: Current network snapshot
            
        Returns:
            Dict with aggregate statistics
        """
        aggregates = {
            'avg_queue': 0.0,
            'avg_delay': 0.0,
            'max_queue': 0.0,
            'max_delay': 0.0,
            'total_edges': 0,
            'smoothed_edges': {}
        }
        
        total_queue = 0.0
        total_delay = 0.0
        max_queue = 0.0
        max_delay = 0.0
        edge_count = 0
        
        for int_id, int_data in snapshot.intersections.items():
            for road in int_data.outgoing_roads:
                edge_key = (int_id, road.to_intersection)
                
                # Initialize window if first time seeing this edge
                if edge_key not in self.rolling_windows:
                    self.rolling_windows[edge_key] = deque(maxlen=self.window_size)
                
                # Add current values to window
                self.rolling_windows[edge_key].append({
                    'queue': road.current_queue,
                    'delay': road.current_delay or 0.0,
                    'flow': road.current_flow or 0.0
                })
                
                # Compute rolling average
                window = self.rolling_windows[edge_key]
                avg_queue = sum(d['queue'] for d in window) / len(window)
                avg_delay = sum(d['delay'] for d in window) / len(window)
                
                aggregates['smoothed_edges'][edge_key] = {
                    'avg_queue': avg_queue,
                    'avg_delay': avg_delay,
                    'raw_queue': road.current_queue,
                    'raw_delay': road.current_delay or 0.0,
                    'window_size': len(window)
                }
                
                # Update network-wide stats
                total_queue += avg_queue
                total_delay += avg_delay
                max_queue = max(max_queue, avg_queue)
                max_delay = max(max_delay, avg_delay)
                edge_count += 1
        
        if edge_count > 0:
            aggregates['avg_queue'] = total_queue / edge_count
            aggregates['avg_delay'] = total_delay / edge_count
        
        aggregates['max_queue'] = max_queue
        aggregates['max_delay'] = max_delay
        aggregates['total_edges'] = edge_count
        
        return aggregates
    
    def _detect_anomalies(self, snapshot: NetworkSnapshot) -> Dict[str, List]:
        """
        Detect anomalies in network state.
        
        Args:
            snapshot: Current network snapshot
            
        Returns:
            Dict with lists of anomalies:
            - spillbacks: list of edges with spillback
            - incidents: list of edges with incidents
            - high_congestion: list of edges with very high queues
        """
        anomalies = {
            'spillbacks': [],
            'incidents': [],
            'high_congestion': []
        }
        
        # Thresholds
        congestion_threshold = getattr(self.config, 'congestion_queue_threshold', 20)
        
        for int_id, int_data in snapshot.intersections.items():
            for road in int_data.outgoing_roads:
                edge_key = (int_id, road.to_intersection)
                
                if road.spillback_active:
                    anomalies['spillbacks'].append({
                        'from': int_id,
                        'to': road.to_intersection,
                        'queue': road.current_queue,
                        'delay': road.current_delay
                    })
                
                if road.incident_active:
                    anomalies['incidents'].append({
                        'from': int_id,
                        'to': road.to_intersection,
                        'queue': road.current_queue,
                        'delay': road.current_delay
                    })
                
                if road.current_queue > congestion_threshold:
                    anomalies['high_congestion'].append({
                        'from': int_id,
                        'to': road.to_intersection,
                        'queue': road.current_queue,
                        'capacity': road.capacity
                    })
        
        return anomalies
    
    def _store_snapshot(self, snapshot: NetworkSnapshot, cycle: int) -> None:
        """
        Store snapshot in knowledge base (database).
        
        Args:
            snapshot: Network snapshot
            cycle: Current cycle number
        """
        try:
            for int_id, int_data in snapshot.intersections.items():
                for road in int_data.outgoing_roads:
                    self.knowledge.insert_snapshot(
                        cycle=cycle,
                        timestamp=snapshot.timestamp,
                        from_intersection=int_id,
                        to_intersection=road.to_intersection,
                        queue=int(road.current_queue),
                        delay=road.current_delay or 0.0,
                        throughput=road.current_flow or 0.0,
                        spillback=road.spillback_active,
                        incident=road.incident_active
                    )
            
            logger.debug(f"Stored snapshot for cycle {cycle} in database")
            
        except Exception as e:
            logger.error(f"Failed to store snapshot: {e}")
    
    def _empty_result(self, cycle: int) -> Dict[str, Any]:
        """Return empty result structure on failure."""
        return {
            'cycle': cycle,
            'timestamp': time.time(),
            'snapshot': None,
            'edges_updated': 0,
            'aggregates': {},
            'anomalies': {'spillbacks': [], 'incidents': [], 'high_congestion': []},
            'collection_time': 0.0
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            'total_snapshots': self.stats['total_snapshots'],
            'failed_collections': self.stats['failed_collections'],
            'success_rate': (self.stats['total_snapshots'] / 
                           (self.stats['total_snapshots'] + self.stats['failed_collections'])
                           if self.stats['total_snapshots'] + self.stats['failed_collections'] > 0
                           else 0.0),
            'last_collection_time': self.stats['last_collection_time'],
            'active_windows': len(self.rolling_windows)
        }

"""Knowledge base interface for MAPE-K components."""

import json
import logging
import math
from typing import Dict, List, Optional, Any
from pathlib import Path

from db_manager.db_utils import (
    get_connection, close_connection,
    get_graph_state, update_graph_state,
    get_last_known_good_config, insert_signal_config,
    insert_adaptation_decision, insert_snapshot,
    insert_or_update_graph_edge, get_outgoing_roads
)
from graph_manager.graph_model import TrafficGraph
from config.costs import CostConfig

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    Knowledge base interface providing shared access to runtime state.
    Serves as abstraction layer over database for all MAPE stages.
    """
    
    def __init__(self, db_path: str, graph: TrafficGraph):
        """
        Initialize knowledge base.
        
        Args:
            db_path: Path to SQLite database
            graph: Traffic graph model
        """
        self.db_path = db_path
        self.graph = graph
        self.cost_config = CostConfig()
        
        # In-memory caches for fast access
        self._cache: Dict[str, Any] = {
            'last_known_good': {},
            'phase_libraries': {},
            'thresholds': {},
            'bandit_state': {}
        }
        
    def get_cost_coefficients(self) -> tuple:
        """Get edge cost function coefficients (a, b, c, d)."""
        return self.cost_config.get_coefficients()
    
    def get_graph_state(self, from_intersection: Optional[str] = None,
                       to_intersection: Optional[str] = None) -> List[Dict]:
        """
        Get current graph state from database.
        
        Args:
            from_intersection: Optional origin intersection
            to_intersection: Optional destination intersection
            
        Returns:
            List of edge state dicts
        """
        conn = get_connection(self.db_path)
        state = get_graph_state(conn, from_intersection, to_intersection)
        close_connection(conn)
        return state
    
    def get_outgoing_roads(self, intersection_id: str) -> List[Dict]:
        """
        Get all outgoing roads from an intersection.
        
        Args:
            intersection_id: Intersection identifier
            
        Returns:
            List of outgoing road states
        """
        conn = get_connection(self.db_path)
        roads = get_outgoing_roads(conn, intersection_id)
        close_connection(conn)
        return roads
    
    def update_edge_state(self, from_intersection: str, to_intersection: str,
                         queue: float, delay: float, flow: float,
                         spillback: bool, incident: bool,
                         cycle: int, timestamp: float) -> None:
        """
        Update edge state in database using upsert.
        
        Args:
            from_intersection: Origin intersection
            to_intersection: Destination intersection
            queue: Current queue length
            delay: Current delay
            flow: Current flow rate
            spillback: Spillback active flag
            incident: Incident active flag
            cycle: Current cycle number
            timestamp: Current timestamp
        """
        conn = get_connection(self.db_path)
        
        # Get existing edge to preserve capacity and free_flow_time
        existing = get_graph_state(conn, from_intersection, to_intersection)
        
        if existing and len(existing) > 0:
            capacity = existing[0]['capacity']
            free_flow_time = existing[0]['free_flow_time']
        else:
            # Default values if edge doesn't exist yet
            capacity = 1.0
            free_flow_time = 30.0
            logger.warning(f"Edge ({from_intersection} -> {to_intersection}) not initialized, using defaults")
        
        insert_or_update_graph_edge(
            conn, from_intersection, to_intersection,
            capacity=capacity,
            free_flow_time=free_flow_time,
            current_queue=queue,
            current_delay=delay,
            current_flow=flow,
            spillback_active=spillback,
            incident_active=incident,
            cycle_number=cycle,
            timestamp=timestamp
        )
        close_connection(conn)
    
    def insert_snapshot(self, cycle: int, timestamp: float,
                       from_intersection: str, to_intersection: str,
                       queue: int, delay: float, throughput: float,
                       spillback: bool, incident: bool) -> None:
        """
        Insert simulation snapshot.
        
        Args:
            cycle: Cycle number
            timestamp: Timestamp
            from_intersection: Origin intersection
            to_intersection: Destination intersection
            queue: Queue length
            delay: Delay
            throughput: Flow rate
            spillback: Spillback flag
            incident: Incident flag
        """
        conn = get_connection(self.db_path)
        insert_snapshot(conn, cycle, timestamp, from_intersection, to_intersection,
                       queue, delay, throughput, spillback, incident)
        close_connection(conn)
    
    def get_last_known_good(self, intersection_id: str) -> Optional[Dict]:
        """
        Get last successful signal configuration for rollback.
        
        Args:
            intersection_id: Intersection identifier
            
        Returns:
            Last known good configuration or None
        """
        # Check cache first
        if intersection_id in self._cache['last_known_good']:
            return self._cache['last_known_good'][intersection_id]
        
        # Query database
        conn = get_connection(self.db_path)
        config = get_last_known_good_config(conn, intersection_id)
        close_connection(conn)
        
        # Update cache
        if config:
            self._cache['last_known_good'][intersection_id] = config
        
        return config
    
    def update_last_known_good(self, cycle: int, adaptations: List[Dict]) -> None:
        """
        Update last-known-good configurations after successful cycle.
        
        Args:
            cycle: Current cycle number
            adaptations: List of applied adaptations
        """
        for adaptation in adaptations:
            intersection_id = adaptation['intersection_id']
            self._cache['last_known_good'][intersection_id] = {
                'cycle': cycle,
                'config': adaptation
            }
    
    def log_decision(self, cycle: int, stage: str, decision_type: str,
                    reasoning: Dict, context: Dict) -> None:
        """
        Log adaptation decision for explainability.
        
        Args:
            cycle: Current cycle number
            stage: MAPE stage (monitor, analyze, plan, execute)
            decision_type: Type of decision made
            reasoning: Decision reasoning (JSON-serializable)
            context: Decision context (JSON-serializable)
        """
        conn = get_connection(self.db_path)
        insert_adaptation_decision(conn, cycle, stage, decision_type, 
                                  reasoning, context)
        close_connection(conn)
    
    def get_performance_threshold(self, metric_name: str) -> float:
        """
        Get performance threshold for rollback detection.
        
        Returns default thresholds for now. Can be extended to load
        from config file or database in future.
        """
        default_thresholds = {
            'utility': 0.1,      # 10% degradation triggers rollback
            'avg_time': 0.15,    # 15% increase in avg time
            'p95_time': 0.20,    # 20% increase in p95 time
            'spillbacks': 0.0    # Any spillback increase
        }
        return self._cache['thresholds'].get(
            metric_name, 
            default_thresholds.get(metric_name, 0.1)
        )
    
    def get_bandit_stats(self, intersection_id: str, plan_id: str) -> Optional[Dict]:
        """
        Get bandit arm statistics for an intersection-plan combination.
        
        Args:
            intersection_id: Intersection ID
            plan_id: Plan ID
            
        Returns:
            Statistics dict or None if not found
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT times_selected, total_reward, avg_reward, confidence
            FROM bandit_state
            WHERE intersection_id = ? AND plan_id = ?
        """, (intersection_id, plan_id))
        
        row = cursor.fetchone()
        close_connection(conn)
        
        if row is None:
            return None
        
        return {
            'times_selected': row[0],
            'total_reward': row[1],
            'avg_reward': row[2],
            'confidence': row[3],
            'total_pulls': row[0]  # For UCB calculation
        }
    
    def update_bandit_stats(self, intersection_id: str, plan_id: str,
                           times_selected: int, total_reward: float,
                           avg_reward: float) -> None:
        """
        Update bandit arm statistics.
        
        Args:
            intersection_id: Intersection ID
            plan_id: Plan ID
            times_selected: Number of times selected
            total_reward: Cumulative reward
            avg_reward: Average reward
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        
        # Calculate confidence (decreases as selections increase)
        confidence = 1.0 / math.sqrt(max(1, times_selected))
        
        cursor.execute("""
            INSERT OR REPLACE INTO bandit_state
            (intersection_id, plan_id, times_selected, total_reward, avg_reward, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (intersection_id, plan_id, times_selected, total_reward, avg_reward, confidence))
        
        conn.commit()
        close_connection(conn)
    
    def log_execution(self, cycle: int, execution_record: Dict) -> None:
        """
        Log execution record for this cycle.
        
        Args:
            cycle: Current cycle number
            execution_record: Execution details including applied adaptations and metrics
        """
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO cycle_logs (cycle, stage, timestamp, data)
                VALUES (?, ?, ?, ?)
            """, (cycle, 'execute', execution_record['timestamp'], 
                  json.dumps(execution_record)))
            
            conn.commit()
            close_connection(conn)
            logger.debug(f"Logged execution for cycle {cycle}")
        except Exception as e:
            logger.warning(f"Could not log execution (table may not exist): {e}")
    
    def log_rollback(self, cycle: int, timestamp: float, config: List[Dict]) -> None:
        """
        Log rollback event.
        
        Args:
            cycle: Current cycle number
            timestamp: Rollback timestamp
            config: Configuration that was restored
        """
        try:
            conn = get_connection(self.db_path)
            cursor = conn.cursor()
            
            rollback_data = {
                'cycle': cycle,
                'timestamp': timestamp,
                'restored_config': config,
                'event_type': 'rollback'
            }
            
            cursor.execute("""
                INSERT INTO cycle_logs (cycle, stage, timestamp, data)
                VALUES (?, ?, ?, ?)
            """, (cycle, 'rollback', timestamp, json.dumps(rollback_data)))
            
            conn.commit()
            close_connection(conn)
            logger.info(f"Logged rollback event for cycle {cycle}")
        except Exception as e:
            logger.warning(f"Could not log rollback (table may not exist): {e}")
    
    def clear_cache(self) -> None:
        """Clear in-memory caches."""
        self._cache = {
            'last_known_good': {},
            'phase_libraries': {},
            'thresholds': {},
            'bandit_state': {}
        }
        logger.debug("Knowledge base cache cleared")

"""Database utility functions for CRUD operations."""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, List, Any
import logging

logger = logging.getLogger(__name__)

# Flag to check if pandas is available (optional dependency)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas not available, export functionality will be limited")


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def close_connection(conn: sqlite3.Connection) -> None:
    """Close database connection."""
    if conn:
        conn.close()


def insert_snapshot(conn: sqlite3.Connection, cycle: int, timestamp: float,
                   from_intersection: str, to_intersection: str,
                   queue: int, delay: float, throughput: float,
                   spillback: bool, incident: bool) -> None:
    """Insert a simulation snapshot using intersection IDs."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO simulation_snapshots
        (cycle_number, timestamp, from_intersection, to_intersection,
         queue_length, delay, throughput, spillback_flag, incident_flag)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cycle, timestamp, from_intersection, to_intersection,
          queue, delay, throughput, int(spillback), int(incident)))
    conn.commit()


def update_graph_state(conn: sqlite3.Connection, from_intersection: str,
                      to_intersection: str, updates: Dict[str, Any]) -> None:
    """Update graph state for an edge using intersection IDs."""
    cursor = conn.cursor()
    
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values()) + [from_intersection, to_intersection]
    
    cursor.execute(f"""
        UPDATE graph_state 
        SET {set_clause}
        WHERE from_intersection = ? AND to_intersection = ?
    """, values)
    conn.commit()


def get_graph_state(conn: sqlite3.Connection,
                   from_intersection: Optional[str] = None,
                   to_intersection: Optional[str] = None) -> List[Dict]:
    """
    Get current graph state for edges.
    
    Args:
        conn: Database connection
        from_intersection: Origin intersection (None = all)
        to_intersection: Destination intersection (None with from = all outgoing)
        
    Returns:
        List of edge state dictionaries
    """
    cursor = conn.cursor()
    
    if from_intersection and to_intersection:
        # Specific edge
        cursor.execute("""
            SELECT * FROM graph_state 
            WHERE from_intersection = ? AND to_intersection = ?
        """, (from_intersection, to_intersection))
    elif from_intersection:
        # All outgoing edges from intersection
        cursor.execute("""
            SELECT * FROM graph_state WHERE from_intersection = ?
        """, (from_intersection,))
    else:
        # All edges
        cursor.execute("SELECT * FROM graph_state")
    
    return [dict(row) for row in cursor.fetchall()]


def get_outgoing_roads(conn: sqlite3.Connection, intersection_id: str) -> List[Dict]:
    """Get all outgoing roads from an intersection."""
    return get_graph_state(conn, from_intersection=intersection_id)


def insert_or_update_graph_edge(conn: sqlite3.Connection,
                               from_intersection: str,
                               to_intersection: str,
                               capacity: float,
                               free_flow_time: float,
                               current_queue: float = 0.0,
                               current_delay: float = 0.0,
                               current_flow: float = 0.0,
                               spillback_active: bool = False,
                               incident_active: bool = False,
                               edge_cost: float = 0.0,
                               cycle_number: int = 0,
                               timestamp: float = 0.0) -> None:
    """
    Insert or update a graph edge (road segment).
    
    Uses UPSERT to handle both insert and update in one operation.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO graph_state 
        (from_intersection, to_intersection, capacity, free_flow_time,
         current_queue, current_delay, current_flow, spillback_active, 
         incident_active, edge_cost, last_updated_cycle, last_updated_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(from_intersection, to_intersection) DO UPDATE SET
            current_queue = excluded.current_queue,
            current_delay = excluded.current_delay,
            current_flow = excluded.current_flow,
            spillback_active = excluded.spillback_active,
            incident_active = excluded.incident_active,
            edge_cost = excluded.edge_cost,
            last_updated_cycle = excluded.last_updated_cycle,
            last_updated_timestamp = excluded.last_updated_timestamp
    """, (from_intersection, to_intersection, capacity, free_flow_time,
          current_queue, current_delay, current_flow,
          int(spillback_active), int(incident_active),
          edge_cost, cycle_number, timestamp))
    conn.commit()
    logger.debug(f"Upserted edge ({from_intersection} -> {to_intersection})")
def insert_signal_config(conn: sqlite3.Connection, intersection_id: str,
                        cycle: int, timestamp: float, plan_id: str,
                        green_splits: Dict, cycle_length: float, offset: float,
                        is_incident_mode: bool = False) -> int:
    """Insert signal configuration and return config_id."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO signal_configurations
        (intersection_id, cycle_number, timestamp, plan_id, green_splits, 
         cycle_length, offset, is_incident_mode, applied)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (intersection_id, cycle, timestamp, plan_id, json.dumps(green_splits),
          cycle_length, offset, int(is_incident_mode)))
    conn.commit()
    return cursor.lastrowid


def get_last_known_good_config(conn: sqlite3.Connection, 
                               intersection_id: str) -> Optional[Dict]:
    """Get last successful (non-rolled-back) configuration."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM signal_configurations
        WHERE intersection_id = ? 
          AND applied = 1 
          AND rolled_back = 0
        ORDER BY cycle_number DESC
        LIMIT 1
    """, (intersection_id,))
    
    row = cursor.fetchone()
    return dict(row) if row else None


def insert_performance_metrics(conn: sqlite3.Connection, cycle: int,
                               timestamp: float, metrics: Dict[str, float]) -> None:
    """Insert performance metrics for a cycle."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO performance_metrics
        (cycle_number, timestamp, avg_trip_time, p95_trip_time, 
         total_spillbacks, total_stops, incident_clearance_time, utility_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (cycle, timestamp, 
          metrics.get('avg_trip_time'), metrics.get('p95_trip_time'),
          metrics.get('total_spillbacks'), metrics.get('total_stops'),
          metrics.get('incident_clearance_time'), metrics.get('utility_score')))
    conn.commit()


def insert_adaptation_decision(conn: sqlite3.Connection, cycle: int, stage: str,
                              decision_type: str, reasoning: Dict, 
                              context: Dict) -> None:
    """Insert adaptation decision for explainability."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO adaptation_decisions
        (cycle_number, stage, decision_type, reasoning, context)
        VALUES (?, ?, ?, ?, ?)
    """, (cycle, stage, decision_type, json.dumps(reasoning), json.dumps(context)))
    conn.commit()


def export_experiment_data(db_path: str, output_dir: Path, 
                          experiment_name: str) -> None:
    """
    Export all experiment data to CSV and JSON files.
    
    Args:
        db_path: Path to database
        output_dir: Directory to save exported files
        experiment_name: Name prefix for output files
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # Export tables to CSV
    tables = [
        'simulation_snapshots',
        'signal_configurations', 
        'performance_metrics',
        'adaptation_decisions',
        'bandit_state'
    ]
    
    if HAS_PANDAS:
        # Use pandas for CSV export if available
        for table in tables:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            output_path = output_dir / f"{experiment_name}_{table}.csv"
            df.to_csv(output_path, index=False)
            logger.info(f"Exported {table} to {output_path}")
    else:
        # Fallback: manual CSV export
        logger.warning("pandas not available, using basic CSV export")
        import csv
        
        for table in tables:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            if rows:
                # Get column names
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                
                output_path = output_dir / f"{experiment_name}_{table}.csv"
                with open(output_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(rows)
                
                logger.info(f"Exported {table} to {output_path}")
    
    # Export summary statistics as JSON
    cursor.execute("SELECT MAX(cycle_number) as max_cycle FROM performance_metrics")
    max_cycle_row = cursor.fetchone()
    max_cycle = max_cycle_row[0] if max_cycle_row and max_cycle_row[0] else 0
    
    cursor.execute("SELECT COUNT(*) as count FROM signal_configurations WHERE applied = 1")
    total_adaptations = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) as count FROM signal_configurations WHERE rolled_back = 1")
    total_rollbacks = cursor.fetchone()[0]
    
    summary = {
        'experiment_name': experiment_name,
        'total_cycles': max_cycle,
        'total_adaptations': total_adaptations,
        'total_rollbacks': total_rollbacks
    }
    
    summary_path = output_dir / f"{experiment_name}_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"Exported summary to {summary_path}")
    
    close_connection(conn)

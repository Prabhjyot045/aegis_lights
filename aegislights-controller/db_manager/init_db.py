"""Initialize SQLite database schema for AegisLights."""

import sqlite3
from pathlib import Path
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


# Define expected schema
EXPECTED_TABLES = [
    'simulation_snapshots',
    'graph_state',
    'signal_configurations',
    'phase_libraries',
    'performance_metrics',
    'adaptation_decisions',
    'bandit_state',
    'cycle_logs'
]

EXPECTED_INDICES = [
    'idx_snapshots_cycle',
    'idx_snapshots_edge_id',
    'idx_graph_from_intersection',
    'idx_graph_to_intersection',
    'idx_configs_cycle',
    'idx_configs_intersection',
    'idx_metrics_cycle',
    'idx_decisions_cycle',
    'idx_cycle_logs_cycle'
]


def initialize_database(db_path: str) -> str:
    """
    Initialize the SQLite database with all required tables.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        str: Absolute path to the initialized database
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Table 1: simulation_snapshots (Historical Data)
    # Stores edge-level traffic data from CityFlow per cycle
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simulation_snapshots (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_number INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            edge_id TEXT NOT NULL,
            from_intersection TEXT NOT NULL,
            to_intersection TEXT NOT NULL,
            queue_length INTEGER,
            delay REAL,
            throughput REAL,
            spillback_flag INTEGER,
            incident_flag INTEGER,
            UNIQUE(cycle_number, edge_id)
        )
    """)
    
    # Table 2: graph_state (Runtime Model - Current State)
    # Stores current state of each edge in the network
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS graph_state (
            edge_id TEXT PRIMARY KEY,
            from_intersection TEXT NOT NULL,
            to_intersection TEXT NOT NULL,
            is_virtual_source INTEGER DEFAULT 0,
            is_virtual_sink INTEGER DEFAULT 0,
            capacity REAL NOT NULL,
            free_flow_time REAL NOT NULL,
            length REAL DEFAULT 0.0,
            current_queue REAL DEFAULT 0.0,
            current_delay REAL DEFAULT 0.0,
            current_flow REAL DEFAULT 0.0,
            spillback_active INTEGER DEFAULT 0,
            incident_active INTEGER DEFAULT 0,
            last_updated_cycle INTEGER DEFAULT 0,
            edge_cost REAL DEFAULT 0.0,
            last_updated_timestamp REAL
        )
    """)
    
    # Table 3: signal_configurations (Adaptation Actions)
    # Tracks signal phase changes applied to CityFlow intersections
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_configurations (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            intersection_id TEXT NOT NULL,
            cycle_number INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            plan_id TEXT,
            phase_id INTEGER,
            green_splits TEXT,
            cycle_length REAL,
            offset REAL,
            is_incident_mode INTEGER DEFAULT 0,
            applied INTEGER DEFAULT 0,
            rolled_back INTEGER DEFAULT 0
        )
    """)
    
    # Table 4: phase_libraries (Knowledge - Pre-verified Plans)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS phase_libraries (
            plan_id TEXT PRIMARY KEY,
            intersection_id TEXT NOT NULL,
            plan_name TEXT,
            phases TEXT,  -- JSON with movements, min/max greens
            pedestrian_compliant INTEGER DEFAULT 1,
            safety_validated INTEGER DEFAULT 1
        )
    """)
    
    # Table 5: performance_metrics (Evaluation)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_number INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            avg_trip_time REAL,
            p95_trip_time REAL,
            total_spillbacks INTEGER,
            total_stops INTEGER,
            incident_clearance_time REAL,
            utility_score REAL
        )
    """)
    
    # Table 6: adaptation_decisions (Explainability)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS adaptation_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_number INTEGER NOT NULL,
            stage TEXT NOT NULL,  -- monitor, analyze, plan, execute
            decision_type TEXT,
            reasoning TEXT,  -- JSON
            context TEXT  -- JSON
        )
    """)
    
    # Table 7: bandit_state (Contextual Bandit Learning)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bandit_state (
            state_id INTEGER PRIMARY KEY AUTOINCREMENT,
            intersection_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            context_hash TEXT,
            times_selected INTEGER DEFAULT 0,
            total_reward REAL DEFAULT 0.0,
            avg_reward REAL DEFAULT 0.0,
            confidence REAL DEFAULT 0.0,
            UNIQUE(intersection_id, plan_id, context_hash)
        )
    """)
    
    # Table 8: cycle_logs (Execution Logging)
    # Logs execution events and rollbacks for debugging
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cycle_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle INTEGER NOT NULL,
            stage TEXT NOT NULL,
            timestamp REAL NOT NULL,
            data TEXT
        )
    """)
    
    # Create indices for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_cycle ON simulation_snapshots(cycle_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_edge_id ON simulation_snapshots(edge_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_from_intersection ON graph_state(from_intersection)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_graph_to_intersection ON graph_state(to_intersection)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_configs_cycle ON signal_configurations(cycle_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_configs_intersection ON signal_configurations(intersection_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_cycle ON performance_metrics(cycle_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_cycle ON adaptation_decisions(cycle_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cycle_logs_cycle ON cycle_logs(cycle)")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized with 8 tables at: {db_path.absolute()}")
    return str(db_path.absolute())


def verify_database(db_path: str) -> Dict[str, any]:
    """
    Verify database structure is correct.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Dict with verification results:
        - valid: bool
        - tables: list of existing tables
        - indices: list of existing indices
        - missing_tables: list of missing tables (if any)
        - missing_indices: list of missing indices (if any)
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        return {
            'valid': False,
            'error': 'Database file does not exist',
            'tables': [],
            'indices': []
        }
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    existing_tables = [row[0] for row in cursor.fetchall()]
    
    # Check indices
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
    existing_indices = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
    
    conn.close()
    
    # Compare with expected
    missing_tables = [t for t in EXPECTED_TABLES if t not in existing_tables]
    missing_indices = [i for i in EXPECTED_INDICES if i not in existing_indices]
    
    is_valid = len(missing_tables) == 0 and len(missing_indices) == 0
    
    result = {
        'valid': is_valid,
        'tables': existing_tables,
        'indices': existing_indices,
        'missing_tables': missing_tables,
        'missing_indices': missing_indices
    }
    
    if is_valid:
        logger.info(f"Database verification passed: {len(existing_tables)} tables, {len(existing_indices)} indices")
    else:
        logger.warning(f"Database verification failed: missing {len(missing_tables)} tables, {len(missing_indices)} indices")
    
    return result


def get_database_info(db_path: str) -> Dict[str, any]:
    """
    Get detailed information about database structure.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Dict with table schemas and row counts
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        return {'error': 'Database file does not exist'}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    info = {
        'path': str(db_path.absolute()),
        'size_bytes': db_path.stat().st_size,
        'tables': {}
    }
    
    # Get table information
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in tables:
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [
            {
                'name': row[1],
                'type': row[2],
                'not_null': bool(row[3]),
                'primary_key': bool(row[5])
            }
            for row in cursor.fetchall()
        ]
        
        info['tables'][table] = {
            'row_count': row_count,
            'columns': columns
        }
    
    conn.close()
    return info

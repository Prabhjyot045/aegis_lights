"""Clean up and reset database for next experiment."""

import sqlite3
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def cleanup_database(db_path: str) -> None:
    """
    Clean up database by removing all data from tables.
    Keeps schema intact for next experiment.
    
    Args:
        db_path: Path to the SQLite database file
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        logger.warning(f"Database not found at {db_path}, nothing to clean up")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Clear all tables (except graph_state which gets reset)
    tables = [
        'simulation_snapshots',
        'signal_configurations',
        'performance_metrics',
        'adaptation_decisions',
        'bandit_state',
        'cycle_logs'
    ]
    
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
        logger.debug(f"Cleared table: {table}")
    
    # Reset graph_state (but keep structure)
    cursor.execute("""
        UPDATE graph_state 
        SET current_queue = 0.0,
            current_delay = 0.0,
            current_flow = 0.0,
            spillback_active = 0,
            incident_active = 0,
            last_updated_cycle = 0,
            edge_cost = 0.0,
            last_updated_timestamp = NULL
    """)
    logger.debug("Reset graph_state to initial values")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database cleaned up successfully: {db_path}")


def delete_database(db_path: str) -> None:
    """
    Completely delete the database file.
    
    Args:
        db_path: Path to the SQLite database file
    """
    db_path = Path(db_path)
    
    if db_path.exists():
        db_path.unlink()
        logger.info(f"Database deleted: {db_path}")
    else:
        logger.warning(f"Database not found at {db_path}, nothing to delete")

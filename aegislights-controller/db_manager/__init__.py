"""Database management modules for AegisLights."""

from .init_db import initialize_database, verify_database, get_database_info
from .cleanup_db import cleanup_database
from .phase_library import PhaseLibrary
from .db_utils import (
    get_connection,
    close_connection,
    insert_snapshot,
    update_graph_state,
    get_graph_state,
    get_outgoing_roads,
    insert_or_update_graph_edge,
    insert_signal_config,
    get_last_known_good_config,
    insert_performance_metrics,
    export_experiment_data
)

__all__ = [
    'initialize_database',
    'verify_database',
    'get_database_info',
    'cleanup_database',
    'PhaseLibrary',
    'get_connection',
    'close_connection',
    'insert_snapshot',
    'update_graph_state',
    'get_graph_state',
    'get_outgoing_roads',
    'insert_or_update_graph_edge',
    'insert_signal_config',
    'get_last_known_good_config',
    'insert_performance_metrics',
    'export_experiment_data'
]

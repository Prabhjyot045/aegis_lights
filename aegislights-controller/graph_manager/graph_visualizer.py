"""Web-based live graph visualization using Flask and D3.js.

Runs as standalone web server that queries database for real-time network state.
Can be started independently from MAPE loop for live monitoring.
"""

import logging
import json
import time
import threading
import sqlite3
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

try:
    from flask import Flask, render_template, jsonify, send_from_directory
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    logging.warning("Flask not available. Install with: pip install flask flask-cors")

from config.visualization import VisualizationConfig

logger = logging.getLogger(__name__)


class GraphVisualizer:
    """
    Web-based real-time visualization of traffic graph state.
    
    Runs Flask web server that serves interactive D3.js visualization.
    Queries database independently for network state updates.
    """
    
    def __init__(self, db_path: str, host: str = '0.0.0.0', port: int = 5001,
                 auto_refresh: bool = True, refresh_interval: int = 2):
        """
        Initialize web-based graph visualizer.
        
        Args:
            db_path: Path to SQLite database
            host: Host address for web server (0.0.0.0 for all interfaces)
            port: Port for web server (default: 5001)
            auto_refresh: Whether to auto-refresh visualization
            refresh_interval: Refresh interval in seconds
        """
        if not FLASK_AVAILABLE:
            raise ImportError("Flask is required for web visualization. Install with: pip install flask flask-cors")
        
        self.db_path = db_path
        self.host = host
        self.port = port
        self.auto_refresh = auto_refresh
        self.refresh_interval = refresh_interval
        self.config = VisualizationConfig()
        
        self.running = False
        self._server_thread = None
        self._app = None
        
        logger.info(f"Web visualizer initialized on http://{host}:{port}")
    
    def start(self) -> None:
        """
        Start the web server in a separate thread.
        Non-blocking - allows MAPE loop to continue or run independently.
        """
        if self.running:
            logger.warning("Visualizer already running")
            return
        
        if not FLASK_AVAILABLE:
            logger.error("Flask not available. Cannot start web visualizer.")
            return
        
        self.running = True
        self._create_flask_app()
        
        # Start Flask server in daemon thread
        self._server_thread = threading.Thread(
            target=self._run_flask_server,
            daemon=True
        )
        self._server_thread.start()
        
        logger.info(f"✅ Web visualizer started at http://{self.host}:{self.port}")
        logger.info(f"   Open in browser: http://localhost:{self.port}")
        logger.info(f"   Auto-refresh: {self.auto_refresh} (interval: {self.refresh_interval}s)")
    
    def stop(self) -> None:
        """Stop the web server."""
        if not self.running:
            return
        
        self.running = False
        logger.info("Web visualizer stopped")
    
    def update(self, graph=None) -> None:
        """
        No-op for web visualizer (queries database directly).
        Kept for compatibility with existing code.
        """
        pass
    
    def update_metrics(self, cycle: int, incidents: int, adaptations: int, avg_delay: float) -> None:
        """
        No-op for web visualizer (queries database directly).
        Kept for compatibility with existing code.
        """
        pass
    
    def _create_flask_app(self) -> None:
        """Create and configure Flask application."""
        self._app = Flask(__name__, 
                         template_folder=str(Path(__file__).parent / 'templates'),
                         static_folder=str(Path(__file__).parent / 'static'))
        CORS(self._app)
        
        # Route: Main visualization page
        @self._app.route('/')
        def index():
            return render_template('visualizer.html', 
                                 auto_refresh=self.auto_refresh,
                                 refresh_interval=self.refresh_interval * 1000)  # Convert to ms
        
        # API: Get current network state
        @self._app.route('/api/network')
        def get_network():
            try:
                data = self._get_network_data()
                return jsonify(data)
            except Exception as e:
                logger.error(f"Error fetching network data: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        # API: Get current metrics
        @self._app.route('/api/metrics')
        def get_metrics():
            try:
                data = self._get_metrics_data()
                return jsonify(data)
            except Exception as e:
                logger.error(f"Error fetching metrics: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        # API: Get performance history
        @self._app.route('/api/history')
        def get_history():
            try:
                data = self._get_history_data()
                return jsonify(data)
            except Exception as e:
                logger.error(f"Error fetching history: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500
        
        # Disable Flask request logging to reduce console noise
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(flask_logging.ERROR)
    
    def _run_flask_server(self) -> None:
        """Run Flask server (called in daemon thread)."""
        try:
            self._app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"Flask server error: {e}", exc_info=True)
    
    def _get_network_data(self) -> Dict:
        """Query database for current network state."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get latest cycle number
        cursor.execute("SELECT MAX(last_updated_cycle) as max_cycle FROM graph_state")
        row = cursor.fetchone()
        current_cycle = row['max_cycle'] if row and row['max_cycle'] else 0
        
        # Get nodes - all intersections from graph_state
        cursor.execute("""
            SELECT DISTINCT from_intersection as node_id
            FROM graph_state
            UNION
            SELECT DISTINCT to_intersection as node_id
            FROM graph_state
        """)
        
        nodes = []
        for row in cursor.fetchall():
            nodes.append({
                'id': row['node_id'],
                'type': 'signalized' if row['node_id'] in ['A', 'B', 'C', 'D', 'E'] else 'virtual'
            })
        
        # Get edges with current state
        cursor.execute("""
            SELECT 
                edge_id,
                from_intersection as source,
                to_intersection as target,
                current_queue as queue,
                current_delay as delay,
                current_flow as flow,
                spillback_active as spillback,
                incident_active as incident,
                capacity,
                free_flow_time,
                edge_cost
            FROM graph_state
            ORDER BY edge_id
        """)
        
        edges = []
        for row in cursor.fetchall():
            # Calculate edge cost
            cost = (
                1.0 * (row['delay'] or 0) +
                0.5 * (row['queue'] or 0) +
                10.0 * (1 if row['spillback'] else 0) +
                20.0 * (1 if row['incident'] else 0)
            )
            
            edges.append({
                'id': row['edge_id'],
                'source': row['source'],
                'target': row['target'],
                'queue': row['queue'] or 0,
                'delay': row['delay'] or 0,
                'flow': row['flow'] or 0,
                'spillback': bool(row['spillback']),
                'incident': bool(row['incident']),
                'capacity': row['capacity'] or 1000,
                'cost': cost
            })
        
        conn.close()
        
        return {
            'cycle': current_cycle,
            'timestamp': datetime.now().isoformat(),
            'nodes': nodes,
            'edges': edges
        }
    
    def _get_metrics_data(self) -> Dict:
        """Query database for current metrics."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get latest cycle from performance_metrics
        cursor.execute("""
            SELECT 
                cycle_number,
                avg_trip_time,
                total_spillbacks,
                utility_score,
                timestamp
            FROM performance_metrics
            ORDER BY cycle_number DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            metrics = {
                'cycle': row['cycle_number'],
                'avg_delay': row['avg_trip_time'] or 0,  # For backward compatibility
                'avg_trip_time': row['avg_trip_time'] or 0,
                'network_cost': row['utility_score'] or 0,
                'total_spillbacks': row['total_spillbacks'] or 0,
                'timestamp': row['timestamp']
            }
        else:
            metrics = {
                'cycle': 0,
                'avg_delay': 0,
                'avg_trip_time': 0,
                'network_cost': 0,
                'total_spillbacks': 0,
                'timestamp': time.time()
            }
        
        # Calculate average queue from graph_state
        cursor.execute("""
            SELECT AVG(current_queue) as avg_queue
            FROM graph_state
        """)
        row = cursor.fetchone()
        metrics['avg_queue'] = row['avg_queue'] if row and row['avg_queue'] else 0
        
        # Get count of active incidents
        cursor.execute("""
            SELECT COUNT(*) as incident_count
            FROM graph_state
            WHERE incident_active = 1
        """)
        
        row = cursor.fetchone()
        metrics['incidents'] = row['incident_count'] if row else 0
        
        # Get count of recent adaptations
        cursor.execute("""
            SELECT COUNT(*) as adaptation_count
            FROM signal_configurations
            WHERE cycle_number = ?
        """, (metrics['cycle'],))
        
        row = cursor.fetchone()
        metrics['adaptations'] = row['adaptation_count'] if row else 0
        
        conn.close()
        
        return metrics
    
    def _get_history_data(self, limit: int = 50) -> Dict:
        """Query database for performance history."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                cycle_number,
                avg_trip_time,
                total_spillbacks,
                utility_score,
                timestamp
            FROM performance_metrics
            ORDER BY cycle_number DESC
            LIMIT ?
        """, (limit,))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'cycle': row['cycle_number'],
                'avg_delay': row['avg_trip_time'] or 0,
                'avg_trip_time': row['avg_trip_time'] or 0,
                'network_cost': row['utility_score'] or 0,
                'total_spillbacks': row['total_spillbacks'] or 0,
                'timestamp': row['timestamp']
            })
        
        conn.close()
        
        # Reverse to get chronological order
        history.reverse()
        
        return {'history': history}


def run_visualizer_standalone(db_path: str, host: str = '0.0.0.0', port: int = 5001):
    """
    Run visualizer as standalone application.
    
    Usage:
        python -m graph_manager.graph_visualizer /path/to/aegis.db
    """
    visualizer = GraphVisualizer(db_path=db_path, host=host, port=port)
    visualizer.start()
    
    print(f"\n{'='*60}")
    print(f"🌐 AEGIS LIGHTS - Web Visualizer")
    print(f"{'='*60}")
    print(f"Server: http://localhost:{port}")
    print(f"Database: {db_path}")
    print(f"")
    print(f"Press Ctrl+C to stop...")
    print(f"{'='*60}\n")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down visualizer...")
        visualizer.stop()


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='AEGIS LIGHTS Web Visualizer')
    parser.add_argument('db_path', help='Path to SQLite database')
    parser.add_argument('--host', default='0.0.0.0', help='Host address (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5001, help='Port number (default: 5001)')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_visualizer_standalone(args.db_path, args.host, args.port)

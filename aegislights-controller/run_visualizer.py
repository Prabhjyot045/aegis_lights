#!/usr/bin/env python3
"""
Standalone script to run the AEGIS LIGHTS Web Visualizer.
This script can be run independently of the MAPE loop.
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path to import from graph_manager
sys.path.insert(0, str(Path(__file__).parent))

# Import directly from the graph_visualizer module file
# This avoids loading graph_manager/__init__.py which imports networkx
import importlib.util
spec = importlib.util.spec_from_file_location(
    "graph_visualizer_module",
    Path(__file__).parent / "graph_manager" / "graph_visualizer.py"
)
graph_visualizer_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph_visualizer_module)

GraphVisualizer = graph_visualizer_module.GraphVisualizer


def main():
    """Run the web visualizer standalone."""
    parser = argparse.ArgumentParser(
        description='AEGIS LIGHTS Web Visualizer - Real-time traffic network visualization'
    )
    parser.add_argument(
        'db_path',
        type=str,
        help='Path to the SQLite database file (e.g., data/aegis_lights.db)'
    )
    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Host address to bind the web server (default: 127.0.0.1, use 0.0.0.0 for all interfaces)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5001,
        help='Port number for the web server (default: 5001)'
    )
    parser.add_argument(
        '--no-auto-refresh',
        action='store_true',
        help='Disable automatic refresh of the visualization'
    )
    parser.add_argument(
        '--refresh-interval',
        type=int,
        default=2000,
        help='Auto-refresh interval in milliseconds (default: 2000)'
    )
    
    args = parser.parse_args()
    
    # Validate database path
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"❌ Error: Database file not found: {db_path}")
        print(f"\nTip: Create the database first by running:")
        print(f"  python db_manager/setup_db.py")
        sys.exit(1)
    
    print("=" * 80)
    print("🚦 AEGIS LIGHTS - Web Visualizer")
    print("=" * 80)
    print(f"\nDatabase: {db_path.absolute()}")
    print(f"Server:   http://{args.host}:{args.port}")
    print(f"Auto-refresh: {'Enabled' if not args.no_auto_refresh else 'Disabled'}")
    if not args.no_auto_refresh:
        print(f"Refresh interval: {args.refresh_interval}ms")
    print("\n" + "=" * 80)
    print("Press Ctrl+C to stop the server")
    print("=" * 80 + "\n")
    
    # Create visualizer
    visualizer = GraphVisualizer(
        db_path=str(db_path.absolute()),
        host=args.host,
        port=args.port,
        auto_refresh=not args.no_auto_refresh,
        refresh_interval=args.refresh_interval / 1000  # Convert ms to seconds
    )
    
    try:
        # Create Flask app and run in foreground (blocking)
        visualizer._create_flask_app()
        visualizer._app.run(
            host=args.host,
            port=args.port,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n\n👋 Visualizer stopped by user")
    except Exception as e:
        print(f"\n❌ Error running visualizer: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

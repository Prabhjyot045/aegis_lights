"""Live graph visualization with recording capability."""

import logging
from typing import Optional, Dict
from pathlib import Path
import matplotlib
matplotlib.use('TkAgg')  # Use Tk backend for interactive mode
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
import networkx as nx

from .graph_model import TrafficGraph
from config.visualization import VisualizationConfig

logger = logging.getLogger(__name__)


class GraphVisualizer:
    """Real-time visualization of traffic graph state using matplotlib interactive mode."""
    
    def __init__(self, graph: TrafficGraph, record: bool = False,
                 output_dir: Optional[Path] = None):
        """
        Initialize graph visualizer.
        
        Args:
            graph: Traffic graph to visualize
            record: Whether to record video
            output_dir: Directory for recording output
        """
        self.graph = graph
        self.config = VisualizationConfig()
        self.record = record
        self.output_dir = Path(output_dir) if output_dir else Path("output/videos")
        
        self.running = False
        self._frame_count = 0
        self._animation = None
        
        # Matplotlib components
        self.fig = None
        self.ax = None
        self.pos = None  # Node positions (computed once)
        self.writer = None
        
        # Metrics cache for display
        self._metrics_cache: Dict = {
            'cycle': 0,
            'incidents': 0,
            'adaptations': 0,
            'avg_delay': 0.0
        }
        
        if self.record:
            self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def start(self) -> None:
        """Start the visualizer with interactive mode."""
        if self.running:
            logger.warning("Visualizer already running")
            return
        
        self.running = True
        self._initialize_plot()
        
        # Turn on interactive mode
        plt.ion()
        plt.show(block=False)
        
        logger.info("Graph visualizer started")
    
    def stop(self) -> None:
        """Stop the visualizer and save recording if enabled."""
        if not self.running:
            return
        
        self.running = False
        
        if self._animation:
            self._animation.event_source.stop()
        
        if self.record:
            self._finalize_recording()
        
        if self.fig:
            plt.ioff()
            plt.close(self.fig)
        
        logger.info("Graph visualizer stopped")
    
    def update(self) -> None:
        """
        Manually update visualization with current graph state.
        Call this after making changes to the graph to refresh the display.
        """
        if self.running and self.fig:
            self._render_frame()
    
    def pause_until_closed(self) -> None:
        """
        Keep the visualization window open until user closes it.
        Blocks execution until window is closed.
        """
        if self.fig and plt.fignum_exists(self.fig.number):
            plt.ioff()
            plt.show()  # Blocking show
    
    def update_metrics(self, cycle: int, incidents: int, adaptations: int, avg_delay: float) -> None:
        """Update metrics display cache."""
        self._metrics_cache = {
            'cycle': cycle,
            'incidents': incidents,
            'adaptations': adaptations,
            'avg_delay': avg_delay
        }
    
    def _initialize_plot(self) -> None:
        """Initialize matplotlib figure and compute layout."""
        self.fig, self.ax = plt.subplots(figsize=(16, 9))
        self.fig.canvas.manager.set_window_title(self.config.window_title)
        
        # Compute node positions using NetworkX layout
        nx_graph = self._to_networkx()
        
        if self.config.layout_algorithm == 'spring':
            self.pos = nx.spring_layout(nx_graph, k=2, iterations=50)
        elif self.config.layout_algorithm == 'circular':
            self.pos = nx.circular_layout(nx_graph)
        else:  # kamada_kawai
            self.pos = nx.kamada_kawai_layout(nx_graph)
        
        logger.info(f"Layout computed with {len(self.pos)} nodes")
        
        # Render initial frame
        self._render_frame()
    
    def _render_frame(self) -> None:
        """Render a single frame of the visualization."""
        if not self.ax or not self.pos:
            return
        
        self.ax.clear()
        self.ax.set_title(
            f"Traffic Network - Cycle {self._metrics_cache['cycle']} | "
            f"Incidents: {self._metrics_cache['incidents']} | "
            f"Adaptations: {self._metrics_cache['adaptations']} | "
            f"Avg Delay: {self._metrics_cache['avg_delay']:.1f}s",
            fontsize=14, pad=20
        )
        self.ax.axis('off')
        
        # Get node and edge colors/widths
        node_colors = [self._get_node_color(self.graph.nodes[node_id]) 
                      for node_id in self.pos.keys()]
        
        edge_colors = []
        edge_widths = []
        for edge_key in self.graph.edges.keys():
            edge = self.graph.edges[edge_key]
            edge_colors.append(self._get_edge_color(edge))
            edge_widths.append(self._get_edge_width(edge))
        
        # Convert to NetworkX for drawing
        nx_graph = self._to_networkx()
        
        # Draw edges
        nx.draw_networkx_edges(
            nx_graph, self.pos, ax=self.ax,
            edge_color=edge_colors,
            width=edge_widths,
            arrows=True,
            arrowsize=15,
            arrowstyle='->',
            connectionstyle='arc3,rad=0.1'
        )
        
        # Draw nodes
        nx.draw_networkx_nodes(
            nx_graph, self.pos, ax=self.ax,
            node_color=node_colors,
            node_size=self.config.node_size,
            node_shape=self.config.node_shape,
            edgecolors='black',
            linewidths=2
        )
        
        # Draw node IDs
        nx.draw_networkx_labels(
            nx_graph, self.pos, ax=self.ax,
            font_size=8,
            font_weight='bold'
        )
        
        # Add edge labels with queue/delay metrics
        edge_labels = {}
        for edge_key, edge in self.graph.edges.items():
            from_node, to_node = edge_key
            label = f"Q:{edge.current_queue:.0f}\nD:{edge.current_delay:.1f}s"
            edge_labels[(from_node, to_node)] = label
        
        nx.draw_networkx_edge_labels(
            nx_graph, self.pos, edge_labels, ax=self.ax,
            font_size=6,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="gray", alpha=0.8)
        )
        
        # Add legend
        self._add_legend()
        
        # Add metrics panel
        if self.config.show_metrics_panel:
            self._add_metrics_panel()
        
        plt.tight_layout()
        
        # Update display
        if self.running and plt.fignum_exists(self.fig.number):
            self.fig.canvas.draw()
            self.fig.canvas.flush_events()
            plt.pause(0.001)  # Allow GUI events to process
        
        self._frame_count += 1
    
    def _finalize_recording(self) -> None:
        """Placeholder for future video recording functionality."""
        # Video recording temporarily disabled due to threading issues
        # Will be reimplemented with alternative approach
        pass
    
    def _get_node_color(self, node) -> str:
        """Get color for node based on state."""
        if node.has_spillback:
            return self.config.node_color_spillback
        elif node.is_congested:
            return self.config.node_color_congested
        else:
            return self.config.node_color_normal
    
    def _get_edge_color(self, edge) -> str:
        """Get color for edge based on state."""
        if edge.incident_active:
            return self.config.edge_color_incident
        elif edge.edge_cost > 10.0:  # High cost threshold
            return self.config.edge_color_high_cost
        else:
            return self.config.edge_color_normal
    
    def _get_edge_width(self, edge) -> float:
        """Get edge width based on queue length."""
        return (
            self.config.edge_width_base + 
            edge.current_queue * self.config.edge_width_multiplier
        )
    
    def _to_networkx(self) -> nx.DiGraph:
        """Convert current graph state to NetworkX graph."""
        G = nx.DiGraph()
        
        # Add nodes
        for node_id in self.graph.nodes.keys():
            G.add_node(node_id)
        
        # Add edges
        for edge_key, edge in self.graph.edges.items():
            from_node, to_node = edge_key
            G.add_edge(from_node, to_node, weight=edge.edge_cost)
        
        return G
    
    def _add_legend(self) -> None:
        """Add color legend to plot."""
        legend_elements = [
            mpatches.Patch(color=self.config.node_color_normal, label='Normal Node'),
            mpatches.Patch(color=self.config.node_color_congested, label='Congested Node'),
            mpatches.Patch(color=self.config.node_color_spillback, label='Spillback Node'),
            mpatches.Patch(color=self.config.edge_color_normal, label='Normal Edge'),
            mpatches.Patch(color=self.config.edge_color_high_cost, label='High Cost Edge'),
            mpatches.Patch(color=self.config.edge_color_incident, label='Incident Edge')
        ]
        
        self.ax.legend(
            handles=legend_elements,
            loc='upper right',
            fontsize=10,
            framealpha=0.9
        )
    
    def _add_metrics_panel(self) -> None:
        """Add metrics text panel to plot."""
        metrics_text = (
            f"Network Status\n"
            f"─────────────\n"
            f"Total Nodes: {len(self.graph.nodes)}\n"
            f"Total Edges: {len(self.graph.edges)}\n"
            f"Congested: {len(self.graph.get_congested_nodes())}\n"
            f"Spillbacks: {len(self.graph.get_spillback_edges())}\n"
            f"Active Incidents: {self._metrics_cache['incidents']}"
        )
        
        self.ax.text(
            0.02, 0.98,
            metrics_text,
            transform=self.ax.transAxes,
            fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9),
            family='monospace'
        )

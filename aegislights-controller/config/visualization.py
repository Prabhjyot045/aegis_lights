"""Visualization configuration."""

from dataclasses import dataclass


@dataclass
class VisualizationConfig:
    """Configuration for graph visualization."""
    
    # Display settings
    window_title: str = "AegisLights - Traffic Network Visualization"
    window_width: int = 1600
    window_height: int = 900
    update_interval_ms: int = 1000  # Update display every N milliseconds
    
    # Graph layout
    layout_algorithm: str = "spring"  # Options: spring, circular, kamada_kawai
    node_size: int = 500
    node_shape: str = "o"  # Circle
    
    # Color schemes
    node_color_normal: str = "#2ecc71"      # Green
    node_color_congested: str = "#f39c12"   # Orange
    node_color_spillback: str = "#e74c3c"   # Red
    
    edge_color_normal: str = "#95a5a6"      # Gray
    edge_color_high_cost: str = "#e67e22"   # Dark orange
    edge_color_incident: str = "#c0392b"    # Dark red
    
    # Edge styling
    edge_width_base: float = 2.0
    edge_width_multiplier: float = 0.1  # Multiply by queue length
    
    # Recording
    record_fps: int = 10
    video_codec: str = "mp4v"
    video_format: str = "mp4"
    
    # Dashboard panels
    show_cycle_info: bool = True
    show_incident_panel: bool = True
    show_adaptation_panel: bool = True
    show_metrics_panel: bool = True

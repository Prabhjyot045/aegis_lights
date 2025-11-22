"""Tests for graph export and visualization functionality."""

import pytest
import tempfile
import json
from pathlib import Path

from graph_manager.graph_model import TrafficGraph, GraphNode, GraphEdge
from graph_manager.graph_utils import (
    export_graph_to_json,
    export_graph_to_graphml,
    export_graph_snapshot
)
from graph_manager.graph_visualizer import GraphVisualizer


@pytest.fixture
def sample_graph():
    """Create a sample traffic graph for testing."""
    graph = TrafficGraph()
    
    # Add nodes
    node1 = GraphNode(node_id="n1", intersection_type="signalized")
    node2 = GraphNode(node_id="n2", intersection_type="signalized")
    node3 = GraphNode(node_id="n3", intersection_type="signalized")
    
    graph.add_node(node1)
    graph.add_node(node2)
    graph.add_node(node3)
    
    # Add edges
    edge1 = GraphEdge(
        from_node="n1",
        to_node="n2",
        capacity=50.0,
        current_delay=5.0,
        current_queue=10.0
    )
    edge2 = GraphEdge(
        from_node="n2",
        to_node="n3",
        capacity=60.0,
        current_delay=8.0,
        current_queue=15.0,
        spillback_active=True
    )
    edge3 = GraphEdge(
        from_node="n1",
        to_node="n3",
        capacity=40.0,
        current_delay=3.0,
        current_queue=5.0,
        incident_active=True
    )
    
    graph.add_edge(edge1)
    graph.add_edge(edge2)
    graph.add_edge(edge3)
    
    return graph


def test_export_graph_to_json(sample_graph):
    """Test JSON export of traffic graph."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        filepath = f.name
    
    try:
        # Export graph
        export_graph_to_json(sample_graph, filepath)
        
        # Verify file exists
        assert Path(filepath).exists()
        
        # Load and verify content
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        assert 'nodes' in data
        assert 'edges' in data
        assert 'metadata' in data
        
        assert len(data['nodes']) == 3
        assert len(data['edges']) == 3
        
        assert data['metadata']['total_nodes'] == 3
        assert data['metadata']['total_edges'] == 3
        
        # Check node structure
        node = data['nodes'][0]
        assert 'node_id' in node
        assert 'intersection_type' in node
        assert 'is_congested' in node
        
        # Check edge structure
        edge = data['edges'][0]
        assert 'from_node' in edge
        assert 'to_node' in edge
        assert 'capacity' in edge
        assert 'current_delay' in edge
        
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_export_graph_to_graphml(sample_graph):
    """Test GraphML export of traffic graph."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.graphml', delete=False) as f:
        filepath = f.name
    
    try:
        # Export graph
        export_graph_to_graphml(sample_graph, filepath)
        
        # Verify file exists
        assert Path(filepath).exists()
        
        # Verify it's valid XML (GraphML)
        with open(filepath, 'r') as f:
            content = f.read()
            assert '<?xml' in content
            assert '<graphml' in content
            assert '<node' in content
            assert '<edge' in content
        
    finally:
        Path(filepath).unlink(missing_ok=True)


def test_export_graph_snapshot(sample_graph):
    """Test snapshot export with cycle number."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cycle = 42
        
        # Export snapshot
        export_graph_snapshot(sample_graph, tmpdir, cycle)
        
        # Verify both files created
        json_file = Path(tmpdir) / f"graph_cycle_{cycle}.json"
        graphml_file = Path(tmpdir) / f"graph_cycle_{cycle}.graphml"
        
        assert json_file.exists()
        assert graphml_file.exists()
        
        # Verify JSON content
        with open(json_file, 'r') as f:
            data = json.load(f)
            assert len(data['nodes']) == 3
            assert len(data['edges']) == 3


def test_visualizer_initialization(sample_graph):
    """Test visualizer can be initialized."""
    viz = GraphVisualizer(sample_graph, record=False)
    
    assert viz.graph == sample_graph
    assert not viz.running
    assert viz._frame_count == 0
    assert viz._metrics_cache['cycle'] == 0


def test_visualizer_metrics_update(sample_graph):
    """Test metrics cache update."""
    viz = GraphVisualizer(sample_graph, record=False)
    
    viz.update_metrics(cycle=10, incidents=2, adaptations=5, avg_delay=12.5)
    
    assert viz._metrics_cache['cycle'] == 10
    assert viz._metrics_cache['incidents'] == 2
    assert viz._metrics_cache['adaptations'] == 5
    assert viz._metrics_cache['avg_delay'] == 12.5


def test_visualizer_color_mapping(sample_graph):
    """Test node and edge color mapping."""
    viz = GraphVisualizer(sample_graph, record=False)
    
    # Test node colors
    normal_node = sample_graph.nodes['n1']
    assert viz._get_node_color(normal_node) == viz.config.node_color_normal
    
    # Test edge colors
    normal_edge = sample_graph.edges[('n1', 'n2')]
    assert viz._get_edge_color(normal_edge) in [
        viz.config.edge_color_normal,
        viz.config.edge_color_high_cost
    ]
    
    incident_edge = sample_graph.edges[('n1', 'n3')]
    assert viz._get_edge_color(incident_edge) == viz.config.edge_color_incident


def test_visualizer_edge_width(sample_graph):
    """Test edge width calculation."""
    viz = GraphVisualizer(sample_graph, record=False)
    
    edge = sample_graph.edges[('n1', 'n2')]
    width = viz._get_edge_width(edge)
    
    expected = viz.config.edge_width_base + edge.current_queue * viz.config.edge_width_multiplier
    assert width == expected
    assert width > viz.config.edge_width_base  # Should be wider due to queue


def test_export_preserves_graph_state(sample_graph):
    """Test that export doesn't modify graph state."""
    # Capture original state
    original_nodes = len(sample_graph.nodes)
    original_edges = len(sample_graph.edges)
    original_edge_cost = sample_graph.edges[('n1', 'n2')].edge_cost
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        filepath = f.name
    
    try:
        export_graph_to_json(sample_graph, filepath)
        
        # Verify state unchanged
        assert len(sample_graph.nodes) == original_nodes
        assert len(sample_graph.edges) == original_edges
        assert sample_graph.edges[('n1', 'n2')].edge_cost == original_edge_cost
        
    finally:
        Path(filepath).unlink(missing_ok=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

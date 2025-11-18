import asyncio
from datetime import datetime

from app.adapters.simulator_client import EdgeMetrics, GlobalMetrics, SimulatorSnapshot
from app.mape.monitor import Monitor
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import RecentGlobalMetrics


def test_monitor_updates_graph_and_recent_metrics() -> None:
	runtime_graph = RuntimeGraph()
	recent_metrics = RecentGlobalMetrics()
	monitor = Monitor(runtime_graph=runtime_graph, db_session_factory=None, recent_metrics=recent_metrics)

	snapshot = SimulatorSnapshot(
		timestamp=datetime.utcnow(),
		edges=[
			EdgeMetrics(
				edge_id="A->B",
				queue_length_veh=7.0,
				mean_delay_s=15.0,
				spillback=True,
				incident=False,
				throughput_veh=20.0,
			)
		],
		globals=GlobalMetrics(avg_trip_time_s=500.0, p95_trip_time_s=800.0, total_spillbacks=2, incident_count=0),
	)

	asyncio.run(monitor.handle_snapshot(snapshot))

	edge_attrs = runtime_graph.graph.get_edge_data("A", "B")
	assert edge_attrs is not None
	assert edge_attrs["queue"] == 7.0
	assert edge_attrs["delay"] == 15.0
	latest = recent_metrics.get_latest()
	assert latest is not None
	assert latest.avg_trip_time_s == 500.0

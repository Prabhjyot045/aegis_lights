import asyncio
from datetime import datetime

from app.adapters.simulator_client import EdgeMetrics, GlobalMetrics, SimulatorClient, SimulatorSnapshot
from app.mape.loop import MAPELoop
from app.mape.plan import IntersectionPlanAction
from app.models.goals import default_goals
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import GlobalMetricsSnapshot, MAPEWorkingState, RecentGlobalMetrics


class StubMonitor:
	def __init__(self) -> None:
		self.snapshots = []

	async def handle_snapshot(self, snapshot: SimulatorSnapshot) -> None:
		self.snapshots.append(snapshot)


class StubSimulatorClient(SimulatorClient):
	def __init__(self, snapshot: SimulatorSnapshot) -> None:
		super().__init__()
		self._snapshot = snapshot

	def fetch_snapshot(self):  # type: ignore[override]
		return self._snapshot


class StubAnalyzer:
	def __init__(self) -> None:
		self.calls = 0

	def analyze(self) -> None:
		self.calls += 1


class StubPlanner:
	def __init__(self) -> None:
		self.plan_calls = 0
		self.observe_payloads: list[dict[str, float]] = []

	def plan(self):  # type: ignore[override]
		self.plan_calls += 1
		return [IntersectionPlanAction(intersection_id="I1", plan_id="planA", score=0.0)]

	def observe_outcome(self, metrics):  # type: ignore[override]
		self.observe_payloads.append(metrics)


class StubExecutor:
	def __init__(self) -> None:
		self.applied_actions: list[list[IntersectionPlanAction]] = []
		self.rollback_calls = 0

	def apply_actions(self, actions):  # type: ignore[override]
		self.applied_actions.append(list(actions))

	def rollback_if_needed(self) -> None:
		self.rollback_calls += 1


def test_mape_loop_polls_simulator_and_observes_rewards() -> None:
	runtime_graph = RuntimeGraph()
	working_state = MAPEWorkingState()
	goals = default_goals()
	recent_metrics = RecentGlobalMetrics()
	recent_metrics.update(
		GlobalMetricsSnapshot(
			timestamp=datetime.utcnow(),
			avg_trip_time_s=400.0,
			p95_trip_time_s=700.0,
			total_spillbacks=1,
			incident_count=0,
		)
	)

	snapshot = SimulatorSnapshot(
		timestamp=datetime.utcnow(),
		edges=[
			EdgeMetrics(
				edge_id="A->B",
				queue_length_veh=3.0,
				mean_delay_s=10.0,
				spillback=False,
				incident=False,
				throughput_veh=25.0,
			)
		],
		globals=GlobalMetrics(avg_trip_time_s=450.0, p95_trip_time_s=800.0, total_spillbacks=1, incident_count=0),
	)

	monitor = StubMonitor()
	simulator_client = StubSimulatorClient(snapshot)
	analyzer = StubAnalyzer()
	planner = StubPlanner()
	executor = StubExecutor()

	loop = MAPELoop(
		runtime_graph=runtime_graph,
		working_state=working_state,
		goals=goals,
		analyzer=analyzer,
		planner=planner,
		executor=executor,
		monitor=monitor,
		simulator_client=simulator_client,
		recent_metrics=recent_metrics,
		interval_seconds=0.01,
	)

	asyncio.run(loop.step())

	assert monitor.snapshots == [snapshot]
	assert analyzer.calls == 1
	assert planner.plan_calls == 1
	assert executor.applied_actions and executor.rollback_calls == 1
	assert planner.observe_payloads, "Planner should observe reward metrics before planning"

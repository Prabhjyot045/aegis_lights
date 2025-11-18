from app.adapters.simulator_client import SimulatorClient
from app.mape.execute import Executor
from app.mape.plan import IntersectionPlanAction
from app.models.goals import default_goals
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import RecentGlobalMetrics


class SpySimulatorClient(SimulatorClient):
	def __init__(self) -> None:
		super().__init__()
		self.calls: list[tuple[str, str]] = []

	def apply_signal_plan(self, intersection_id: str, plan_id: str) -> None:  # type: ignore[override]
		self.calls.append((intersection_id, plan_id))


def test_executor_applies_actions_and_updates_graph() -> None:
	runtime_graph = RuntimeGraph()
	sim_client = SpySimulatorClient()
	recent_metrics = RecentGlobalMetrics()
	executor = Executor(
		runtime_graph=runtime_graph,
		simulator_client=sim_client,
		goals=default_goals(),
		recent_metrics=recent_metrics,
	)

	actions = [
		IntersectionPlanAction(intersection_id="I1", plan_id="planA", score=0.5, reason="test"),
		IntersectionPlanAction(intersection_id="I2", plan_id="planB", score=0.7),
	]

	executor.apply_actions(actions)

	assert sim_client.calls == [("I1", "planA"), ("I2", "planB")]
	assert runtime_graph.graph.nodes["I1"]["current_plan_id"] == "planA"
	assert runtime_graph.graph.nodes["I1"]["plan_reason"] == "test"

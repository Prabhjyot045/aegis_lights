from app.mape.plan import BanditPolicy, Planner
from app.models.goals import default_goals
from app.models.graph_runtime import RuntimeGraph
from app.models.mape_working import IntersectionContext, MAPEWorkingState
from app.models.phase_library import PhaseLibrary, PhasePlan


class RecordingBandit(BanditPolicy):
	def __init__(self) -> None:
		self.select_calls: list[tuple[str, list[str]]] = []
		self.observe_calls: list[tuple[str, str, float]] = []

	def select_action(self, intersection_id, context_vec, candidate_ids):  # type: ignore[override]
		self.select_calls.append((intersection_id, list(candidate_ids)))
		return candidate_ids[-1]

	def observe(self, intersection_id, context_vec, action_id, reward):  # type: ignore[override]
		self.observe_calls.append((intersection_id, action_id, reward))


def _build_planner(recording_bandit: RecordingBandit) -> Planner:
	graph = RuntimeGraph()
	working_state = MAPEWorkingState()
	working_state.update_intersection_contexts(
		{
			"I1": IntersectionContext(
				intersection_id="I1",
				features={"incoming_incidents": 1, "incoming_queue_sum": 5},
			)
		}
	)
	phase_library = PhaseLibrary(
		[
			PhasePlan(plan_id="I1_default", intersection_id="I1", tags=["default"]),
			PhasePlan(plan_id="I1_incident_mode", intersection_id="I1", tags=["incident_mode"]),
		]
	)
	goals = default_goals()
	return Planner(
		runtime_graph=graph,
		working_state=working_state,
		goals=goals,
		phase_library=phase_library,
		bandit=recording_bandit,
	)


def test_planner_uses_phase_library_candidates() -> None:
	bandit = RecordingBandit()
	planner = _build_planner(bandit)

	actions = planner.plan()

	assert actions, "Planner should produce at least one action"
	assert bandit.select_calls == [("I1", ["I1_default", "I1_incident_mode"])]


def test_planner_observe_outcome_updates_bandit() -> None:
	bandit = RecordingBandit()
	planner = _build_planner(bandit)
	planner.plan()

	planner.observe_outcome({"avg_trip_time_s": 400.0, "p95_trip_time_s": 600.0})

	assert len(bandit.observe_calls) == 1
	intersection_id, action_id, reward = bandit.observe_calls[0]
	assert intersection_id == "I1"
	assert action_id in ("I1_default", "I1_incident_mode")
	assert 0.0 <= reward <= 1.0

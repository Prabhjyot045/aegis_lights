# AegisLights Controller

Micro adaptive traffic signal controller for ECE750 course project.

## Completion Checklist

- FastAPI app boots shared RuntimeGraph/Monitor/MAPE loop and exposes health, simulator ingest, and graph snapshot routes.
- Simulator client now supports a configurable HTTP contract (`SimulatorAPIContract`) with optional API key header and helper documentation hook.
- Phase library, bandit-ready planner, and reward-fed MAPE loop wired with shared RecentGlobalMetrics.
- Monitor persists cycle metrics to SQLite via SQLAlchemy models/session factory and updates RecentGlobalMetrics.
- Executor applies planner actions through the simulator client, annotates graph nodes, and performs automatic rollback when utility drops below `rollback_utility_threshold`.
- Unit and integration tests cover planner, monitor, executor, and loop orchestration.

## Outstanding Gaps

- `app/models/environment.py` and `app/adapters/visualization_adapter.py` remain placeholders.
- `app/visualization/static` and `app/visualization/templates` are empty shells awaiting UI assets.
- Real simulator endpoints are assumed; provide integration tests or mocks once the partner simulator is available.
- Visualization layer/scripts still need a second pass once simulator/database behavior stabilizes.

## Simulator HTTP Contract

The controller treats the traffic simulator as an HTTP peer defined by `SimulatorAPIContract` (see `app/core/config.py` for defaults and environment overrides):

| Purpose | Method | Path (relative to `SIMULATOR_BASE_URL`) | Auth |
| --- | --- | --- | --- |
| Fetch latest snapshot | `GET` | `/api/v1/controller/snapshot` | Optional `x-api-key` header |
| Apply signal plan | `POST` | `/api/v1/controller/intersections/{intersection_id}/plan` | Optional `x-api-key` header |

- Snapshot responses must match the `SimulatorSnapshot` schema (`timestamp`, `edges[]`, optional `globals`).
- Plan apply requests expect `{ "plan_id": "phase-123" }` JSON and respond with any 2xx code on success.
- Update `SIMULATOR_BASE_URL`, `SIMULATOR_SNAPSHOT_PATH`, `SIMULATOR_PLAN_PATH`, and `SIMULATOR_API_KEY` via environment variables to target a partner deployment.

## Data Validation & Safety

- Ingest endpoint `/simulator/snapshot` now rejects malformed payloads (negative queues/delays/throughput or empty edge lists) before they touch the Monitor.
- Executor monitors recent utility (computed from `RecentGlobalMetrics` + `AdaptationGoals`) and automatically rolls back to the last known safe plan once utility stays below `rollback_utility_threshold` for multiple cycles.
- SQLite persistence is initialized at startup (`init_db`) and reusable via `scripts/init_db.py` for manual bootstrapping.

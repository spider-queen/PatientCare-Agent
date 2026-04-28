# Spec: Agent Ops Observability

## Objective
Upgrade the patient-support agent from a demo-style workflow into a more business-like service by adding persistent run metrics, aggregate operations KPIs, and a workspace-visible ops snapshot.

The goal is not to make the model "more powerful" in this slice. The goal is to make the system measurable, explainable, and demoable with hard numbers:

- How long does a request take end to end?
- What share of traffic hits the fast path?
- How often does identity verification succeed?
- How reliable are tool calls?
- How often does memory retrieval fall back?

## Commands
- Backend tests: `conda --no-plugins run -n patient-agent-dev python -m pytest -q`
- Backend dev server: `conda --no-plugins run -n patient-agent-dev python -m uvicorn app.main:app --reload`
- Frontend dev server: `cd frontend && npm run dev`

## Project Structure
- `app/api/routes/agent.py`: request orchestration and per-run timing capture
- `app/api/routes/dashboard.py`: aggregate KPI endpoint
- `app/db/models.py`: persistent metrics model
- `app/services/agent_metrics_service.py`: metric persistence and aggregation
- `app/schemas/dashboard.py`: ops response contracts
- `frontend/src/components/*`: workspace ops snapshot UI
- `tests/`: regression coverage for metrics capture and aggregation

## Code Style
- Keep the runtime path explicit and conservative.
- Prefer simple counters and stage timings over abstract telemetry frameworks.
- Make every metric traceable back to one request-level decision.

Example:

```python
stage_timings_ms = {
    "patient_resolution_ms": 0,
    "memory_context_ms": 0,
    "agent_execution_ms": 0,
    "persistence_ms": 0,
}
```

## Testing Strategy
- Add unit-style tests for metric aggregation math.
- Add route-level regression tests to prove a request records a run metric.
- Keep tests independent of real LLM calls by mocking the harness boundary.

## Boundaries
- Always: record metrics with a stable `run_id`, preserve current request contract, keep tests green
- Ask first: introducing external telemetry vendors, message queues, or schema-breaking API changes
- Never: fabricate benchmark numbers, log secrets, or bypass privacy checks to improve metrics

## Success Criteria
- Every successful agent request writes one persistent run metric row.
- Metrics include stage timings and business-relevant flags such as fast-path, verification, and memory fallback.
- The backend exposes an aggregate ops endpoint with p50/p95 latency and rates.
- The workspace shows a compact ops snapshot based on real recorded runs.
- Regression tests cover metrics capture and aggregation.

## Open Questions
- Whether to promote the current SQLite-backed metrics table into a production telemetry pipeline later
- Whether to add request-failure metrics for all exception branches in a later slice

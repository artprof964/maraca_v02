# Current Process Status

## Latest Update - 2026-06-04

Workspace: `C:\Users\fredo\git_repos\MARACA\maraca_V02`

Current active program: `project_generalize`.

Status: in progress.
Finished: false.

2026-06-04 P5.3 backend service/env defaults validation:

- Live goal/context signal for this implementation turn reported an active goal with `9776` tokens used and no remaining-token ceiling, so the run proceeded under the user threshold rule.
- Re-read `current_process_status.md`, `project_generalize_handoff.md`, `project_generalize_tracker.md`, and `git status --short` before editing.
- Implemented/finished the selected `P5.3 backend service/env defaults inventory/parity` lane.
- Production behavior now preserves env-derived Qdrant collection defaults and Neo4j database defaults, explicit constructor override precedence, injected fake-client support, explicit `client=None` unavailable-client behavior, `.env.example` backend defaults, and secret-safe health/config output.
- Added parity coverage for missing-env health default rows and for omitted-client auto-loading versus explicit `client=None` unavailability in Qdrant and Neo4j adapters.
- Focused P5.3 pytest passed: `30 passed in 2.71s`.
- Backend-adjacent phase pytest passed: `70 passed in 3.14s`.
- Standard-library unittest discovery passed: `Ran 141 tests in 0.475s`, `OK`.
- Full pytest passed: `307 passed in 4.01s`.
- Lenient `rag-center-health --env-file .env.example` passed and reported Qdrant/Neo4j default rows.
- `rag-center-smoke` passed with one keyword candidate, keyword execution mode, one citation, 20 logs, and a cited answer.
- Strict service health was skipped because Docker Compose is installed but the Docker daemon/API pipe is unavailable on this host.
- Validator review found no blocking P5.3 behavior drift in env precedence, client semantics, redaction, health rows, or adapter config shape.
- Status: validated for P5.3; project remains in progress overall.
- Finished: false.

2026-06-04 current-run orientation:

- Live goal/context signal checked first: goal usage counter reported `197528` tokens used, with no active budget object, remaining-token ceiling, or direct context-window percentage exposed.
- Required project files and `git status --short --branch` were reread before edits.
- Project is not finalized overall. It remains validated through `P1.4.2 broader repository save/orchestration hook extraction`, and the active work is next-lane selection after that validation point.
- Dirty source/test/docs/tracker changes are present; continue without reverting unrelated edits.
- Continue with bounded orchestration unless an explicit over-50% current-context signal appears; if that happens, stop agent spawning and update tracker/status/handoff only.
- Prior tracker text referenced an OA1 orchestration agent named `Euler`; in this current OA1 loop, child-agent/thread spawning was not available, so no new child agents were started.

2026-06-04 OA1 lane selection update:

- Current OA1 loop checked available context/window signal; no active goal, remaining-token ceiling, or direct context percentage was exposed, so no explicit over-50% signal was available.
- Child-agent/thread spawning is unavailable in the current toolset; tool discovery found no `create_thread` or `send_message_to_thread` capability.
- Required project files were reread and `git status --short` plus high-level diffs were reviewed before this status update.
- Selected next safest production optimization lane: `P5.3 backend service/env defaults inventory/parity`, supported by evidence ids `D-05` and `B-01` and summary findings ranks 6 and 7.
- Rationale: current dirty material already clusters around Qdrant/Neo4j env defaults, backend health checks, adapter config serialization, `.env.example`, and redacted connection settings; this is narrower and safer than durable persistence wrappers or broad telemetry-builder extraction.
- Acceptance criteria: preserve explicit override precedence, default Qdrant collection and Neo4j database behavior, injected fake-client support, explicit `client=None` unavailable paths, health/config redaction, and existing backend defaults.
- Required test-first inventory/parity gates: focused backend health tests, focused Qdrant/Neo4j adapter tests, optional connection-settings redaction tests if included, backend-adjacent phase tests, unittest discovery, full pytest, lenient health, smoke, and strict service health only when Qdrant/Neo4j containers are running.
- Boundaries: durable repository wrappers, P1.5.2 broader telemetry builders, social source candidate mapping, and evidence bundle export remain separate/deferred lanes unless explicitly re-scoped.
- Exact briefs for code-worker, validator, and tester/task-update agents are recorded in `project_generalize_tracker.md` and `project_generalize_handoff.md`.
- Status: ready for bounded test-first inventory/parity review; not validated.
- Finished: false.
- Focused dirty-change pytest baseline passed: `63 passed in 4.91s` for connection settings, social-source candidates, evidence-bundle export, backend health/adapters, broader repository save parity, and repository hook parity. This is not lane validation yet.

2026-06-04 main-thread wrap-up:

- Live goal/context signal was checked again after OA1 completed and before starting worker/validator/tester agents.
- Latest goal usage counter reported `289495` tokens used, with no remaining-token ceiling or direct context-window percentage exposed.
- Decision: do not start additional agents and do not edit production code or tests in this chat. Continue only by updating tracker/status/handoff files.
- Superseded note: at this point P5.3 was still pending and the next work was expected to start from the recorded code-worker, validator, and tester/task-update briefs.
- Finished: false.

2026-06-04 automatic continuation wrap-up:

- Live goal/context signal was checked again in the automatic continuation.
- Latest goal usage counter reported `422752` tokens used, with no remaining-token ceiling or direct context-window percentage exposed.
- Decision remains unchanged: do not start additional agents and do not edit production code or tests in this same chat. Continue only by updating tracker/status/handoff files.
- `git status --short --branch` still shows dirty implementation, test, tracker, and handoff changes; do not revert unrelated edits.
- Superseded note: at this point P5.3 was still pending and the fresh-context next step was the recorded P5.3 worker/validator/tester loop.
- Finished: false.

2026-06-04 repeated threshold blocker:

- Live goal/context signal was checked again in the next automatic continuation.
- Latest goal usage counter reported `491480` tokens used, with no remaining-token ceiling or direct context-window percentage exposed.
- This is the third consecutive same-thread continuation of the same context-threshold condition after OA1, so the active thread goal is blocked for additional agent-based implementation here.
- `git status --short --branch` still shows dirty implementation, test, tracker, and handoff changes; do not revert unrelated edits.
- Superseded note: at this point P5.3 was still pending; the later 2026-06-04 implementation continuation finished and validated it.
- Goal-tool result: active thread goal marked `blocked`; final usage returned `520831` tokens used.
- Finished: false.

Context rule added:

- Before starting any new agent, check current goal/context usage.
- If usage exceeds 50%, do not start another agent.
- Wrap up the project files, update tracker status and finished flags, and write a handoff summary for a new chat.
- Historical prior-chat status exceeded the threshold; the 2026-06-03 run proceeded after a fresh context check, but the 2026-06-04 main thread now stops additional agent spawning after goal usage reached `289495`, `422752`, and `491480` tokens across repeated same-thread continuations, then marked the active thread goal blocked with final goal-tool usage `520831`.

Current handoff file:

- `project_generalize_handoff.md`

Blocked handoff status:

- Historical observed goal usage: `1082685` tokens in a prior chat.
- The same over-threshold condition had repeated across prior goal continuations.
- The 2026-06-03 fresh run proceeded under the under-threshold branch because live goal tooling reported no active budget object.
- The 2026-06-04 main thread is now blocked for additional agents because the repeated threshold condition has completed the blocked audit; continue from a fresh context before starting future agents.

Validated through:

- `P5.3 backend service/env defaults inventory/parity`
- `P1.4.2 broader repository save/orchestration hook extraction`
- Focused P5.3 pytest: 30 passed.
- Backend-adjacent phase pytest: 70 passed.
- Standard-library unittest discovery: 141 passed.
- Full pytest: 307 passed.
- Lenient health and short keyword smoke passed.
- Strict service health skipped because the Docker daemon/API pipe is unavailable.
- Focused feedback/evaluation parity pytest: 36 passed.
- Broader phase-adjacent pytest: 112 passed.
- Standard-library unittest discovery: 139 passed.
- Full pytest: 304 passed.
- Lenient health and short keyword smoke passed.

Next lane:

- Select the next production optimization lane after validated P5.3.
- `P1.5.2 additional telemetry builders` remains deferred until more telemetry golden coverage exists.
- Durable storage wrappers remain deferred until separate persistence golden tests exist; feedback/evaluation domain save helper extraction is validated for the narrow P1.4.2 broader-hook scope.

Current validation spot-check:

- Date: 2026-06-03.
- Focused feedback/evaluation parity pytest passed: 36 passed.
- Broader phase-adjacent pytest passed: 112 passed.
- Full pytest with tracker-documented repo-local temp settings passed: 304 passed.
- Standard-library unittest discovery passed: 139 tests, OK.
- Lenient health passed and short keyword smoke passed with one keyword candidate, keyword execution mode, one citation, 20 logs, and an answer.
- Strict backend health was skipped because Qdrant and Neo4j containers are present but exited with code `255`.
- `scripts\test_full_backend.ps1 -StrictServices` failed in this checkout because it hardcodes `.\.venv\Scripts\python.exe`, while the current validation environment uses the discovered sibling venv at `C:\Users\fredo\git_repos\MARACA\MARACA-1\.venv\Scripts\python.exe`.

Production optimization request capture:

- Date: 2026-06-02.
- User requested production optimization with orchestration, code-worker, validation, and testing/task-update agents, continuous tracker/status updates, full process testing if finished, and a same-prompt takeover summary.
- The persisted project handoff/tracker state still marks this chat as over the 50% context threshold, so no new agents were spawned and no production code changes were started in this chat.
- `project_generalize_handoff.md` now contains the latest exact controlling prompt and a fresh-chat production-optimization takeover prompt.
- Superseded next-lane note: P1.4.2 inventory/parity tests and narrow repository hook extraction are now validated. Next fresh-chat work is lane selection after P1.4.2.

Current turn wrap-up:

- Date: 2026-06-02.
- Re-read `current_process_status.md`, `project_generalize_tracker.md`, `project_generalize_handoff.md`, `pyproject.toml`, `README.md`, and git status before taking action.
- Goal tooling reported no active goal budget in this thread, but persisted project status still records the same chat as over the 50% agent-start threshold and blocked for additional agent-based implementation.
- Decision: do not start orchestration, code-worker, validation, or testing/task-update agents in this chat; preserve the user prompt for a fresh chat instead.
- Status remains in progress and `Finished: false`; no production optimization code was started or completed in this turn.

Fresh delegation start:

- Date: 2026-06-02.
- Re-read the required handoff, tracker, status, test-plan, summary, and README files plus git status before starting new work.
- Live goal tooling for this delegated run reported no active goal budget object and no over-threshold usage; this run is treated as a fresh under-threshold context.
- Decision: begin P1.4.2 using the requested orchestration split, with inventory/parity tests only before any production hook extraction.
- Status remains in progress and `Finished: false`.

P1.4.2 inventory/parity progress:

- Date: 2026-06-02.
- Read-only orchestration inventory confirmed the current mixed strict/permissive repository-hook contract.
- Added test-only parity coverage for ranking, synthesis, validation, planning, and orchestration runtime repository hook behavior.
- Focused pytest for the touched P1.4.2 modules passed with `41 passed in 0.30s`.
- Phase-adjacent pytest including shared repository hooks, feedback/evaluation, evaluation metrics, and telemetry golden coverage passed with `71 passed in 0.30s`.
- No production hook extraction has been started.

P1.4.2 validation repair and final gates:

- Date: 2026-06-02.
- Initial independent validation found parity coverage gaps in the four target files.
- Repaired the tests to lock validation hook failure propagation, orchestration no-fallback return shape, and paired error/log detail separation.
- Final focused pytest passed: `41 passed in 0.23s`.
- Final expanded phase-adjacent pytest passed: `147 passed in 0.49s`.
- Final unittest discovery passed: `Ran 129 tests in 0.390s`, `OK`.
- Final full pytest passed: `268 passed in 2.85s`.
- Targeted validator repair review passed with no blocking findings; residual risk is intentionally order-sensitive telemetry assertions.
- Superseded by the later P1.4.2 narrow extraction validation entry below: the inventory/parity-test slice was implemented, validator-signed, and regressed before production extraction began.
- `project_generalize_handoff.md` was refreshed with this fresh delegation progress and the same next boundary.

Fresh continuation for P1.4.2 production extraction:

- Date: 2026-06-02.
- Live goal tooling reported no active budget object and no over-threshold usage.
- Re-read the required handoff, tracker, generalization, summary, test-plan, status, README files, and git status before editing.
- Decision: proceed with orchestration agents and begin only narrow production extraction backed by the signed P1.4.2 parity tests.
- Boundary: do not touch durable save/snapshot/JSON/JSONL persistence behavior in this extraction.
- Status remains in progress and `Finished: false`.

P1.4.2 narrow production extraction progress:

- Date: 2026-06-02.
- Wired ranking, synthesis, validation, planning, and orchestration runtime repository hook paths through `shared.repository_hooks`.
- Preserved strict ranking/synthesis/planning behavior with `required=True` and permissive validation/orchestration behavior with default helper calls.
- Durable storage save/snapshot/JSON/JSONL files were not edited.
- Focused P1.4.2 pytest passed with `59 passed in 0.32s`.
- Expanded phase-adjacent pytest passed with `147 passed in 0.43s`.
- Standard-library unittest discovery passed with `Ran 129 tests in 0.410s`, `OK`.
- Full pytest passed with `268 passed in 3.25s`.
- Superseded by the validation entry below: final test gates were complete at this point, and the current production-extraction validator signoff arrived afterward.

P1.4.2 narrow extraction validated:

- Date: 2026-06-02.
- Independent validator passed the production extraction with no blocking behavior findings.
- Corrected stale tracker wording that still said production extraction had not started.
- Validated production scope: ranking, synthesis, validation, planning, and orchestration runtime repository hook wiring through `shared.repository_hooks`.
- Deferred scope: feedback/evaluation domain save helpers and durable storage save/snapshot/JSON/JSONL wrappers.
- Status: validated for the completed narrow P1.4.2 extraction scope.
- Finished: true for the completed narrow extraction scope.

Production optimization restart:

- Date: 2026-06-03.
- Live goal/context tooling was checked first and reported no active goal budget object or over-threshold usage in this fresh run.
- Re-read the required handoff, tracker, plan, summary, status, test-plan, README files, and git status before editing.
- Dirty worktree changes are present in source and tests; continue without reverting edits made by others.
- Current lane is P1.4.2 broader repository save and orchestration hooks, beginning with inventory/parity tests only.
- Do not extract production hooks until strict/permissive behavior, telemetry payloads, return shapes, failure propagation, and durable persistence side effects are locked.
- Status remains in progress and `Finished: false`.

Broader hook inventory started:

- Date: 2026-06-03.
- Searched repository save/log/error/orchestration hook surfaces in planning, orchestration runtime, feedback, evaluation, storage, ranking, validation, synthesis, and tests.
- Narrow P1.4.2 behavior is already covered by repository-hook parity and module-focused tests.
- Broader remaining surface is feedback/evaluation domain save helpers plus durable storage snapshot and JSONL side effects.
- Orchestration, code-worker, validation, and testing/task-update agents were started because the fresh live context check did not report over-threshold usage.
- Current action remains test-only inventory/parity coverage; no broader production hook extraction is validated or started.

Orchestration brief received:

- Date: 2026-06-03.
- Recommended test-only scope is feedback/evaluation domain saves, durable JSON snapshot and JSONL persistence side effects, and preservation of existing planning/orchestration hook parity.
- Backend health/runtime adapter dirty changes are treated as separate existing work and not part of this lane.
- Production extraction remains blocked until the broader parity/golden tests pass and validator review signs off.

Validation findings for broader hook inventory:

- Date: 2026-06-03.
- Validator agreed with the test-first lane and found production extraction still blocked.
- Missing parity coverage includes feedback/evaluation domain save helper matrices, durable JSON snapshot/JSONL shape and rollback side effects, and orchestration hook failure-propagation cases.
- Existing dirty backend health/runtime, connection settings, social-source mapping, and evidence-bundle export changes remain unrelated to the P1.4.2 broader hook lane.

Testing baseline:

- Date: 2026-06-03.
- Focused dirty-change pytest passed with `40 passed in 6.30s`.
- P1.4.2 repository/orchestration hook parity pytest passed with `70 passed in 0.51s`.
- Backend-adjacent durable/support pytest passed with `39 passed in 4.75s`.
- Full pytest passed with `291 passed in 4.77s`.
- Standard-library unittest discovery passed with `Ran 139 tests in 0.469s`, `OK`.
- Lenient `rag-center-health --env-file .env.example` passed and `rag-center-smoke` passed with one keyword candidate, keyword execution mode, one citation, and 20 logs.
- Strict service health was skipped because Qdrant and Neo4j containers are present but exited.
- This is a validation baseline only; broader P1.4.2 production extraction remains unstarted and blocked on missing parity/golden tests.

Broader parity tests added:

- Date: 2026-06-03.
- Added `tests/test_broader_repository_save_parity.py` as a test-only broader repository save parity slice.
- Added orchestration failure-propagation and partial-hook return-shape parity to `tests/test_repository_hook_parity.py`.
- Focused parity pytest passed with `19 passed in 0.24s`.
- Expanded adjacent pytest passed with `65 passed in 0.68s`.
- Full pytest passed with `300 passed in 4.95s`.
- Standard-library unittest discovery passed with `Ran 139 tests in 0.620s`, `OK`.
- No production hook extraction was started; the test-only slice is implemented but not yet validated.

Post-patch validation result:

- Date: 2026-06-03.
- Validator confirmed the orchestration parity gaps are addressed.
- Production extraction remains blocked because feedback/evaluation domain-save helper matrices and broader durable side-effect parity are still incomplete.
- Continue with additional test-only coverage for improvement tasks, evaluation cases/reports, observability reports, and durable JSONL/error/no-extra-write behavior before any production hook extraction.

Broader domain save parity expanded:

- Date: 2026-06-03.
- Extended `tests/test_broader_repository_save_parity.py` with present-hook saves, failing domain-save telemetry, and durable JSONL side effects for improvement tasks, evaluation cases/reports, and observability reports.
- Focused broader save parity pytest passed with `9 passed in 0.24s`.
- Expanded adjacent pytest passed with `69 passed in 0.61s`.
- Full pytest passed with `304 passed in 4.00s`.
- Standard-library unittest discovery passed with `Ran 139 tests in 0.359s`, `OK`.
- No production hook extraction was started; expanded test-only parity is implemented and pending validator review.

Expanded parity slice validated:

- Date: 2026-06-03.
- Validator found no blocking findings for the expanded test-only P1.4.2 broader repository save/orchestration-hook inventory.
- Validated locked scope includes feedback/evaluation domain-save helper behavior, orchestration hook behavior, retryable telemetry return shapes, and durable JSONL/memory-only side effects for covered domain-save flows.
- Residual non-blocking precision gap: a dedicated durable `save_evaluation_case` failure path is not directly exercised, but public `evaluate_batch` failure shape and durable `errors.jsonl` behavior are pinned.
- Test gates for the test-only slice passed: focused broader parity `9 passed`, expanded adjacent `69 passed`, full pytest `304 passed`, and unittest discovery `139 passed`.

Narrow broader-hook production extraction started:

- Date: 2026-06-03.
- Production extraction may now begin for feedback/evaluation deferred domain save helpers through `shared.repository_hooks.call_repository_hook`.
- Durable wrappers, backend health/runtime adapter dirty changes, connection settings, social-source mapping, evidence-bundle export, and broad telemetry builders remain out of scope.
- Status remains in progress and `Finished: false`.

Narrow broader-hook production extraction implemented:

- Date: 2026-06-03.
- Wired feedback/evaluation deferred domain save helpers through `shared.repository_hooks.call_repository_hook`.
- Production files touched: `src/feedback/__init__.py` and `src/evaluation/__init__.py`.
- Durable storage save/snapshot/JSON/JSONL wrappers were not touched.
- Focused feedback/evaluation parity pytest passed with `36 passed in 0.55s`.
- Broader phase-adjacent pytest passed with `112 passed in 1.02s`.
- Full pytest passed with `304 passed in 5.12s`.
- Standard-library unittest discovery passed with `Ran 139 tests in 0.607s`, `OK`.
- Lenient `rag-center-health --env-file .env.example` passed and `rag-center-smoke` passed with one keyword candidate, keyword execution mode, one citation, and 20 logs.
- Strict service health was not run because Qdrant and Neo4j containers are present but exited with code `255`.
- Status is implemented and pending validator review.

Narrow broader-hook production extraction validated:

- Date: 2026-06-03.
- Validator found no blocking findings.
- Validated production scope: feedback/evaluation deferred domain save helpers now route through `shared.repository_hooks.call_repository_hook`.
- Validated behavior: permissive missing-hook behavior, callable hook failure propagation, telemetry return shapes, durable JSONL/memory-only side effects, and orchestration hook failure/partial-hook return shapes.
- Residual non-blocking note: non-callable hook attributes such as `None` are treated as absent by `call_repository_hook`, consistent with the prior optional-hook contract.
- Final gates passed: focused feedback/evaluation parity `36 passed`, broader phase-adjacent `112 passed`, full pytest `304 passed`, unittest discovery `139 passed`, lenient health, and smoke.
- Strict service health was skipped because Qdrant and Neo4j containers are present but exited.
- Status: validated for the narrow broader-hook production extraction scope.
- Finished: true for the completed narrow broader-hook production extraction scope.

Date: 2026-05-29
Workspace: `C:\Users\Fred_U\Documents\MA-RAG-CAG-Graph`

## Active Agent Workflow Tracker

Date: 2026-05-31
Workspace: `C:\Users\fredo\git_repos\MARACA\maraca_V02`
Model policy: use GPT-5.5 medium for newly spawned agents.

### Current Workflow

Status: validating.
Finished: false.

Goal:

- Read existing files.
- Use an outline agent to summarize the project.
- Use an adversarial agent to review risks.
- Use a planning agent to write the final process and plan.
- Use a worker agent for implementation.
- Use a validator agent to check the implementation.
- Track testing and finished state explicitly.

Agent results:

- Outline agent: complete. Confirmed MARACA v02 is complete through Milestone 13 and current next work is productionization, generalization, and repair-loop traceability.
- Adversarial review agent: complete. Highest risks are Neo4j real-service parity, Qdrant collection bootstrap, env knob wiring, durable runtime state, and absolute ingestion paths.
- Process/plan agent: complete. Recommended tracker fields are status, risk level, owner, implementation scope, test gate, validator result, adversarial result, trace links, and finished flag.
- Implementation worker: complete. Added observable repair-loop execution trace state to planned-query results.
- Validator agent: complete. Static review passed with no blocking findings; Python/pytest execution remains blocked locally.

### Current Implementation Task

Task id: `repair-loop-trace-2026-05-31`
Status: validating.
Finished: false.
Owner: implementation worker, followed by validator agent.
Risk level: medium.

Scope:

- `src/planning/__init__.py`
- `tests/test_planner_orchestration.py`

Implemented:

- Added `RepairExecutionTrace`.
- Exposed optional `PlannedQueryResult.repair_trace`.
- Populates the trace when validation returns `REPAIR_NEEDED` or `FAIL`.
- Trace captures validation status, repair action, repair attempt bounds, previous actions, fallback actions, exhaustion state, and whether a retrieval rerun was triggered.
- Added focused planner orchestration tests for repair-needed and exhausted repair states.

Testing:

- `python -m pytest tests\test_planner_orchestration.py -q`: blocked because `python` resolves to the Windows Store shim and no interpreter is available.
- `python -m unittest tests.test_planner_orchestration`: blocked for the same reason.
- `.venv\Scripts\python.exe`: not present.
- `py`: not present.

Validator result: pass by static GPT-5.5-medium review.
Adversarial result: complete for project-level review, not yet re-run on this implementation.
Finished flag rule: keep `Finished: false` until implementation, reproducible tests, validator pass, and adversarial review pass are all complete.

### Next Recommended Productionization Tasks

1. Qdrant collection bootstrap hardening.
2. Neo4j real Cypher parity for graph indexing and traversal.
3. Wire documented `QDRANT_COLLECTION` and `NEO4J_DATABASE` env knobs through health/runtime adapters.
4. Decide which runtime state must survive durable restart.
5. Lock down absolute local ingestion paths before operator-facing source registration.

## Full Backend Install and Interface Tracker

Date: 2026-05-31
Status: planning.
Finished: false.
Audit agent: complete using GPT-5.5 medium.

### Existing Full Backend Surfaces

Package and install:

- `pyproject.toml` defines Python `>=3.11`, package extras, console scripts, pytest settings, and `src/` package discovery.
- Optional extras:
  - `backend`: `langgraph>=1.2.2`, `llama-index-core>=0.14.22`, `neo4j>=6.2.0`, `qdrant-client>=1.18.0`.
  - `test`: `pytest>=8`.
  - `full`: backend extras plus pytest.

Runtime services:

- `docker-compose.yml` defines Qdrant `qdrant/qdrant:v1.18.0` on ports `6333` and `6334`.
- `docker-compose.yml` defines Neo4j `neo4j:5.26-community` on ports `7474` and `7687`, with APOC enabled.
- `.env.example` defines `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `RAG_STORAGE_ROOT`, and `RAG_MODEL_PROFILE`.

Backend interfaces:

- `src/backend_app/health.py`: `rag-center-health` CLI for optional imports, env checks, Docker checks, Qdrant, Neo4j, and LangGraph-compatible runtime health.
- `src/backend_app/manual.py`: `rag-center-smoke` CLI for fixture-backed keyword/vector/planned-query smoke flow.
- `src/storage/adapters.py`: backend adapter contracts, health checks, operation results, registry, selection, and local backend registry.
- `src/storage/durable.py`: local JSON/JSONL durable repository baseline.
- `src/storage/vector_runtime.py`: in-memory executable vector backend adapter.
- `src/storage/qdrant_runtime.py`: Qdrant-compatible vector adapter with injected-client support.
- `src/storage/neo4j_runtime.py`: Neo4j-compatible graph adapter with injected-client support.
- `src/planning/orchestration_runtime.py`: LangGraph-compatible orchestration adapter and local planned-query fallback.
- `src/retrieval/indexing.py` and `src/retrieval/execution.py`: deterministic embedding, sparse indexing, keyword/vector/hybrid/graph retrieval, access filtering, and merge execution.

Setup and test scripts:

- `scripts/setup_full_backend.ps1`: creates `.venv`, installs `.[full]`, copies `.env`, optionally installs Docker Desktop, optionally starts services, then runs health and smoke checks.
- `scripts/test_full_backend.ps1`: runs `pip check`, health, optional strict service health, smoke, unittest discovery, and pytest.

Current local machine probe:

- `.env`: present.
- `.env.example`: present.
- `.venv\Scripts\python.exe`: missing.
- `python`: present only as Windows Store shim, not a usable interpreter.
- `py`: missing.
- Docker CLI: present.
- `docker compose ps`: no Qdrant or Neo4j services currently running.

Exact installed stack probe:

- Current checkout `C:\Users\fredo\git_repos\MARACA\maraca_V02` does not have a local `.venv`.
- Sibling checkout `C:\Users\fredo\git_repos\MARACA\MARACA-1` has an existing `.venv`.
- Existing usable interpreter found: `C:\Users\fredo\git_repos\MARACA\MARACA-1\.venv\Scripts\python.exe`.
- Interpreter version: Python `3.12.13`.
- Pip version in that venv: `25.0.1`.
- Editable package installed in that venv:
  - `agent-orchestrated-hybrid-retrieval-center==0.1.0`
  - Editable project location: `C:\Users\fredo\git_repos\MARACA\MARACA-1`
- Full backend Python packages installed in that venv:
  - `qdrant-client==1.18.0`
  - `neo4j==6.2.0`
  - `langgraph==1.2.2`
  - `llama-index-core==0.14.22`
  - `pytest==9.0.3`
  - `setuptools==82.0.1`
- Console scripts found in that venv:
  - `C:\Users\fredo\git_repos\MARACA\MARACA-1\.venv\Scripts\rag-center-health.exe`
  - `C:\Users\fredo\git_repos\MARACA\MARACA-1\.venv\Scripts\rag-center-smoke.exe`
- Codex bundled Python exists at `C:\Users\fredo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`, version Python `3.12.13`, but it does not have `qdrant-client`, `neo4j`, `langgraph`, `llama-index-core`, or `pytest`.
- `pip check` in the sibling `MARACA-1` venv reports: no broken requirements found.

Exact Docker stack probe:

- Docker CLI installed: Docker `29.5.2`.
- Docker Compose installed: `v5.1.3`.
- Required images present locally:
  - `qdrant/qdrant:v1.18.0`
  - `neo4j:5.26-community`
- Related extra images also present locally:
  - `qdrant/qdrant:v1.15.4`
  - `qdrant/qdrant:v1.12.5`
  - `postgres:16-alpine`
  - `redis:7-alpine`
  - `minio/minio:RELEASE.2025-01-20T14-49-07Z`
  - `openpolicyagent/opa:0.70.0`
- MARACA containers found:
  - `rag-center-qdrant`, image `qdrant/qdrant:v1.18.0`, status `exited`, exit code `255`, finished `2026-05-30T23:48:00Z`.
  - `rag-center-neo4j`, image `neo4j:5.26-community`, status `exited`, exit code `255`, finished `2026-05-30T23:48:00Z`.
- MARACA Docker volumes found:
  - `maraca-1_qdrant_data`
  - `maraca-1_neo4j_data`
  - `maraca-1_neo4j_logs`
- Qdrant logs show collection `evidence_chunks` was previously loaded and reachable while the container was running.
- Neo4j logs show Neo4j `5.26.26` previously started with Bolt on `7687` and HTTP on `7474`.
- Current service state: Qdrant and Neo4j are installed as images/containers/volumes but are not running.

Validation using found stack without installing software:

- Command style: used `MARACA-1\.venv\Scripts\python.exe` with `PYTHONPATH` pointed at `maraca_V02\src` and `PYTHONDONTWRITEBYTECODE=1`.
- Lenient health check: passed optional imports, Docker availability, env checks, and LangGraph-compatible runtime; Qdrant/Neo4j strict service checks were not run in lenient mode.
- Strict health check: failed only because Qdrant and Neo4j services are not running on `localhost:6333` and `localhost:7687`.
- Smoke check: passed against the `maraca_V02` source path with one keyword candidate, keyword execution mode, one citation, and an answer.
- No software was installed during this probe.

Service start result:

- Date: 2026-06-01.
- Goal: start all necessary backend services.
- Necessary services from `docker-compose.yml`: `qdrant`, `neo4j`.
- Initial `docker compose up -d qdrant neo4j` from `maraca_V02` created the `maraca_v02_default` network and new empty `maraca_v02_*` volumes, then stopped on container-name conflict because `rag-center-qdrant` and `rag-center-neo4j` already existed.
- No containers or volumes were removed.
- Existing containers started instead:
  - `rag-center-qdrant`
  - `rag-center-neo4j`
- Running containers:
  - `rag-center-qdrant`, image `qdrant/qdrant:v1.18.0`, ports `6333` and `6334`.
  - `rag-center-neo4j`, image `neo4j:5.26-community`, ports `7474` and `7687`.
- Port checks passed:
  - `localhost:6333`
  - `localhost:7474`
  - `localhost:7687`
- Qdrant collection check passed:
  - Collection: `evidence_chunks`
  - Status: `green`
  - Vector size: `32`
  - Distance: `Cosine`
- Strict backend health passed using `MARACA-1\.venv\Scripts\python.exe` with `PYTHONPATH` pointed at `maraca_V02\src`:
  - `qdrant-client`: installed.
  - `neo4j`: installed.
  - `langgraph`: installed.
  - `llama-index-core`: installed.
  - Docker Compose: available.
  - Qdrant service: ready.
  - Neo4j service: ready.
  - LangGraph-compatible runtime: ready.
- Finished: true for service startup and strict health verification.

Service conflict fix:

- Date: 2026-06-01.
- Conflict found: plain `docker compose` from `maraca_V02` originally used project name `maraca_v02`, while the existing fixed-name service containers were labeled for project `maraca-1`.
- Fix applied: added `COMPOSE_PROJECT_NAME=maraca-1` to the local ignored `.env` file.
- Result: plain `docker compose ps --all` from `maraca_V02` now shows the existing running `rag-center-qdrant` and `rag-center-neo4j` containers.
- Cleanup: removed unattached failed-start resources created during the earlier conflict:
  - `maraca_v02_qdrant_data`
  - `maraca_v02_neo4j_data`
  - `maraca_v02_neo4j_logs`
  - `maraca_v02_default`
- Remaining MARACA Docker resources:
  - Network: `maraca-1_default`
  - Volumes: `maraca-1_qdrant_data`, `maraca-1_neo4j_data`, `maraca-1_neo4j_logs`
- Verification after fix:
  - `docker compose up -d qdrant neo4j`: reports both containers running.
  - `localhost:6333`: reachable.
  - `localhost:7474`: reachable.
  - `localhost:7687`: reachable.
  - Strict backend health: all checks OK.
- Finished: true for service conflict resolution.

### Missing or Partial Full Backend Parts

Install/runtime blockers:

- A usable Python `>=3.11` interpreter is missing from the current shell.
- `.venv` is missing, so package extras and console scripts are not installed in this checkout.
- Qdrant and Neo4j containers are not running.

Service integration gaps:

- `QDRANT_COLLECTION` is documented but not wired through the health CLI or default adapter construction.
- Qdrant adapter does not currently bootstrap or validate a fresh collection before health/index operations.
- `NEO4J_DATABASE` is documented but not wired through the health CLI or default adapter construction.
- Neo4j graph adapter writes skeletal graph nodes and does not yet create the full properties/relationships expected by traversal.
- LangGraph is checked as an optional dependency, but the health path uses `LocalPlannedQueryGraphApp`; no production graph workflow is wired yet.
- LlamaIndex is declared and checked, but not materially integrated into ingestion/indexing.
- Production metadata, raw object store, telemetry store, model service, and external embedding service remain deferred or local-only.

### Installation Plan

Status: todo.
Finished: false.

1. Install or expose Python `>=3.11` in the shell.
   - Interface: `python`, `py`, or explicit interpreter path.
   - Test gate: `python --version` or explicit interpreter `--version` returns `>=3.11`.

2. Create the virtual environment.
   - Command: `py -m venv .venv` or equivalent explicit Python command.
   - Interface: `.venv\Scripts\python.exe`.
   - Test gate: `.venv\Scripts\python.exe --version`.

3. Install full backend extras.
   - Command: `.venv\Scripts\python.exe -m pip install -e ".[full]"`.
   - Interfaces: `qdrant_client`, `neo4j`, `langgraph`, `llama_index.core`, `pytest`.
   - Test gate: `.venv\Scripts\python.exe -m pip check`.

4. Confirm environment file.
   - Command: `Copy-Item .env.example .env` if `.env` is absent.
   - Interfaces: Qdrant, Neo4j, storage root, model profile env vars.
   - Test gate: `.venv\Scripts\rag-center-health.exe --env-file .env`.

5. Start service containers.
   - Command: `docker compose up -d qdrant neo4j`.
   - Interfaces: Qdrant HTTP/gRPC ports, Neo4j browser/Bolt ports.
   - Test gate: `docker compose ps` shows both services running.

6. Add or run Qdrant collection bootstrap.
   - Interface: `QDRANT_COLLECTION`, vector size `32`, distance metric chosen by adapter policy.
   - Test gate: strict Qdrant health succeeds from an empty Docker volume and succeeds again idempotently.

7. Harden Neo4j graph persistence before calling it production-ready.
   - Interface: graph entity, relation, chunk payloads, Cypher upsert, traversal result hydration.
   - Test gate: real-service graph index and traversal smoke test returns governed candidates with chunk/source/document/access metadata.

8. Run full validation.
   - Commands:
     - `.venv\Scripts\rag-center-health.exe --strict-services --env-file .env`
     - `.venv\Scripts\rag-center-smoke.exe`
     - `.venv\Scripts\python.exe -m unittest discover -s tests`
     - `.venv\Scripts\python.exe -m pytest`
     - `PowerShell -ExecutionPolicy Bypass -File scripts\test_full_backend.ps1 -StrictServices`
   - Finished flag: true only after all gates pass on the same environment.

### Interface Test Matrix

- Package install: `pip check`, optional import checks, console script existence.
- Health CLI: lenient health before services, strict health after services.
- Smoke CLI: keyword candidate count, executed mode, citation count, answer text, log count.
- Qdrant adapter: health, collection bootstrap, index chunks, search, no text leakage, incompatible collection failure.
- Neo4j adapter: health, graph index, traversal, access metadata preservation, no text leakage, write failure envelope.
- LangGraph-compatible runtime: local fallback, injected app execution, app failure fallback, disabled fallback unavailable state.
- Durable/local storage: JSON/JSONL round trip, rollback, telemetry append, governance field preservation.
- End-to-end backend: fixture ingest, chunk, storage commit, vector/sparse commit, retrieval, ranking, validation, synthesis.

### Tracker Fields for Full Backend Work

- `task_id`
- `status`: `todo`, `in_progress`, `blocked`, `validating`, `done`
- `finished`: `false` or `true`
- `owner`
- `interface`
- `install_or_code_scope`
- `dependencies`
- `test_gate`
- `latest_result`
- `validator_result`
- `adversarial_result`
- `notes`

## Current Goal

Implement the project according to the milestone plan, using a worker/validator pair for each part and one repair loop when the validator finds actionable suggestions.

The current implementation loop has completed Milestone 13: LangGraph-compatible orchestration runtime boundary.

## Finished Work

### Project Read-Through

The project planning and research files were read and used as the implementation source of truth:

- `project_milestones.md`
- `project_tests.md`
- `research/method_detail_AgentOrchHybrid.md`
- `research/method_flow_AgentOrchHybrid.mmd`
- `research/skill_AgentOrchHybrid.md`
- `research/project_summary_outline_AgentOrchHybrid.md`
- `research/proposals.md`
- `research/top_10_methods.md`
- `research/papers_database.csv`
- `research/papers_database.sqlite`

The SQLite database was inspected and contains one `papers` table with 21 rows and fields matching the CSV research database.

### Recent Repository Updates

Status: complete.

Latest local commits:

- `45690cc` Move research artifacts into research folder.
- `40c733f` Complete milestone 4 validation support.
- `4668d74` Implement milestone 3 graph layer.

Repository organization update:

- Research artifacts now live under `research/`.
- `pyproject.toml` now uses `research/project_summary_outline_AgentOrchHybrid.md` as the package readme.
- Root-level references to moved research files were updated in the status and baseline docs.

### Milestone 0: Project Foundation

Status: complete.

Implemented:

- Python project baseline with `pyproject.toml`.
- Source package layout under `src/` for:
  - `source_registry`
  - `ingestion`
  - `enrichment`
  - `storage`
  - `planning`
  - `retrieval`
  - `ranking`
  - `validation`
  - `synthesis`
  - `feedback`
  - `evaluation`
  - `shared`
- Shared core contracts in `src/shared/contracts.py`:
  - `Partition`
  - `ErrorEnvelope`
  - `LogEvent`
  - `new_correlation_id`
  - error/log enums and serialization helpers
- Shared core records in `src/shared/records.py`:
  - source, ingestion, document, chunk, entity, relation, retrieval request, retrieval plan, evidence, ranked evidence, validation, claim, answer, and feedback records
- Shared policy defaults in `src/shared/policies.py`:
  - fallback actions by partition
  - successful ingestion/query log expectations
  - degraded vector/sparse alternatives
  - required error-type coverage
  - helper constructors for log/error records
- Static environment profiles in `src/shared/environment.py`:
  - local
  - test
  - staging
  - production
- Declarative stack selections in `src/shared/stack.py`:
  - LlamaIndex
  - Neo4j
  - Qdrant
  - LangGraph
  - metadata store
  - raw source store
  - model services
  - dependency-free fallback mocks
- Fixture catalog and synthetic source fixtures under `fixtures/`:
  - public document
  - external web page
  - internal CSV table
  - API-like JSON
  - restricted source
  - stale source
  - malformed source
  - conflict pair
  - graph relationship fixture
- Fixture loader and validator in `src/shared/fixtures.py`.
- Foundation documentation in `docs/development_baseline.md`.
- Tests for package layout, shared contracts, shared records, policies, environment profiles, stack selections, and fixtures.

Validator repairs completed:

- Added optional `pytest` test extra.
- Tightened package layout tests to require exact partition names.
- Added first-class `ClaimRecord`.
- Split optional feedback logs from always-required query logs.
- Added degraded vector/sparse log alternatives.
- Aligned environment serialization with shared serializer.
- Added staging behavior assertions.
- Added path traversal protection for fixtures.
- Added explicit internal fixture coverage.
- Added `SourceType.TABLE` so the catalog and shared enum are consistent.

### Milestone 1 Part 1: Source Registry and Access Policy

Status: complete.

Implemented in:

- `src/source_registry/registry.py`
- `src/source_registry/__init__.py`
- `tests/test_source_registry.py`

Implemented:

- In-memory source repository.
- `SourceRegistry`.
- Source registration preserving:
  - `external_link`
  - access metadata
  - license policy
  - reliability fields
  - freshness fields
  - status
- Source status updates.
- Access checks for public, internal, restricted, and confidential sources.
- Fail-closed behavior for missing access metadata.
- License/status/source policy decisions.
- Structured log/error output with shared `LogEvent` and `ErrorEnvelope`.

Validator repairs completed:

- Missing `access_policy_id` now resolves to unknown and fails closed.
- Internal access now requires `internal` scope or allow-list membership.

### Milestone 1 Part 2: Ingestion Jobs and Raw Source Loading

Status: complete.

Implemented in:

- `src/ingestion/__init__.py`
- `tests/test_ingestion.py`

Implemented:

- In-memory ingestion job repository.
- Correlated `start_ingestion_job`.
- `RawArtifact`.
- Safe raw fixture/local source loading.
- Lightweight normalization for:
  - Markdown
  - HTML
  - JSON
  - CSV
- `DocumentRecord` creation with inherited:
  - access policy
  - access level
  - canonical link
  - owner
  - checksum
  - freshness date
- `run_ingestion_job` orchestration.
- Retry logging and error envelopes.
- Completed, failed, and partial ingestion statuses.

Validator repairs completed:

- ISO datetime date extraction now handles values like `2026-05-20T09:00:00Z`.
- Added retry-exhaustion coverage.
- Added successful HTML, JSON, and CSV normalization coverage.
- Removed pytest-only temp-path usage from ingestion tests.

### Milestone 1 Part 3: Document/Chunk Records and Storage Baseline

Status: complete.

Implemented in:

- `src/ingestion/__init__.py`
- `src/storage/__init__.py`
- `tests/test_chunking_storage.py`

Implemented:

- Deterministic `split_document_into_chunks`.
- Stable `ChunkRecord` IDs.
- Chunk text offsets.
- Heading path metadata.
- Token counts.
- Page metadata where available.
- Access metadata inheritance.
- In-memory storage repository for:
  - raw artifacts
  - sources
  - documents
  - chunks
  - vector embeddings
  - sparse terms
  - ingestion jobs
  - logs
  - errors
- Commit helpers for raw artifacts, documents, chunks, and ingestion metadata.
- Storage verification.
- Access metadata verification.

Validator repairs completed:

- Chunk IDs no longer depend on generated `document_id`; equivalent fresh document records now produce stable chunk IDs.
- Storage verification now reports missing raw artifacts.
- Chunk/storage tests were converted to `unittest.TestCase`.

### Milestone 1 Part 4: Vector and Keyword Indexing

Status: complete.

Implemented in:

- `src/retrieval/indexing.py`
- `src/retrieval/__init__.py`
- `src/storage/__init__.py`
- `tests/test_indexing.py`

Implemented:

- Deterministic hashed bag-of-terms embedding records.
- Sparse keyword/phrase extraction.
- Exact identifier preservation.
- Phrase n-gram indexing.
- In-memory vector index.
- In-memory keyword index.
- Vector commit helper.
- Sparse index commit helper.
- Vector search returning scored chunk candidates.
- Keyword search returning exact candidates.
- Degraded behavior for empty chunks.

Validator repairs completed:

- `commit_vectors` and `commit_sparse_index` now preserve the other existing chunk index pointer.
- Added regression coverage for vector-then-sparse and sparse-then-vector commit order.
- Fixed the unquoted exact phrase test.
- Documented the `unittest` fallback command.

### Milestone 1 Part 5: Hybrid Retrieval, Access Filtering, and Merge

Status: complete.

Implemented in:

- `src/retrieval/execution.py`
- `src/retrieval/__init__.py`
- `tests/test_retrieval_execution.py`

Implemented:

- Vector retrieval hydration into `EvidenceCandidate`.
- Keyword retrieval hydration into `EvidenceCandidate`.
- Provenance metadata:
  - source ID
  - document ID
  - chunk ID
  - snippet
  - reliability
  - citation link
  - license constraints
  - access scope
- Access filtering before merge/ranking.
- Fail-closed behavior for missing source/document/chunk access metadata.
- Restricted/confidential/internal exclusion for unauthorized principals.
- Stricter document/chunk policy checks.
- Hybrid search orchestration.
- Score normalization by retrieval mode.
- Deduplication by source/chunk.
- Retrieval/access logs and access errors.

Validator repairs completed:

- Removed the hybrid multi-mode score bonus from merge so merge does not act as reranking.
- Added regression coverage proving lower-scored hybrid duplicates do not overtake stronger single-mode candidates.

### Milestone 1 Part 6: Basic Reranking

Status: complete.

Implemented in:

- `src/ranking/__init__.py`
- `tests/test_ranking.py`

Implemented:

- Dependency-free `select_ranked_evidence` ranking flow.
- Safe evidence deduplication by source/chunk, citation, or snippet fallback.
- Query relevance scoring with retrieval-score, source-reliability, and freshness modifiers.
- Configurable ranking weights.
- Source diversity selection with `max_per_source`.
- Optional external reranker integration.
- Fallback to normalized retrieval scores when the reranker fails.
- Ranking logs using the shared `LogEvent` conventions.
- Ranking errors using shared `ErrorEnvelope` conventions.

Validator repairs completed:

- Non-finite external reranker scores such as `NaN` are treated as `0.0`.
- Added regression coverage for invalid external reranker scores.

## Continued Finished Work

### Milestone 1 Part 7: Cited Synthesis

Status: complete.

Implemented in:

- `src/synthesis/__init__.py`
- `tests/test_synthesis.py`

Implemented:

- Dependency-free `generate_answer` synthesis flow.
- Answer generation only from approved `AccessDecision.ALLOWED` evidence.
- Claim record creation tied to supporting evidence IDs.
- Citation maps containing evidence IDs and citation links where available.
- Ranked evidence ordering support.
- Limitations for no evidence, no approved evidence, single evidence, missing links, stale evidence, low/unverified reliability, weak validation, and underspecified queries.
- Conservative uncertainty answer when cited evidence is insufficient.
- Synthesis logs for claim creation, citation attachment, and answer generation.
- Synthesis error envelope when no approved cited evidence is available.

Validator repairs completed:

- Public `create_claim_records` now skips denied/unapproved evidence when called directly.
- Citation attachment telemetry now emits a `citations_attached` log.

### Milestone 1 Part 8: Feedback Capture and Evaluation Trace Storage

Status: complete.

Implemented in:

- `src/feedback/__init__.py`
- `src/evaluation/__init__.py`
- `src/storage/__init__.py`
- `tests/test_feedback_evaluation.py`

Implemented:

- Append-only feedback capture.
- Feedback trace references for request, answer, claims, evidence, source, document, chunk, citation, and validation IDs.
- Failure category classification from rating, correction text, validation criteria, and evidence signals.
- Append-only evaluation trace records with feedback/failure references and scalar metrics.
- Shared-style feedback and evaluation logs.
- Retry-safe handling for feedback/evaluation write failures.
- In-memory storage persistence for feedback records, feedback trace references, and evaluation traces.
- Regression coverage proving feedback/evaluation do not automatically mutate source reliability or access policy.

Validator repairs completed:

- `InMemoryStorageRepository` now persists feedback records, feedback trace references, and evaluation traces instead of only receiving logs.
- Write failures preserve local feedback/trace records and emit retryable storage errors.

### Milestone 1 Final Validation and Smoke Flow

Status: complete.

Implemented in:

- `tests/test_milestone1_smoke.py`

Implemented:

- Run an end-to-end happy path:
  - register source
  - ingest source
  - chunk
  - store
  - index vector and keyword data
  - hybrid retrieval
  - rerank
  - synthesize cited answer
  - capture feedback
  - store evaluation trace
- Restricted source exclusion before ranking and synthesis.
- Malformed source partial/error path and failed extractor path.
- Logs across source registry, ingestion, storage, retrieval, ranking, synthesis, feedback, and evaluation partitions.
- Errors across source registry, ingestion, and retrieval partitions.

Validator repairs completed:

- Final smoke coverage now asserts access-approved ranking, ranked-to-synthesis evidence continuity, feedback trace references, claim IDs, citation links, and evaluation trace persistence.
- Restricted-source coverage now confirms restricted evidence is absent from retrieval, ranking, and synthesis.
- Removed stale status-file caveats for already completed reranking, synthesis, and feedback/evaluation behavior.

### Milestone 2 Part 1: Planner Baseline and Routing Plan Generation

Status: complete.

Implemented in:

- `src/planning/__init__.py`
- `tests/test_planning.py`

Implemented:

- Dependency-free planner request helper using existing `RetrievalRequest`.
- Query classification for exact, semantic, graph, multi-hop, fresh-data, high-risk, and mixed/uncertain queries.
- Conservative retrieval-mode selection:
  - exact to keyword
  - semantic to vector/hybrid
  - graph to graph/hybrid
  - uncertain to hybrid
  - direct/no-retrieval only for explicit or inline-content cases
- Retrieval budget generation for `top_k`, latency target, cost target, and bounded repair attempts.
- Shared `RetrievalPlan` creation with repair-loop fields and fallback actions.
- No-retrieval direct response decision metadata without answer synthesis.
- Planner trace records carrying plan reason, retrieval budget, selected modes, fallback actions, and repair bounds.
- Planner decision logs for:
  - `query_classified`
  - `retrieval_modes_selected`
  - `retrieval_budget_set`
  - `retrieval_plan_created`

Validator repairs completed:

- Source-backed queries beginning with greetings no longer route to `NO_RETRIEVAL`.
- Transform-style wording such as `Rewrite this policy from approved sources` no longer bypasses retrieval without inline content.
- Planner logs now include a `retrieval_plan_created` event carrying `plan_reason`.
- Planner trace now includes explicit repair-loop bounds.

### Milestone 2 Part 2: Planner-to-Retrieval Orchestration Smoke Flow

Status: complete.

Implemented in:

- `src/planning/__init__.py`
- `tests/test_planner_orchestration.py`

Implemented:

- `run_planned_query` orchestration helper connecting planner output to retrieval, ranking, and cited synthesis.
- Shared `PlannedQueryResult` carrying planning, retrieval, ranking, synthesis, executed modes, logs, and errors.
- Exact query execution through keyword-only retrieval with access filtering and retrieval completion logs.
- Semantic and uncertain/source-backed query execution through hybrid text retrieval.
- No-retrieval route that preserves planner trace and skips retrieval, ranking, and synthesis.
- Request ID continuity from planner request to retrieval evidence and generated answer.
- Planner, retrieval, ranking, and synthesis log coverage against the currently available shared successful-query expectations.
- Milestone 2 smoke tests for exact, semantic, hybrid fallback, no-retrieval, and log expectation behavior.

Validator repairs completed:

- Not yet needed; the initial local test gate passed.

### Milestone 3: Graph Layer

Status: complete.

Implemented in:

- `src/enrichment/__init__.py`
- `src/storage/__init__.py`
- `src/retrieval/execution.py`
- `src/retrieval/__init__.py`
- `src/planning/__init__.py`
- `tests/test_graph_layer.py`

Implemented:

- Deterministic dependency-free graph extraction for fixture-style relationship sentences.
- Entity extraction into shared `EntityRecord` records with stable IDs, aliases, confidence, and source provenance.
- Relation extraction into shared `RelationRecord` records for `depends_on`, `supports`, and `updates`, with evidence chunk IDs and confidence.
- Chunk-to-entity and chunk-to-relation links through graph quality flags and repository-side graph indexes.
- In-memory graph storage dictionaries and indexes for entities, relations, aliases, chunks, and entity adjacency.
- `commit_graph_records` and `verify_graph_storage` helpers with graph commit/verification logs.
- Graph traversal retrieval producing `EvidenceCandidate` records with:
  - `RetrievalMode.GRAPH`
  - entity IDs
  - relation IDs
  - source/document/chunk provenance
  - source reliability
  - citation links
  - access metadata
- Graph retrieval degraded-mode logs when no traversable graph is available.
- Graph/text merge compatibility so graph provenance survives evidence deduplication.
- Planner execution priority for graph plans so graph-selected requests execute graph traversal before hybrid fallback.
- End-to-end planned graph query flow through retrieval, ranking, and synthesis.

Validator repairs completed:

- Graph-selected planner routes now execute graph retrieval before hybrid retrieval.
- Added a full-flow graph orchestration test to lock planner-to-graph behavior.
- Tightened graph alias matching so one-character aliases do not match inside unrelated words.
- Added optional graph enrichment to the storage bundle path.
- Strengthened graph storage verification to check alias, chunk, relation, and reverse indexes.
- Added regression tests for unrelated graph evidence, graph-aware bundle commits, and corrupted graph indexes.

### Milestone 4: Validator Agent and Claim-Level Support

Status: complete.

Implemented in:

- `src/validation/__init__.py`
- `src/planning/__init__.py`
- `src/storage/__init__.py`
- `tests/test_validation.py`
- `tests/test_planner_orchestration.py`

Implemented:

- Dependency-free validator module with relevance, sufficiency, freshness, access, contradiction, and citation checks.
- `ValidationResult`, `EvidenceCheck`, and `ClaimSupportResult` result contracts.
- Claim-level support checks that annotate `ClaimRecord` support status, support type, confidence, and validator notes.
- Repair-action selection with bounded repair-loop handling.
- Validation logs and error envelopes for pass, repair-needed, and failure outcomes.
- In-memory validation and claim persistence hooks in `InMemoryStorageRepository`.
- Planner integration so ranked evidence is validated before synthesis.
- Non-pass validation blocks evidence-backed synthesis claims by passing no approved evidence to synthesis.
- Passing planned answers re-check generated claims and store supported claim records.
- Fresh-data phrasing now adds freshness validation even when the request did not explicitly set a freshness enum.

Validator repairs completed:

- Validation repair/failure status is now behaviorally enforced before synthesis, not only logged.
- Generated synthesis claims are rechecked and persisted on the passing orchestration path.
- Empty `required_validations=[]` stays explicit instead of falling back to default checks.
- Orchestration tests now require validation logs instead of skipping the validation partition.

### Milestone 5: Evaluation, Observability, and Optimization

Status: complete.

Implemented in:

- `src/evaluation/__init__.py`
- `src/feedback/__init__.py`
- `src/storage/__init__.py`
- `tests/test_evaluation_metrics.py`
- `tests/test_feedback_improvement.py`

Implemented:

- Dependency-free evaluation dataset case records for reviewed request/answer/evidence/validation/feedback context.
- Batch evaluation reports with retrieval recall, citation precision, unsupported claim rate, validator rejection rate, graph hit rate, and reranker improvement metrics.
- Dashboard-ready observability reports for partition log counts, event counts, error counts, latency, and cost.
- Feedback-to-improvement task records that group failure categories into append-only queued work without mutating source reliability, access policy, or governance state.
- In-memory persistence hooks for evaluation cases, evaluation reports, observability reports, and improvement tasks.
- Retryable storage error handling for evaluation reports, observability reports, and improvement tasks.

Validator repairs completed:

- Metric aggregation skips non-applicable reranker-improvement cases instead of treating missing baselines as regressions.
- Citation precision treats requests with no emitted citations as having no precision denominator, while unsupported-claim and validation metrics still track quality failures.
- Full test coverage now includes evaluation metrics, observability summaries, improvement task creation, deduplication, storage failure handling, and policy non-mutation.

### Milestone 6: Hardening and Production Readiness

Status: complete.

Implemented in:

- `src/storage/__init__.py`
- `src/source_registry/registry.py`
- `src/source_registry/__init__.py`
- `docs/production_readiness.md`
- `tests/test_milestone6_hardening.py`

Implemented:

- Retryable storage bundle commits with rollback snapshots for partial-write recovery.
- `StorageOperationError` and `StorageRecoveryResult` contracts for failure injection and recovery reporting.
- Structured storage retry, failure, and successful recovery telemetry.
- Source refresh monitoring for scheduled, event-driven, real-time, static, and manual sources.
- Duration parsing for `refresh_interval` and `freshness_sla` values such as `15m`, `12h`, `2d`, and `1w`.
- Stale-source detection for overdue, never-checked, blocked, and failed sources.
- Stale active source deprecation that preserves access policy and allowed principals.
- Production readiness checklist, recovery procedure, security review, source refresh procedure, and load-test report.
- Local load-style retrieval/ranking guardrail over 120 in-memory chunks.

Validator repairs completed:

- Initial focused Milestone 6 test gate passed.

### Milestone 7: Durable Backend Integration Baseline

Status: complete.

Implemented in:

- `src/storage/durable.py`
- `src/storage/__init__.py`
- `tests/test_durable_storage.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `DurableStorageRepository`, a dependency-free extension of `InMemoryStorageRepository`.
- JSON snapshot persistence for:
  - raw artifacts
  - sources
  - documents
  - chunks
  - entities
  - relations
  - ingestion jobs
- Append-only JSONL persistence for logs and error envelopes.
- Durable reload behavior that reconstructs shared dataclasses and enum/date/datetime fields from existing serializers.
- Recovery warnings for malformed snapshots and JSONL rows, while valid persisted records continue to load.
- Graph index rebuild on durable reload for entity aliases and relation reverse indexes.
- Regression coverage for round-trip persistence, append-only logs/errors, malformed persisted rows, and access/governance non-mutation.

Validator repairs completed:

- Focused Milestone 7 durable storage test gate passed.
- Durable rollback now restores local JSON/JSONL files as well as in-memory repository fields, preventing phantom persisted records after failed bundle commits.
- Status/test notes were refreshed after the final Milestone 7 repair pass.

### Milestone 8: External Backend Adapter Contracts

Status: complete.

Implemented in:

- `src/storage/adapters.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `BackendType` roles for metadata, raw source, vector, graph, and telemetry backends.
- `BackendCapability` manifests for read/write, snapshot, append-only telemetry, access filtering, vector search, graph traversal, health checks, and transactional write requirements.
- `BackendAdapterConfig`, `BackendHealthCheck`, and `BackendSelection` records with serializer-friendly dictionaries.
- `BackendAdapterRegistry` for deterministic registration, health recording, adapter selection, and missing-capability failure reporting.
- `create_local_backend_registry`, mapping the current JSON/JSONL durable store and in-memory indexes into future backend roles.
- `validate_backend_plan`, a small helper for checking multi-backend requirements before future external service clients are introduced.
- Redacted serialized adapter connection settings for secret-like keys while preserving environment-variable references.

Validator repairs completed:

- Focused Milestone 8 adapter contract test gate passed.

### Milestone 9: Executable Local Durable Backend Adapter

Status: complete.

Implemented in:

- `src/storage/adapters.py`
- `src/storage/durable.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `BackendRuntimeAdapter`, a dependency-free protocol for executable backend adapters.
- `BackendOperationResult`, a serializer-friendly operation outcome record.
- `LocalDurableStorageBackendAdapter`, the first executable backend adapter around `DurableStorageRepository`.
- Adapter health checks that verify local durable storage writability and report missing capabilities without exposing credentials.
- Adapter commit execution through the existing `commit_storage_bundle_with_recovery` rollback and retry boundary.
- Registry selection coverage for transactional durable write capabilities.
- Regression coverage proving adapter commits persist raw artifacts, sources, documents, chunks, logs, and access-governance fields.

Validator repairs completed:

- Focused Milestone 9 adapter runtime test gate passed.

### Milestone 10: Executable Vector Backend Adapter Baseline

Status: complete.

Implemented in:

- `src/storage/vector_runtime.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`

Implemented:

- `InMemoryVectorBackendAdapter`, an executable runtime adapter around the existing dependency-free vector index.
- Vector backend health checks with capability reporting, latency, indexed chunk counts, and degraded missing-capability details.
- Adapter-driven vector indexing through the existing `commit_vectors` storage/indexing path.
- Adapter-driven vector search through the existing deterministic vector search path.
- `BackendOperationResult` output for vector indexing and search.
- Search result details that expose candidate IDs, scores, matched terms, and index record IDs without exposing chunk text.
- Regression coverage for vector runtime selection, indexing, search serialization, access-governance preservation, and empty-content indexing failure behavior.

Validator repairs completed:

- Focused Milestone 10 vector runtime adapter test gate passed.

### Milestone 11: Qdrant-Compatible Vector Backend Adapter

Status: complete.

Implemented in:

- `src/storage/qdrant_runtime.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`
- `project_tests.md`

Implemented:

- `QdrantVectorBackendAdapter`, a dependency-optional service-backed vector adapter boundary with injected-client support.
- Qdrant health checks with capability reporting, collection point counts, unavailable-client errors, and secret-safe connection summaries.
- Adapter-driven point indexing from deterministic chunk embeddings into governed Qdrant payloads.
- Qdrant-style search support for both `search` and `query_points` client APIs.
- Search result details exposing chunk IDs, scores, matched terms, index IDs, source/document IDs, and access metadata without exposing chunk text.
- Regression coverage for Qdrant adapter selection, indexing, search serialization, unavailable-client behavior, no-text-leakage, and write-failure error envelopes.

Validator repairs completed:

- Focused Milestone 11 Qdrant-compatible adapter test gate passed.

### Milestone 12: Neo4j-Compatible Graph Backend Adapter

Status: complete.

Implemented in:

- `src/storage/neo4j_runtime.py`
- `src/storage/__init__.py`
- `tests/test_backend_adapters.py`
- `project_milestones.md`
- `current_process_status.md`
- `project_tests.md`

Implemented:

- `Neo4jGraphBackendAdapter`, a dependency-optional service-backed graph adapter boundary with injected-client support.
- Neo4j health checks with capability reporting, unavailable-client errors, and secret-safe connection summaries.
- Adapter-driven graph indexing from deterministic entity, relation, and chunk graph metadata into governed service payloads.
- Neo4j-style traversal support through `execute_query` clients.
- Traversal result details exposing chunk IDs, scores, entity IDs, relation IDs, source/document IDs, and access metadata without exposing chunk text.
- Regression coverage for Neo4j adapter selection, graph indexing, traversal serialization, unavailable-client behavior, no-text-leakage, and write-failure error envelopes.

Validator repairs completed:

- Focused Milestone 12 Neo4j-compatible adapter test gate passed.

### Milestone 13: LangGraph-Compatible Orchestration Runtime Boundary

Status: complete.

Implemented in:

- `src/planning/orchestration_runtime.py`
- `src/planning/__init__.py`
- `tests/test_planner_orchestration.py`
- `project_milestones.md`
- `current_process_status.md`
- `project_tests.md`

Implemented:

- `LangGraphCompatibleOrchestrationAdapter`, a dependency-optional orchestration adapter for injected LangGraph-style apps.
- Orchestration runtime config, capability, health-check, and run-result records.
- Health checks for ready, degraded local fallback, missing capability, and unavailable runtime states.
- Adapter-driven planned-query execution through injected app `invoke` calls or the existing local `run_planned_query` fallback.
- App-failure fallback behavior that preserves the original error envelope while completing through local planned-query execution.
- Regression coverage for local fallback, injected app execution, app-failure fallback, unavailable disabled-fallback behavior, and serialized operation summaries.

Validator repairs completed:

- Focused Milestone 13 orchestration runtime test gate passed.

### Full Backend Environment and Short Keyword Manual

Status: complete.

Implemented in:

- `pyproject.toml`
- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- `src/backend_app/__init__.py`
- `src/backend_app/health.py`
- `src/backend_app/manual.py`
- `scripts/setup_full_backend.ps1`
- `scripts/test_full_backend.ps1`
- `tests/test_backend_health.py`
- `tests/test_backend_manual.py`
- `tests/test_backend_setup_artifacts.py`
- `docs/local_environment.md`
- `docs/service_setup.md`
- `docs/short_keyword_manual.md`
- `project_tests.md`

Implemented:

- `backend`, `test`, and `full` package extras for reproducible local installs.
- Full optional backend software installed in `.venv`: Qdrant client, Neo4j driver, LangGraph, and LlamaIndex core.
- Docker Compose definitions for local Qdrant and Neo4j service containers.
- `.env.example` with local Qdrant, Neo4j, storage, and model-profile defaults.
- `rag-center-health`, a console command that checks optional client imports, Docker availability, environment variables, service adapter health, and LangGraph fallback status.
- `rag-center-smoke`, a console command that ingests the public fixture, commits storage records, builds vector and sparse keyword indexes, runs an exact keyword path, and prints a cited answer.
- `scripts/setup_full_backend.ps1`, a repeatable setup workflow for venv creation, full extra install, `.env` creation, optional Docker Desktop install request, optional service startup, health checks, and smoke run.
- `scripts/test_full_backend.ps1`, a repeatable validation workflow for dependency checks, health checks, smoke run, unittest discovery, and pytest.
- A short keyword manual documenting the smoke path and its proof points.
- Regression coverage for demo repository construction, short keyword manual execution, and CLI success output.
- Setup artifact coverage for console entry points, full/backend extras, `.env.example`, Docker Compose services, and setup/test script wiring.

Validated:

- Full backend imports passed.
- Optional backend imports passed.
- `pip check` reported no broken requirements.
- `rag-center-health` passed in regular mode with Docker/service warnings.
- `rag-center-health --strict-services --env-file .env.example` reported blocked Qdrant and Neo4j services because Docker is not installed on the current host.
- `rag-center-smoke` returned one keyword candidate, keyword execution mode, one citation, and a cited answer.
- Standard-library unittest discovery passed with 115 tests.
- Pytest passed with 205 tests.
- `scripts/test_full_backend.ps1` passed end to end.
- Docker Desktop is not available on the current host, so local Qdrant and Neo4j containers were not started.

## Unfinished Work

### Later Milestones

Status:

- Milestone 2: complete.
- Milestone 3: complete.
- Milestone 4: complete.
- Milestone 5: complete.
- Milestone 6: complete.
- Milestone 7: complete.
- Milestone 8: complete.
- Milestone 9: complete.
- Milestone 10: complete.
- Milestone 11: complete.
- Milestone 12: complete.
- Milestone 13: complete.

## Known Issues and Caveats

### Test Runner Availability

`python -m pytest` is available in the current environment. Standard-library unittest discovery is still kept as a dependency-light test gate:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Current status:

- Standard-library unittest discovery passes.
- Latest observed unittest result: 115 standard-library unittest tests passed.
- Latest observed pytest result: 205 tests passed.

### Runtime Dependencies and Optional Integrations

The base project still has no required runtime dependencies. The `full` extra installs optional integration libraries for local development and compatibility checks.

Installed optional integration libraries:

- LlamaIndex
- Neo4j
- Qdrant
- LangGraph

Deferred real services and credentials:

- model services
- durable metadata store
- durable raw source/object store

### In-Memory First With Local Durable Baseline

Current implementations remain dependency-free and in-memory first:

- source registry
- ingestion job repository
- raw artifact repository
- metadata storage
- vector index
- keyword index
- retrieval execution
- ranking
- validation
- synthesis
- feedback capture
- evaluation trace storage
- planner routing
- graph extraction, storage, and traversal retrieval

Milestone 7 adds a local durable baseline for storage records, logs, and errors through JSON snapshots and append-only JSONL files. External durable services are still future work.

Milestone 8 adds dependency-free adapter contracts so external metadata stores, raw source/object stores, vector databases, graph databases, and telemetry stores can be introduced behind explicit capability and health checks.

Milestone 9 adds the first executable adapter runtime by wrapping the local durable JSON/JSONL repository behind health-check, transactional-write selection, and recovery-aware commit semantics.

Milestone 10 adds an executable vector backend runtime around the current dependency-free vector index, preserving adapter health checks, operation results, storage-index commit behavior, and downstream access-filter ownership.

Milestone 11 adds a Qdrant-compatible vector backend adapter with injected-client support, governed point payloads, service search result serialization, and dependency-optional runtime behavior.

Milestone 12 adds a Neo4j-compatible graph backend adapter with injected-client support, governed graph payloads, service traversal result serialization, and dependency-optional runtime behavior.

Milestone 13 adds a LangGraph-compatible orchestration runtime boundary with injected-app support, local planned-query fallback, health checks, operation summaries, and dependency-optional behavior.

### No Real Embeddings Yet

Vector indexing uses deterministic hashed bag-of-terms vectors. This is suitable for unit tests and early behavior checks, but not for production retrieval quality.

### Planner Orchestration Has a Dependency-Optional Runtime Boundary

Milestone 2 provides planner classification, routing, budgets, trace records, and a dependency-free planner-to-retrieval smoke flow. Milestone 13 wraps that flow in a LangGraph-compatible adapter boundary, but it does not yet implement durable orchestration traces, explicit graph nodes, or production LangGraph workflows.

### Graph Layer Is Deterministic

The graph layer is implemented with deterministic fixture-friendly extraction and in-memory traversal. It is suitable for milestone tests and orchestration checks, but it does not yet use a production entity extraction model or durable graph database.

## Current Test Status

Latest unittest command run:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Latest unittest result:

```text
Ran 115 tests
OK
```

Latest pytest result:

```text
205 passed
```

`python -m pytest` is available in the current environment.

## Recommended Next Step

Use the validated P1.4.2 broader repository save/orchestration hook extraction as the handoff point for selecting the next production optimization lane. Prefer test-first work such as P1.5.2 telemetry golden coverage or durable persistence golden tests. Do not begin durable repository wrappers until separate persistence golden tests exist.

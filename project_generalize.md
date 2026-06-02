# Project Generalize

Evidence sources:

- `generalize_project.json`
- `generalize_project_summary.md`
- `MARACA_v02_generalize_tracker.md`

## Purpose

`project_generalize` is the controlled standardization and generalization process for MARACA v02. Its goal is to extract shared behavior only where the current codebase provides evidence, while preserving public behavior, test semantics, dependency-free paths, access controls, telemetry fields, and durable persistence compatibility.

## Operating Rules

1. Every task must map to evidence from `generalize_project.json`, the summary findings, duplicate groups, or existing tracker items.
2. Prefer parity and golden tests before moving shared behavior.
3. Introduce abstractions only when at least two evidence-backed modules use the behavior, or when a ranked summary finding calls out the cross-cutting surface.
4. Keep first implementations narrow and reversible.
5. Preserve public APIs and serialized output shapes unless a reviewed migration note exists.
6. Treat these surfaces as high-risk gates: telemetry/error envelopes, provenance/access policy, candidate hydration, claim lifecycle, durable persistence, backend adapters, and planner routing.
7. Before starting a new agent, check current goal/context usage. If usage exceeds 50%, do not start another agent; update the project files, write a handoff summary with the same controlling prompt, and continue from a new chat.

## Optimized Execution Strategy

Use a risk ladder instead of a broad refactor pass:

1. Lock exact behavior with focused parity or golden tests.
2. Extract dependency-free helpers first when the duplicate behavior is exact.
3. Move medium-risk shared contracts only after serialized output fixtures are captured.
4. Defer high-risk lifecycle, telemetry, persistence, and access-policy surfaces until the affected modules have explicit acceptance tests.
5. Promote only one implementation lane at a time unless file ownership is disjoint and validation commands are independent.

The current optimized sequence is:

1. **P1.3 deterministic stable IDs** - completed bootstrap extraction.
2. **P1.1.1 serialization golden-output inventory** - completed test-first behavior lock.
3. **P1.1.2 shared serialization helper** - completed extraction with P1.1.1 golden outputs preserved.
4. **P1.2 enum coercion helper** - completed focused coercion/lookup extraction.
5. **P1.4.1 optional repository log/error hook helper** - completed shared optional repository log/error hook helpers for feedback/evaluation only.
6. **P1.5 telemetry/event golden-output inventory** - completed test-first behavior lock for representative logs and errors.
7. **P1.5.1 paired error telemetry helper** - completed production extraction covered by P1.5 golden tests.
8. **P1.4.2 narrow repository hook extraction** - completed and validated for ranking, synthesis, validation, planning, and orchestration runtime hook wiring.
9. **Next lane selection** - choose the next high-value production optimization lane; feedback/evaluation domain save hooks and durable repository wrappers remain deferred until separate persistence golden tests exist.

## Task Promotion Model

Tasks move through these states:

- `proposed`: evidence exists, but acceptance criteria or tests are incomplete.
- `ready`: affected files, compatibility requirements, and validation commands are known.
- `in_progress`: an implementation owner is assigned and file scope is locked.
- `implemented`: code or docs are changed and focused tests have been run by the worker.
- `validating`: an independent validator/adversary review is checking the diff and test evidence.
- `validated`: validator signoff, tracker update, and required tests are complete.
- `blocked` or `deferred`: the reason is written in the tracker with the next unblock condition.

## Agent Workflow

Each implementation task uses an agent loop:

1. **Review agent** reads the evidence and recommends the smallest safe slice.
2. **Planning agent** maps the slice into acceptance criteria, tests, risks, and tracker fields.
3. **Orchestration worker agent** implements the slice in an owned file scope.
4. **Validator agent** reviews the diff and focused validation output.
5. **Main thread** integrates, runs tests, updates the tracker, and decides whether the task is complete or needs repair.

Workers must not revert unrelated edits and must keep write scopes disjoint when multiple workers run.

Agent start gate: check context usage before each new agent. If the usage is over 50%, stop agent spawning for this chat and switch to tracker, plan, and handoff updates only.

Required agent outputs:

- Review agent: ranked slice recommendation, evidence references, and adversarial risks.
- Planning agent: file scope, acceptance criteria, rollback note, and validation commands.
- Worker agent: implementation summary, changed files, and focused test output.
- Validator agent: pass/fail finding list with file references and residual risk.
- Main thread: final regression result, tracker status, and finished flag.

## Phase Order

### Phase 0 - Evidence Lock and Review Gates

Confirm every generalization task has source evidence and clear affected modules. Planning-only changes stay separate from implementation changes.

### Phase 1 - Shared Foundation Contracts

Standardize low-level shared primitives before high-risk behavior:

- serialization and DTO export
- enum coercion
- deterministic stable IDs
- repository hooks
- telemetry and operation builders

The first implementation slice is **P1.3 deterministic stable IDs**, because the review agent found an exact duplicate helper in `src/enrichment/__init__.py` and `src/retrieval/indexing.py`. Serialization remains a foundational follow-up after golden outputs are locked.

### Phase 2 - Evidence, Provenance, Access, and Claims

Centralize trace extraction, candidate hydration, fail-closed access metadata checks, citation approval, and claim lifecycle behavior only after parity tests exist.

### Phase 3 - Repository, Persistence, Graph, and Index Primitives

Standardize in-memory repository patterns, save/snapshot tables, graph index rebuild/verify/traversal, and vector/sparse index commit pipelines.

### Phase 4 - Normalization, Freshness, and Scoring

Extract shared text normalization, date/freshness resolution, scoring, clamping, term extraction, and quality flag helpers.

### Phase 5 - Table-Driven Policy Surfaces

Convert conditional-heavy behavior into explicit policy tables for ingestion normalization, planner routing, backend health descriptors, and feedback failure taxonomy.

### Phase 6 - Adapter, Runtime, Metrics, and Script Templates

Generalize backend runtime adapter patterns, optional-client boundaries, metrics aggregation, and PowerShell setup/test helpers.

## Validation Gates

- **Evidence gate:** task references evidence ids or exact source findings.
- **Parity gate:** tests prove existing behavior is unchanged.
- **API gate:** public names and return shapes remain compatible.
- **Safety gate:** access and citation logic remain fail-closed.
- **Persistence gate:** durable JSON/JSONL compatibility is preserved.
- **Telemetry gate:** event names, severities, retry counts, fallback actions, and output references remain stable.
- **Adapter gate:** ready/degraded/unavailable semantics remain intact.
- **Review gate:** high-risk surfaces have explicit validator/adversarial review.

Validation runs in tiers:

- **Focused:** tests for the touched modules and new helper contracts.
- **Phase:** tests covering all modules listed in the active phase item.
- **Full regression:** full `pytest` plus `unittest discover` before marking a task validated when the implementation touches shared behavior.
- **Service smoke:** Qdrant/Neo4j health and adapter semantics when storage, retrieval, graph, or backend service surfaces change.

## Completed Tasks

Task: **P1.3 deterministic stable ID extraction**

Scope:

- Add a dependency-free shared stable-id helper.
- Wire `src/enrichment/__init__.py` and `src/retrieval/indexing.py` to the helper.
- Preserve byte-for-byte ID format: prefix, separator `\x1f`, SHA-256 digest, and 24 hex characters.
- Add focused tests proving separator behavior and parity for embedding, sparse, entity, and relation IDs.

Initial validation:

- `python -m pytest tests/test_shared_ids.py tests/test_indexing.py tests/test_graph_layer.py`
- `python -m unittest discover -s tests`

Result: validated with focused pytest, full unittest discovery, full pytest, and validator signoff.

Task: **P1.1.1 serialization golden-output inventory**

Scope:

- Inventory current DTO/dataclass export behavior in the affected shared and planning modules.
- Add golden tests for current JSON-ready output shapes.
- Lock tuple/list behavior, nested dataclass export, enum/date coercion, explicit orchestration runtime payloads, and `planned_query` omission.
- Keep this task test-only with no shared serializer implementation.

Validation:

- focused golden pytest: 6 passed
- broader focused serialization suite: 51 passed
- phase pytest: 82 passed
- full unittest discovery: 121 passed
- full pytest: 217 passed

Result: validated with validator signoff and tracker update.

Task: **P1.1.2 shared serialization helper extraction**

Scope:

- Add a dependency-free `shared.serialization` helper surface.
- Wire shared contracts, shared records, environment profiles, stack components, and orchestration runtime serialization through the helper.
- Export the helper from `shared`.
- Preserve compatibility aliases from `shared.contracts`.
- Preserve intentional output differences: planner traces emit lists, orchestration runtime DTOs preserve selected tuples, stack package names are lists, and `OrchestrationRunResult.to_dict()` omits `planned_query`.

Validation:

- focused serialization/planning pytest: 52 passed
- phase pytest: 83 passed
- full unittest discovery: 121 passed
- full pytest: 218 passed

Result: validated with validator signoff and tracker update.

Task: **P1.2 enum coercion and lookup helper**

Scope:

- Add a dependency-free `shared.enums` helper surface for string enum coercion and enum-keyed lookup.
- Wire source registry enum input coercion through the helper while preserving `SourceRegistryError` wrapping and native `ValueError` cause.
- Wire environment profile and stack component lookups through the helper while preserving native `ValueError` and mapping `KeyError` behavior.
- Wire ingestion trigger-type coercion only for the public `start_ingestion_job(trigger_type=...)` input.
- Avoid broad internal ingestion coercion of manually malformed `SourceRecord` fields.

Validation:

- focused P1.2 pytest: 55 passed
- phase pytest: 95 passed
- full unittest discovery: 121 passed
- full pytest: 230 passed

Result: validated with validator signoff and tracker update.

Task: **P1.4.1 optional repository log/error hook helper**

Scope:

- Add shared optional repository log/error hook helpers in `src/shared/repository_hooks.py`.
- Export the helpers from `src/shared/__init__.py`.
- Wire feedback/evaluation `_add_log` and `_save_error` helpers through the shared hook surface.
- Preserve optional repository behavior, telemetry/error event details, and return shapes.
- Validate this as a first slice only.

Validator notes:

- `required=True` means the method is required only when a repository object exists.
- Optional mode treats a hook attribute of `None` as missing.

Validation:

- focused P1.4 pytest: 27 passed
- phase-adjacent pytest: 35 passed
- full unittest discovery: 125 passed
- full pytest: 242 passed

Result: validated first slice with validator signoff and tracker update. Broader validation, ranking, synthesis, planning, and orchestration repository hook wiring was completed later as P1.4.2; feedback/evaluation domain save hooks and durable repository wrappers remain deferred until persistence golden tests exist.

Task: **P1.5 telemetry/event golden-output inventory**

Scope:

- Add telemetry/event golden tests before extracting shared builders.
- Preserve event names, severities, retry counts, fallback actions, output references, messages, operation names, and error envelopes.
- Keep implementation test-only because this surface is high risk.
- Defer enrichment, storage, retrieval execution, orchestration runtime/adapters, feedback improvement tasks, and evaluation batch/observability telemetry.
- Keep feedback/evaluation domain save hooks and durable repository wrappers deferred until behavior inventory and persistence golden tests exist.

Validation:

- focused P1.5 pytest: 8 passed
- phase-adjacent pytest: 109 passed
- full unittest discovery: 125 passed
- full pytest: 250 passed

Result: validated with validator signoff and tracker update. Builder extraction is promoted separately as P1.5.1.

Task: **P1.5.1 paired error telemetry helper**

Scope:

- Use the P1.5 golden inventory as the compatibility gate.
- Extract the smallest production helper for repeated paired error envelope/log construction.
- Preserve every locked event/error payload shape from `tests/test_telemetry_event_golden.py`.
- Keep omitted telemetry surfaces deferred until their own golden coverage exists.

Validation:

- focused P1.5.1 pytest: 16 passed
- phase-adjacent pytest: 53 passed
- full unittest discovery: 125 passed
- full pytest: 252 passed

Result: validated with validator signoff and tracker update. Additional telemetry builders remain deferred until their own golden coverage exists.

Task: **P1.4.2 narrow repository hook extraction**

Scope:

- Inventory deferred repository save/log/error hook behavior before extraction.
- Lock strict/permissive missing-hook behavior for ranking, validation, synthesis, and planning/orchestration; inventory domain save hooks but defer their extraction until persistence golden tests exist.
- Preserve durable persistence compatibility, telemetry payloads, return shapes, and failure propagation.
- Keep production extraction narrow and gated by focused parity tests.

Validated production scope:

- ranking and synthesis log/error helpers wired through `shared.repository_hooks` with strict `required=True` behavior
- validation log/error/validation/claim helpers wired through permissive `shared.repository_hooks`
- planning required log hooks and optional claim save wired through `shared.repository_hooks`
- orchestration runtime adapter log/error hooks wired through permissive `shared.repository_hooks`

Deferred scope:

- feedback/evaluation domain save helpers
- durable storage save/snapshot/JSON/JSONL wrappers

Validation:

- focused P1.4.2 pytest: 59 passed
- expanded phase-adjacent pytest: 147 passed
- full unittest discovery: 129 passed
- full pytest: 268 passed

Result: validated with validator signoff and tracker update. Durable/domain-save wrapper work remains deferred until persistence golden tests exist.

## Next Orchestration Task

Task: **Next lane selection after P1.4.2**

Scope:

- Select the next production optimization lane from the remaining backlog.
- Prefer test-first work for any high-risk surface.
- Do not begin feedback/evaluation domain save or durable repository wrapper extraction until separate persistence golden tests exist.

Initial validation:

- update tracker/status with selected lane and acceptance criteria
- add focused golden/parity tests before production extraction
- run focused, phase-adjacent, unittest discovery, and full pytest before marking any lane validated

## Handoff Note

The latest validated lane is P1.4.2 narrow repository hook extraction. Continue from `project_generalize_handoff.md`, check the context threshold before starting agents, and select the next production optimization lane. Feedback/evaluation domain save hooks and durable repository wrappers require separate persistence golden tests before extraction.

## Completion Criteria

`project_generalize` is complete only when every tracker item is validated, deferred with rationale, or explicitly closed; high-risk surfaces have review signoff; and full regression tests pass with no public behavior drift.

from dataclasses import replace
from datetime import date
import unittest

import planning as planning_module
from ingestion import run_ingestion_job, split_document_into_chunks
from planning import (
    LangGraphCompatibleOrchestrationAdapter,
    LocalPlannedQueryGraphApp,
    OrchestrationStatus,
    create_retrieval_request,
    run_planned_query,
)
from retrieval import commit_sparse_index, commit_vectors
from shared import (
    AccessDecision,
    AccessLevel,
    AccessMethod,
    FreshnessPolicy,
    LicensePolicy,
    OutputIntent,
    QueryType,
    ReliabilityLevel,
    RepairAction,
    RetrievalMode,
    SourceStatus,
    SourceType,
    SUCCESSFUL_QUERY_LOG_EXPECTATIONS,
    ValidationStatus,
    load_fixture_catalog,
)
from source_registry import SourceRegistry
from storage import InMemoryStorageRepository, commit_storage_bundle


def _fixture(fixture_id: str) -> dict[str, object]:
    catalog = load_fixture_catalog()
    return next(entry for entry in catalog["fixtures"] if entry["id"] == fixture_id)


def _register_fixture(registry: SourceRegistry, fixture_id: str):
    entry = _fixture(fixture_id)
    source = registry.register_source(
        source_name=str(entry["source_name"]),
        source_type=SourceType(str(entry["source_type"])),
        owner="milestone2-orchestration",
        access_method=AccessMethod.UPLOAD,
        access_level=AccessLevel(str(entry["access"])),
        external_link=entry["external_link"] if isinstance(entry["external_link"], str) else None,
        internal_location=str(entry["path"]),
        license_policy=LicensePolicy(str(entry["license"])),
        reliability_level=ReliabilityLevel(str(entry["reliability"])),
        freshness_policy=FreshnessPolicy(str(entry["freshness"]["policy"])),
        status=SourceStatus(str(entry["status"])),
    )
    return source, entry


def _indexed_public_repository() -> InMemoryStorageRepository:
    storage = InMemoryStorageRepository()
    registry = SourceRegistry()
    source, entry = _register_fixture(registry, "fixture_a_public_document")
    ingestion = run_ingestion_job(source, fixture_entry=entry)
    if ingestion.document_record is None or ingestion.normalized_document is None:
        raise AssertionError("public fixture did not produce a document")
    chunks = split_document_into_chunks(ingestion.normalized_document, ingestion.document_record, source=source)
    commit_storage_bundle(
        storage,
        raw_artifact=ingestion.raw_artifact,
        source=source,
        document=ingestion.document_record,
        chunks=chunks,
        job=ingestion.job,
        logs=ingestion.logs,
        errors=ingestion.errors,
    )
    commit_vectors(storage, storage.chunks.values())
    commit_sparse_index(storage, storage.chunks.values())
    return storage


class FakeLangGraphApp:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.payloads: list[dict[str, object]] = []

    def invoke(self, payload: dict[str, object]) -> object:
        self.payloads.append(payload)
        if self.fail:
            raise RuntimeError("graph app failed")
        return run_planned_query(
            payload["request"],
            payload["repository"],
            principal=payload["principal"],
            principal_scopes=payload["principal_scopes"],
            use_case=payload["use_case"],
            ranking_config=payload["ranking_config"],
            current_date=payload["current_date"],
            correlation_id=payload["correlation_id"],
        )


class SaveErrorOnlyRepository:
    def __init__(self) -> None:
        self.errors: list[object] = []

    def save_error(self, error: object) -> None:
        self.errors.append(error)


class PlannerOrchestrationTests(unittest.TestCase):
    def test_exact_plan_executes_keyword_retrieval_and_preserves_trace(self) -> None:
        storage = _indexed_public_repository()
        result = run_planned_query(
            '"alpha evidence bridge"',
            storage,
            principal="reader",
            current_date=date(2026, 5, 21),
        )

        self.assertEqual(result.planning.plan.query_type, QueryType.EXACT)
        self.assertEqual(result.planning.plan.selected_modes, [RetrievalMode.KEYWORD])
        self.assertEqual(result.executed_modes, (RetrievalMode.KEYWORD,))
        self.assertIsNotNone(result.retrieval)
        self.assertTrue(result.retrieval.candidates)
        self.assertTrue(all(candidate.retrieval_mode is RetrievalMode.KEYWORD for candidate in result.retrieval.candidates))
        self.assertTrue(all(candidate.request_id == result.planning.request.request_id for candidate in result.retrieval.candidates))
        self.assertIsNotNone(result.synthesis)
        self.assertEqual(result.synthesis.answer.request_id, result.planning.request.request_id)
        self.assertIsNone(result.repair_trace)
        self.assertEqual({log.correlation_id for log in result.logs}, {result.planning.logs[0].correlation_id})

    def test_semantic_plan_uses_hybrid_text_retrieval_for_source_backed_answer(self) -> None:
        storage = _indexed_public_repository()
        result = run_planned_query(
            "Explain how sparse search and vector search support citation quality",
            storage,
            principal="reader",
            current_date=date(2026, 5, 21),
        )

        self.assertEqual(result.planning.plan.query_type, QueryType.SEMANTIC)
        self.assertEqual(result.planning.plan.selected_modes, [RetrievalMode.VECTOR, RetrievalMode.HYBRID])
        self.assertEqual(result.executed_modes, (RetrievalMode.HYBRID,))
        self.assertIsNotNone(result.retrieval)
        self.assertTrue(result.retrieval.candidates)
        self.assertTrue(any(candidate.retrieval_mode in {RetrievalMode.VECTOR, RetrievalMode.HYBRID} for candidate in result.retrieval.candidates))
        self.assertIsNotNone(result.ranking)
        self.assertIsNotNone(result.synthesis)
        self.assertTrue(result.ranking.ranked_evidence)
        self.assertTrue(result.synthesis.claims)
        self.assertTrue(storage.claim_records)

    def test_validation_repair_blocks_evidence_backed_synthesis_claims(self) -> None:
        storage = _indexed_public_repository()
        result = run_planned_query(
            "latest alpha evidence bridge",
            storage,
            principal="reader",
            current_date=date(2028, 5, 22),
        )

        self.assertIsNotNone(result.validation)
        self.assertEqual(result.validation.validation.validation_status, ValidationStatus.REPAIR_NEEDED)
        self.assertIsNotNone(result.repair_trace)
        self.assertEqual(result.repair_trace.validation_status, ValidationStatus.REPAIR_NEEDED)
        self.assertEqual(result.repair_trace.repair_action, RepairAction.EXTERNAL_LOOKUP)
        self.assertEqual(result.repair_trace.repair_attempt, result.planning.plan.repair_attempt)
        self.assertEqual(result.repair_trace.max_repair_attempts, result.planning.plan.max_repair_attempts)
        self.assertEqual(result.repair_trace.previous_actions, ())
        self.assertFalse(result.repair_trace.exhausted)
        self.assertFalse(result.repair_trace.retrieval_rerun_requested)
        self.assertIsNotNone(result.synthesis)
        self.assertEqual(result.synthesis.used_evidence, ())
        self.assertEqual(result.synthesis.claims, ())
        self.assertIn("validation_repair_needed", _event_names(result.logs))

    def test_validation_failure_exposes_exhausted_repair_trace_with_prior_actions(self) -> None:
        storage = _indexed_public_repository()
        original_plan_request = planning_module.plan_request

        def plan_with_exhausted_attempt(*args, **kwargs):
            planning = original_plan_request(*args, **kwargs)
            plan = replace(
                planning.plan,
                repair_attempt=1,
                max_repair_attempts=1,
                previous_actions=["retrieve_more"],
            )
            return replace(planning, plan=plan)

        planning_module.plan_request = plan_with_exhausted_attempt
        try:
            result = run_planned_query(
                "latest alpha evidence bridge",
                storage,
                principal="reader",
                current_date=date(2028, 5, 22),
            )
        finally:
            planning_module.plan_request = original_plan_request

        self.assertIsNotNone(result.validation)
        self.assertEqual(result.validation.validation.validation_status, ValidationStatus.FAIL)
        self.assertIsNotNone(result.repair_trace)
        self.assertEqual(result.repair_trace.validation_status, ValidationStatus.FAIL)
        self.assertEqual(result.repair_trace.repair_action, RepairAction.STOP)
        self.assertEqual(result.repair_trace.repair_attempt, 1)
        self.assertEqual(result.repair_trace.max_repair_attempts, 1)
        self.assertEqual(result.repair_trace.previous_actions, ("retrieve_more",))
        self.assertEqual(result.repair_trace.fallback_actions, tuple(result.planning.plan.fallback_actions))
        self.assertTrue(result.repair_trace.exhausted)
        self.assertFalse(result.repair_trace.retrieval_rerun_requested)
        self.assertIn("validation_failed", _event_names(result.logs))

    def test_source_backed_uncertain_question_falls_back_to_hybrid(self) -> None:
        storage = _indexed_public_repository()
        result = run_planned_query("alpha evidence bridge", storage, principal="reader")

        self.assertEqual(result.planning.plan.query_type, QueryType.MIXED)
        self.assertEqual(result.planning.plan.selected_modes, [RetrievalMode.HYBRID])
        self.assertEqual(result.executed_modes, (RetrievalMode.HYBRID,))
        self.assertIsNotNone(result.retrieval)
        self.assertTrue(result.retrieval.candidates)
        self.assertTrue(all(candidate.access_decision is AccessDecision.ALLOWED for candidate in result.retrieval.candidates))

    def test_no_retrieval_plan_does_not_call_downstream_retrieval(self) -> None:
        storage = _indexed_public_repository()
        request = create_retrieval_request(
            "Format this paragraph",
            output_intent=OutputIntent.SUMMARY,
            constraints={"no_retrieval": True, "inline_content": "A rough paragraph."},
        )
        result = run_planned_query(request, storage, principal="reader")

        self.assertTrue(result.skipped_retrieval)
        self.assertEqual(result.executed_modes, (RetrievalMode.NO_RETRIEVAL,))
        self.assertIsNone(result.retrieval)
        self.assertIsNone(result.ranking)
        self.assertIsNone(result.synthesis)
        self.assertIsNone(result.repair_trace)
        self.assertNotIn("retrieval_completed", _event_names(result.logs))

    def test_planned_query_keeps_required_repository_log_hook_behavior(self) -> None:
        with self.assertRaises(AttributeError):
            run_planned_query("hello", object())

    def test_orchestrated_query_logs_match_available_successful_query_expectations(self) -> None:
        storage = _indexed_public_repository()
        result = run_planned_query('"alpha evidence bridge"', storage, principal="reader")

        events_by_partition_operation = {
            (log.partition, log.operation_name, log.details.get("event_name"))
            for log in result.logs
        }

        for expectation in SUCCESSFUL_QUERY_LOG_EXPECTATIONS:
            self.assertTrue(
                any(
                    (
                        expectation.partition,
                        expectation.operation_name,
                        accepted_event,
                    )
                    in events_by_partition_operation
                    for accepted_event in expectation.accepted_events()
                ),
                f"missing expected log {expectation.partition.value}:{expectation.operation_name}:{expectation.event_name}",
            )

    def test_langgraph_compatible_runtime_uses_local_fallback_without_dependency(self) -> None:
        storage = _indexed_public_repository()
        adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=None)

        health = adapter.health_check(correlation_id="corr_orchestration_health")
        result = adapter.run_query(
            '"alpha evidence bridge"',
            storage,
            principal="reader",
            correlation_id="corr_orchestration_fallback",
        )

        self.assertEqual(health.status, OrchestrationStatus.DEGRADED)
        self.assertTrue(result.ok)
        self.assertTrue(result.details["fallback_used"])
        self.assertIsNotNone(result.planned_query)
        self.assertEqual(result.planned_query.executed_modes, (RetrievalMode.KEYWORD,))
        self.assertIn("orchestration_started", _event_names(result.logs))
        self.assertIn("orchestration_completed", _event_names(result.logs))
        self.assertEqual(result.to_dict()["runtime_name"], "LangGraph")
        self.assertEqual(result.to_dict()["details"]["executed_modes"], ("keyword",))

    def test_langgraph_compatible_runtime_invokes_injected_app(self) -> None:
        storage = _indexed_public_repository()
        app = FakeLangGraphApp()
        adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=app)

        health = adapter.health_check(correlation_id="corr_orchestration_ready")
        result = adapter.run_query(
            "Explain how sparse search and vector search support citation quality",
            storage,
            principal="reader",
            current_date=date(2026, 5, 21),
            correlation_id="corr_orchestration_app",
        )

        self.assertEqual(health.status, OrchestrationStatus.READY)
        self.assertTrue(result.ok)
        self.assertFalse(result.details["fallback_used"])
        self.assertEqual(len(app.payloads), 1)
        self.assertEqual(app.payloads[0]["correlation_id"], "corr_orchestration_app")
        self.assertEqual(result.planned_query.planning.plan.query_type, QueryType.SEMANTIC)

    def test_local_planned_query_graph_app_reports_ready(self) -> None:
        storage = _indexed_public_repository()
        adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=LocalPlannedQueryGraphApp())

        health = adapter.health_check(correlation_id="corr_orchestration_local_graph_ready")
        result = adapter.run_query(
            '"alpha evidence bridge"',
            storage,
            principal="reader",
            correlation_id="corr_orchestration_local_graph",
        )

        self.assertEqual(health.status, OrchestrationStatus.READY)
        self.assertTrue(result.ok)
        self.assertFalse(result.details["fallback_used"])
        self.assertEqual(result.planned_query.executed_modes, (RetrievalMode.KEYWORD,))

    def test_langgraph_compatible_runtime_falls_back_after_app_failure(self) -> None:
        storage = _indexed_public_repository()
        adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=FakeLangGraphApp(fail=True))

        result = adapter.run_query(
            '"alpha evidence bridge"',
            storage,
            principal="reader",
            correlation_id="corr_orchestration_app_failed",
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.details["fallback_used"])
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.details["fallback_runtime"], "local_planned_query")

    def test_langgraph_compatible_runtime_can_be_unavailable_without_fallback(self) -> None:
        storage = _indexed_public_repository()
        adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=None, allow_local_fallback=False)

        result = adapter.run_query(
            '"alpha evidence bridge"',
            storage,
            principal="reader",
            correlation_id="corr_orchestration_unavailable",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.health.status, OrchestrationStatus.UNAVAILABLE)
        self.assertIsNotNone(result.error)

    def test_langgraph_runtime_error_path_preserves_optional_save_error_hook_behavior(self) -> None:
        repository = SaveErrorOnlyRepository()
        adapter = LangGraphCompatibleOrchestrationAdapter(graph_app=FakeLangGraphApp(fail=True), allow_local_fallback=False)

        result = adapter.run_query(
            '"alpha evidence bridge"',
            repository,
            principal="reader",
            correlation_id="corr_orchestration_no_fallback_error",
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.health.status, OrchestrationStatus.READY)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.error_message, "graph app failed")
        self.assertEqual(result.error.details, {"runtime_name": "LangGraph", "exception_type": "RuntimeError"})
        self.assertEqual(repository.errors, [result.error])
        self.assertEqual(result.details["fallback_used"], False)
        self.assertEqual(_event_names(result.logs), ["orchestration_started"])


def _event_names(logs) -> list[str]:
    return [log.details.get("event_name") for log in logs]


if __name__ == "__main__":
    unittest.main()

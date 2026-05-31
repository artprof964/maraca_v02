import unittest

from planning import (
    classify_query,
    create_retrieval_plan,
    create_retrieval_request,
    plan_request,
    select_retrieval_modes,
    set_retrieval_budget,
)
from shared import (
    LogEventType,
    OutputIntent,
    QueryType,
    RequiredFreshness,
    RetrievalMode,
    RetrievalRequest,
    RiskLevel,
    ValidationCriterion,
)


class PlanningTests(unittest.TestCase):
    def test_create_retrieval_request_normalizes_query(self) -> None:
        request = create_retrieval_request("  Find   exact   phrase  ")

        self.assertIsInstance(request, RetrievalRequest)
        self.assertEqual(request.normalized_query, "Find exact phrase")
        self.assertEqual(request.user_query, "  Find   exact   phrase  ")

    def test_exact_query_routes_to_keyword_retrieval(self) -> None:
        request = create_retrieval_request('"incident-42"')

        self.assertEqual(classify_query(request), QueryType.EXACT)
        self.assertEqual(select_retrieval_modes(QueryType.EXACT, request), [RetrievalMode.KEYWORD])

    def test_semantic_query_routes_to_vector_and_hybrid(self) -> None:
        request = create_retrieval_request("Explain how hybrid retrieval improves citation quality")
        result = plan_request(request, correlation_id="corr_test")

        self.assertEqual(result.plan.query_type, QueryType.SEMANTIC)
        self.assertEqual(result.plan.selected_modes, [RetrievalMode.VECTOR, RetrievalMode.HYBRID])
        self.assertIn("semantic", result.plan.plan_reason or "")
        self.assertFalse(result.direct_response.should_respond_directly)

    def test_uncertain_query_falls_back_to_hybrid(self) -> None:
        result = plan_request("project alpha")

        self.assertEqual(result.plan.query_type, QueryType.MIXED)
        self.assertEqual(result.plan.selected_modes, [RetrievalMode.HYBRID])
        self.assertIn("conservatively", result.plan.plan_reason or "")
        self.assertGreater(result.plan.max_repair_attempts, 0)

    def test_no_retrieval_path_sets_direct_response_metadata_without_synthesis(self) -> None:
        request = create_retrieval_request(
            "Format this paragraph",
            output_intent=OutputIntent.SUMMARY,
            constraints={"no_retrieval": True, "inline_content": "A rough paragraph."},
        )
        result = plan_request(request)

        self.assertEqual(result.plan.selected_modes, [RetrievalMode.NO_RETRIEVAL])
        self.assertEqual(result.plan.retrieval_budget["top_k"], 0)
        self.assertEqual(result.plan.required_validations, [])
        self.assertTrue(result.direct_response.should_respond_directly)
        self.assertTrue(result.direct_response.metadata["synthesis_deferred"])
        self.assertFalse(result.direct_response.metadata["requires_retrieval"])
        self.assertEqual(result.trace.selected_modes, (RetrievalMode.NO_RETRIEVAL,))
        self.assertEqual(result.trace.retrieval_budget["top_k"], 0)
        self.assertEqual(result.trace.max_repair_attempts, 0)

    def test_greeting_with_source_backed_question_still_uses_retrieval(self) -> None:
        result = plan_request("Hello, what is the latest source status?")

        self.assertEqual(result.plan.query_type, QueryType.FRESH_DATA)
        self.assertEqual(result.plan.selected_modes, [RetrievalMode.HYBRID])
        self.assertFalse(result.direct_response.should_respond_directly)

    def test_transform_wording_without_inline_content_does_not_bypass_retrieval(self) -> None:
        request = create_retrieval_request("Rewrite this policy from approved sources")
        result = plan_request(request)

        self.assertEqual(result.plan.selected_modes, [RetrievalMode.HYBRID])
        self.assertFalse(result.direct_response.should_respond_directly)

    def test_budget_overrides_are_bounded_and_carried_to_repair_fields(self) -> None:
        request = create_retrieval_request(
            "latest architecture decision",
            required_freshness=RequiredFreshness.RECENT,
            risk_level=RiskLevel.MEDIUM,
            constraints={
                "top_k": 100,
                "latency_target_ms": 900,
                "cost_target": 0.08,
                "max_repair_attempts": 99,
            },
        )
        result = plan_request(request)

        self.assertEqual(result.plan.query_type, QueryType.FRESH_DATA)
        self.assertEqual(result.plan.retrieval_budget["top_k"], 20)
        self.assertEqual(result.plan.retrieval_budget["latency_target_ms"], 900)
        self.assertEqual(result.plan.retrieval_budget["cost_target"], 0.08)
        self.assertEqual(result.plan.retrieval_budget["max_repair_attempts"], 3)
        self.assertEqual(result.plan.repair_attempt, 0)
        self.assertEqual(result.plan.max_repair_attempts, 3)
        self.assertEqual(result.plan.previous_actions, [])

    def test_create_retrieval_plan_adds_freshness_validation_when_required(self) -> None:
        request = create_retrieval_request("current source status", required_freshness=RequiredFreshness.RECENT)
        plan = create_retrieval_plan(request)

        self.assertIn(ValidationCriterion.FRESHNESS, plan.required_validations)
        self.assertIn(ValidationCriterion.ACCESS, plan.required_validations)

    def test_planner_logs_expected_decision_events(self) -> None:
        result = plan_request("Compare RAG and CAG")

        event_names = [log.details["event_name"] for log in result.logs]
        self.assertIn("query_classified", event_names)
        self.assertIn("retrieval_modes_selected", event_names)
        self.assertIn("retrieval_budget_set", event_names)
        self.assertIn("retrieval_plan_created", event_names)
        self.assertTrue(all(log.event_type is LogEventType.DECISION for log in result.logs))
        self.assertTrue(all(log.partition.value == "planning" for log in result.logs))
        logs_by_event = {log.details["event_name"]: log for log in result.logs}
        self.assertEqual(logs_by_event["query_classified"].operation_name, "classify_query")
        self.assertEqual(logs_by_event["retrieval_modes_selected"].operation_name, "select_retrieval_modes")
        self.assertEqual(logs_by_event["retrieval_budget_set"].operation_name, "set_retrieval_budget")
        self.assertEqual(logs_by_event["retrieval_plan_created"].operation_name, "create_retrieval_plan")
        self.assertEqual(
            logs_by_event["retrieval_plan_created"].details["selected_modes"],
            [mode.value for mode in result.plan.selected_modes],
        )
        self.assertEqual(logs_by_event["retrieval_plan_created"].details["plan_reason"], result.plan.plan_reason)

    def test_set_retrieval_budget_for_direct_route_is_zero_top_k(self) -> None:
        budget = set_retrieval_budget(QueryType.MIXED, [RetrievalMode.NO_RETRIEVAL])

        self.assertEqual(budget["top_k"], 0)
        self.assertEqual(budget["max_repair_attempts"], 0)


if __name__ == "__main__":
    unittest.main()

"""Dependency-free planner baseline for routing retrieval requests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Iterable

from shared.contracts import LogEvent, LogEventType, Partition, new_correlation_id
from shared.policies import create_success_log_event
from shared.records import (
    OutputIntent,
    PlanFallbackAction,
    QueryType,
    RequiredFreshness,
    RepairAction,
    RetrievalMode,
    RetrievalPlan,
    RetrievalRequest,
    RiskLevel,
    ValidationRecord,
    ValidationCriterion,
    ValidationStatus,
)

try:
    from ranking import RankingConfig, RankingResult, select_ranked_evidence
    from retrieval import (
        HybridSearchResult,
        apply_access_filter,
        merge_evidence_candidates,
        run_graph_retrieval,
        run_hybrid_search,
        run_keyword_retrieval,
        run_vector_retrieval,
    )
    from storage import InMemoryStorageRepository
    from synthesis import SynthesisResult, generate_answer
    from validation import ValidationResult, validate_answer_evidence, validate_claim_support
except ImportError:  # pragma: no cover - keeps planner-only imports isolated.
    HybridSearchResult = object  # type: ignore[assignment, misc]
    InMemoryStorageRepository = object  # type: ignore[assignment, misc]
    RankingConfig = object  # type: ignore[assignment, misc]
    RankingResult = object  # type: ignore[assignment, misc]
    SynthesisResult = object  # type: ignore[assignment, misc]
    ValidationResult = object  # type: ignore[assignment, misc]
    apply_access_filter = None  # type: ignore[assignment]
    generate_answer = None  # type: ignore[assignment]
    merge_evidence_candidates = None  # type: ignore[assignment]
    run_hybrid_search = None  # type: ignore[assignment]
    run_graph_retrieval = None  # type: ignore[assignment]
    run_keyword_retrieval = None  # type: ignore[assignment]
    run_vector_retrieval = None  # type: ignore[assignment]
    select_ranked_evidence = None  # type: ignore[assignment]
    validate_answer_evidence = None  # type: ignore[assignment]
    validate_claim_support = None  # type: ignore[assignment]

PARTITION = "planning"

DEFAULT_TOP_K = 6
DEFAULT_LATENCY_TARGET_MS = 750
DEFAULT_COST_TARGET = 0.02
DEFAULT_MAX_REPAIR_ATTEMPTS = 1
MAX_TOP_K = 20
MAX_REPAIR_ATTEMPTS = 3

_EXACT_MARKERS = (
    '"',
    "'",
    "exact",
    "verbatim",
    "literal",
    "id:",
    "error code",
    "ticket",
    "sku",
)
_SEMANTIC_MARKERS = (
    "why",
    "how",
    "explain",
    "summarize",
    "compare",
    "relationship",
    "tradeoff",
    "approach",
    "concept",
)
_FRESH_MARKERS = ("current", "latest", "recent", "today", "now", "this week", "as of")
_TRANSFORM_DIRECT_MARKERS = (
    "format this",
    "rewrite this",
    "rephrase this",
    "translate this",
    "make this",
    "shorten this",
    "fix grammar",
)
_CONVERSATIONAL_DIRECT_MARKERS = (
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
)


@dataclass(frozen=True, slots=True)
class DirectResponseDecision:
    """Planner metadata for requests that should not enter retrieval."""

    should_respond_directly: bool
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlannerTrace:
    """Traceable planner decisions without evidence or synthesis output."""

    request_id: str
    query_type: QueryType
    selected_modes: tuple[RetrievalMode, ...]
    plan_reason: str
    direct_response: DirectResponseDecision
    retrieval_budget: dict[str, Any]
    repair_attempt: int = 0
    max_repair_attempts: int = 0
    fallback_actions: tuple[PlanFallbackAction, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "query_type": self.query_type.value,
            "selected_modes": [mode.value for mode in self.selected_modes],
            "plan_reason": self.plan_reason,
            "direct_response": {
                "should_respond_directly": self.direct_response.should_respond_directly,
                "reason": self.direct_response.reason,
                "metadata": dict(self.direct_response.metadata),
            },
            "retrieval_budget": dict(self.retrieval_budget),
            "repair_attempt": self.repair_attempt,
            "max_repair_attempts": self.max_repair_attempts,
            "fallback_actions": [action.value for action in self.fallback_actions],
        }


@dataclass(frozen=True, slots=True)
class PlanningResult:
    """Retrieval plan plus emitted planner logs and decision trace."""

    request: RetrievalRequest
    plan: RetrievalPlan
    trace: PlannerTrace
    logs: tuple[LogEvent, ...] = ()
    direct_response: DirectResponseDecision | None = None


@dataclass(frozen=True, slots=True)
class RepairExecutionTrace:
    """Observable bounded repair-loop state for a planned query result."""

    validation_status: ValidationStatus
    repair_action: RepairAction
    repair_attempt: int
    max_repair_attempts: int
    previous_actions: tuple[str, ...] = ()
    fallback_actions: tuple[PlanFallbackAction, ...] = ()
    exhausted: bool = False
    retrieval_rerun_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_status": self.validation_status.value,
            "repair_action": self.repair_action.value,
            "repair_attempt": self.repair_attempt,
            "max_repair_attempts": self.max_repair_attempts,
            "previous_actions": list(self.previous_actions),
            "fallback_actions": [action.value for action in self.fallback_actions],
            "exhausted": self.exhausted,
            "retrieval_rerun_requested": self.retrieval_rerun_requested,
        }


@dataclass(frozen=True, slots=True)
class PlannedQueryResult:
    """Planner-to-retrieval smoke flow with downstream trace continuity."""

    planning: PlanningResult
    retrieval: HybridSearchResult | None = None
    ranking: RankingResult | None = None
    validation: ValidationResult | None = None
    synthesis: SynthesisResult | None = None
    executed_modes: tuple[RetrievalMode, ...] = ()
    repair_trace: RepairExecutionTrace | None = None
    logs: tuple[LogEvent, ...] = ()
    errors: tuple[Any, ...] = ()

    @property
    def skipped_retrieval(self) -> bool:
        return self.retrieval is None


def create_retrieval_request(
    user_query: str,
    *,
    normalized_query: str | None = None,
    user_context: dict[str, Any] | None = None,
    required_freshness: RequiredFreshness = RequiredFreshness.NONE,
    risk_level: RiskLevel = RiskLevel.LOW,
    output_intent: OutputIntent = OutputIntent.ANSWER,
    constraints: dict[str, Any] | None = None,
) -> RetrievalRequest:
    """Create a baseline request record with conservative normalization."""

    return RetrievalRequest(
        user_query=user_query,
        normalized_query=normalized_query or normalize_query(user_query),
        user_context=dict(user_context or {}),
        required_freshness=required_freshness,
        risk_level=risk_level,
        output_intent=output_intent,
        constraints=dict(constraints or {}),
    )


def normalize_query(query: str) -> str:
    """Normalize whitespace while preserving user wording for exact routing."""

    return " ".join(query.strip().split())


def classify_query(request_or_query: RetrievalRequest | str) -> QueryType:
    """Classify a query with deterministic conservative routing heuristics."""

    request = _coerce_request(request_or_query)
    query = (request.normalized_query or normalize_query(request.user_query)).lower()
    constraints = request.constraints

    if request.required_freshness in {RequiredFreshness.RECENT, RequiredFreshness.DATE_BOUNDED, RequiredFreshness.REAL_TIME}:
        return QueryType.FRESH_DATA
    if any(marker in query for marker in _FRESH_MARKERS):
        return QueryType.FRESH_DATA
    if request.risk_level is RiskLevel.HIGH:
        return QueryType.HIGH_RISK
    if _truthy(constraints.get("graph_required")) or any(marker in query for marker in ("relationship between", "connected to", "depends on")):
        return QueryType.GRAPH
    if any(marker in query for marker in ("multi-hop", "across sources", "chain of", "path from")):
        return QueryType.MULTI_HOP
    if any(marker in query for marker in _EXACT_MARKERS):
        return QueryType.EXACT
    if any(marker in query for marker in _SEMANTIC_MARKERS):
        return QueryType.SEMANTIC
    return QueryType.MIXED


def select_retrieval_modes(
    query_type: QueryType,
    request: RetrievalRequest | None = None,
) -> list[RetrievalMode]:
    """Select retrieval modes, falling back to hybrid when uncertain."""

    if request is not None and _is_direct_response_request(request):
        return [RetrievalMode.NO_RETRIEVAL]
    if query_type is QueryType.EXACT:
        return [RetrievalMode.KEYWORD]
    if query_type is QueryType.SEMANTIC:
        return [RetrievalMode.VECTOR, RetrievalMode.HYBRID]
    if query_type is QueryType.GRAPH:
        return [RetrievalMode.GRAPH, RetrievalMode.HYBRID]
    if query_type is QueryType.FRESH_DATA:
        return [RetrievalMode.HYBRID]
    if query_type is QueryType.HIGH_RISK:
        return [RetrievalMode.HYBRID]
    if query_type is QueryType.MULTI_HOP:
        return [RetrievalMode.HYBRID, RetrievalMode.ITERATIVE]
    return [RetrievalMode.HYBRID]


def set_retrieval_budget(
    query_type: QueryType,
    selected_modes: Iterable[RetrievalMode],
    *,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set bounded retrieval budget fields with validated caller overrides."""

    modes = tuple(selected_modes)
    supplied = dict(constraints or {})
    if modes == (RetrievalMode.NO_RETRIEVAL,):
        top_k = 0
        latency_target_ms = _positive_int(supplied.get("latency_target_ms"), 100)
        cost_target = _positive_float(supplied.get("cost_target"), 0.0)
        max_repair_attempts = 0
    else:
        top_k_default = _default_top_k(query_type)
        latency_default = _default_latency_target_ms(query_type)
        cost_default = _default_cost_target(query_type)
        repair_default = _default_max_repair_attempts(query_type)
        top_k = min(_positive_int(supplied.get("top_k"), top_k_default), MAX_TOP_K)
        latency_target_ms = _positive_int(supplied.get("latency_target_ms"), latency_default)
        cost_target = _positive_float(supplied.get("cost_target"), cost_default)
        max_repair_attempts = min(
            _positive_int(supplied.get("max_repair_attempts"), repair_default),
            MAX_REPAIR_ATTEMPTS,
        )

    return {
        "top_k": top_k,
        "latency_target_ms": latency_target_ms,
        "cost_target": cost_target,
        "max_repair_attempts": max_repair_attempts,
    }


def create_retrieval_plan(
    request: RetrievalRequest,
    *,
    query_type: QueryType | None = None,
    selected_modes: Iterable[RetrievalMode] | None = None,
    retrieval_budget: dict[str, Any] | None = None,
) -> RetrievalPlan:
    """Create a shared RetrievalPlan record with bounded repair-loop fields."""

    resolved_query_type = query_type or classify_query(request)
    modes = list(selected_modes or select_retrieval_modes(resolved_query_type, request))
    budget = dict(retrieval_budget or set_retrieval_budget(resolved_query_type, modes, constraints=request.constraints))
    direct = modes == [RetrievalMode.NO_RETRIEVAL]
    fallback_actions = [] if direct else _fallback_actions(resolved_query_type)
    reason = _plan_reason(resolved_query_type, modes, request, direct=direct)

    return RetrievalPlan(
        request_id=request.request_id,
        query_type=resolved_query_type,
        selected_modes=modes,
        retrieval_budget=budget,
        repair_attempt=0,
        max_repair_attempts=budget["max_repair_attempts"],
        previous_actions=[],
        required_validations=[] if direct else _required_validations(request),
        fallback_actions=fallback_actions,
        plan_reason=reason,
    )


def plan_request(
    request_or_query: RetrievalRequest | str,
    *,
    correlation_id: str | None = None,
) -> PlanningResult:
    """Classify, route, budget, and trace a request without running retrieval."""

    request = _coerce_request(request_or_query)
    corr = correlation_id or new_correlation_id("planning")

    query_type = classify_query(request)
    classification_reason = _classification_reason(query_type, request)
    classification_log = _decision_log(
        corr,
        "classify_query",
        "query_classified",
        "Classified query for retrieval planning.",
        request.request_id,
        {
            "request_id": request.request_id,
            "query_type": query_type.value,
            "classification_reason": classification_reason,
            "conservative_fallback": query_type is QueryType.MIXED,
        },
    )

    modes = select_retrieval_modes(query_type, request)
    direct_response = _direct_response_decision(request, modes)
    mode_log = _decision_log(
        corr,
        "select_retrieval_modes",
        "retrieval_modes_selected",
        "Selected retrieval modes for request.",
        request.request_id,
        {
            "request_id": request.request_id,
            "query_type": query_type.value,
            "selected_modes": [mode.value for mode in modes],
            "direct_response": direct_response.should_respond_directly,
            "selection_reason": direct_response.reason if direct_response.should_respond_directly else "source-backed route selected",
        },
    )

    budget = set_retrieval_budget(query_type, modes, constraints=request.constraints)
    budget_log = _decision_log(
        corr,
        "set_retrieval_budget",
        "retrieval_budget_set",
        "Set bounded retrieval budget.",
        request.request_id,
        {
            "request_id": request.request_id,
            "retrieval_budget": dict(budget),
            "repair_attempt": 0,
            "max_repair_attempts": budget["max_repair_attempts"],
        },
    )

    plan = create_retrieval_plan(
        request,
        query_type=query_type,
        selected_modes=modes,
        retrieval_budget=budget,
    )
    plan_log = _decision_log(
        corr,
        "create_retrieval_plan",
        "retrieval_plan_created",
        "Created retrieval plan with traceable routing reason.",
        plan.plan_id,
        {
            "request_id": request.request_id,
            "plan_id": plan.plan_id,
            "query_type": query_type.value,
            "selected_modes": [mode.value for mode in modes],
            "plan_reason": plan.plan_reason,
            "repair_attempt": plan.repair_attempt,
            "max_repair_attempts": plan.max_repair_attempts,
            "fallback_actions": [action.value for action in plan.fallback_actions],
            "direct_response": direct_response.should_respond_directly,
        },
    )
    trace = PlannerTrace(
        request_id=request.request_id,
        query_type=query_type,
        selected_modes=tuple(modes),
        plan_reason=plan.plan_reason or "",
        direct_response=direct_response,
        retrieval_budget=budget,
        repair_attempt=plan.repair_attempt,
        max_repair_attempts=plan.max_repair_attempts,
        fallback_actions=tuple(plan.fallback_actions),
    )
    return PlanningResult(
        request=request,
        plan=plan,
        trace=trace,
        logs=(classification_log, mode_log, budget_log, plan_log),
        direct_response=direct_response,
    )


def run_planned_query(
    request_or_query: RetrievalRequest | str,
    repository: InMemoryStorageRepository,
    *,
    principal: str | None = None,
    principal_scopes: Iterable[str] = (),
    use_case: str = "general",
    ranking_config: RankingConfig | None = None,
    current_date: date | None = None,
    correlation_id: str | None = None,
) -> PlannedQueryResult:
    """Plan, retrieve, rank, and synthesize while preserving one request trace."""

    corr = correlation_id or new_correlation_id("planned_query")
    planning = plan_request(request_or_query, correlation_id=corr)
    for log in planning.logs:
        repository.add_log(log)

    logs: list[LogEvent] = list(planning.logs)
    errors: list[Any] = []

    if planning.direct_response and planning.direct_response.should_respond_directly:
        return PlannedQueryResult(
            planning=planning,
            executed_modes=(RetrievalMode.NO_RETRIEVAL,),
            logs=tuple(logs),
            errors=tuple(errors),
        )

    query = planning.request.normalized_query or normalize_query(planning.request.user_query)
    top_k = int(planning.plan.retrieval_budget.get("top_k", DEFAULT_TOP_K))
    retrieval, executed_modes = _execute_plan_retrieval(
        query,
        planning,
        repository,
        principal=principal,
        principal_scopes=principal_scopes,
        use_case=use_case,
        top_k=top_k,
        correlation_id=corr,
    )
    logs.extend(retrieval.logs)
    errors.extend(retrieval.errors)

    ranking = select_ranked_evidence(
        query,
        retrieval.candidates,
        top_k=top_k,
        config=ranking_config,
        repository=repository,
        correlation_id=corr,
    )
    logs.extend(ranking.logs)
    errors.extend(ranking.errors)

    validation = validate_answer_evidence(
        query,
        ranking.candidates,
        required_validations=planning.plan.required_validations,
        required_freshness=planning.request.required_freshness is not RequiredFreshness.NONE,
        current_date=current_date,
        max_repair_attempts=planning.plan.max_repair_attempts,
        repair_attempt=planning.plan.repair_attempt,
        repository=repository,
        correlation_id=corr,
    )
    logs.extend(validation.logs)
    errors.extend(validation.errors)
    repair_trace = _repair_execution_trace(planning, validation.validation)
    synthesis_evidence = (
        validation.approved_evidence
        if validation.validation.validation_status is ValidationStatus.PASS
        else ()
    )

    synthesis = generate_answer(
        query,
        synthesis_evidence,
        ranked_evidence=ranking.ranked_evidence,
        validation=validation.validation,
        repository=repository,
        current_date=current_date,
        correlation_id=corr,
    )
    if validation.validation.validation_status is ValidationStatus.PASS and synthesis.claims:
        claim_support = validate_claim_support(synthesis.claims, validation.approved_evidence)
        for claim in claim_support.claims:
            if hasattr(repository, "save_claim_record"):
                repository.save_claim_record(claim)
        synthesis = replace(
            synthesis,
            claims=claim_support.claims,
            answer=replace(synthesis.answer, claim_records=list(claim_support.claims)),
        )
    logs.extend(synthesis.logs)
    errors.extend(synthesis.errors)

    return PlannedQueryResult(
        planning=planning,
        retrieval=retrieval,
        ranking=ranking,
        validation=validation,
        synthesis=synthesis,
        executed_modes=executed_modes,
        repair_trace=repair_trace,
        logs=tuple(logs),
        errors=tuple(errors),
    )


def _coerce_request(request_or_query: RetrievalRequest | str) -> RetrievalRequest:
    if isinstance(request_or_query, RetrievalRequest):
        if request_or_query.normalized_query is not None:
            return request_or_query
        return RetrievalRequest(
            user_query=request_or_query.user_query,
            normalized_query=normalize_query(request_or_query.user_query),
            user_context=dict(request_or_query.user_context),
            required_freshness=request_or_query.required_freshness,
            risk_level=request_or_query.risk_level,
            output_intent=request_or_query.output_intent,
            constraints=dict(request_or_query.constraints),
            request_id=request_or_query.request_id,
        )
    return create_retrieval_request(request_or_query)


def _is_direct_response_request(request: RetrievalRequest) -> bool:
    if _truthy(request.constraints.get("no_retrieval")) or _truthy(request.constraints.get("direct_response")):
        return True
    query = (request.normalized_query or request.user_query).lower()
    if request.output_intent in {OutputIntent.EXTRACTION, OutputIntent.SUMMARY} and _has_inline_content(request):
        return True
    if query.strip(" .!?") in _CONVERSATIONAL_DIRECT_MARKERS:
        return True
    if _has_inline_content(request) or ":" in query:
        return any(query.startswith(marker) for marker in _TRANSFORM_DIRECT_MARKERS)
    return False


def _has_inline_content(request: RetrievalRequest) -> bool:
    return bool(request.constraints.get("inline_content") or request.user_context.get("inline_content"))


def _direct_response_decision(request: RetrievalRequest, modes: list[RetrievalMode]) -> DirectResponseDecision:
    direct = modes == [RetrievalMode.NO_RETRIEVAL]
    reason = "request can be handled without source retrieval" if direct else "retrieval required before answer synthesis"
    return DirectResponseDecision(
        should_respond_directly=direct,
        reason=reason,
        metadata={
            "request_id": request.request_id,
            "synthesis_deferred": True,
            "requires_retrieval": not direct,
        },
    )


def _repair_execution_trace(
    planning: PlanningResult,
    validation: ValidationRecord,
) -> RepairExecutionTrace | None:
    if validation.validation_status not in {ValidationStatus.REPAIR_NEEDED, ValidationStatus.FAIL}:
        return None

    repair_attempt = planning.plan.repair_attempt
    max_repair_attempts = planning.plan.max_repair_attempts
    exhausted = (
        validation.validation_status is ValidationStatus.FAIL
        or validation.repair_action is RepairAction.STOP
        or repair_attempt >= max_repair_attempts
    )
    return RepairExecutionTrace(
        validation_status=validation.validation_status,
        repair_action=validation.repair_action,
        repair_attempt=repair_attempt,
        max_repair_attempts=max_repair_attempts,
        previous_actions=tuple(planning.plan.previous_actions),
        fallback_actions=tuple(planning.plan.fallback_actions),
        exhausted=exhausted,
        retrieval_rerun_requested=False,
    )


def _required_validations(request: RetrievalRequest) -> list[ValidationCriterion]:
    validations = [
        ValidationCriterion.RELEVANCE,
        ValidationCriterion.SUFFICIENCY,
        ValidationCriterion.CITATION,
        ValidationCriterion.ACCESS,
        ValidationCriterion.CONTRADICTION,
    ]
    query = (request.normalized_query or request.user_query).lower()
    if request.required_freshness is not RequiredFreshness.NONE or any(marker in query for marker in _FRESH_MARKERS):
        validations.append(ValidationCriterion.FRESHNESS)
    return validations


def _fallback_actions(query_type: QueryType) -> list[PlanFallbackAction]:
    if query_type is QueryType.EXACT:
        return [PlanFallbackAction.ADD_VECTOR, PlanFallbackAction.CLARIFY]
    if query_type is QueryType.SEMANTIC:
        return [PlanFallbackAction.ADD_KEYWORD, PlanFallbackAction.CLARIFY]
    if query_type is QueryType.GRAPH:
        return [PlanFallbackAction.EXPAND_GRAPH, PlanFallbackAction.ADD_VECTOR, PlanFallbackAction.CLARIFY]
    if query_type is QueryType.MULTI_HOP:
        return [PlanFallbackAction.REWRITE, PlanFallbackAction.ADD_KEYWORD, PlanFallbackAction.CLARIFY]
    return [PlanFallbackAction.ADD_KEYWORD, PlanFallbackAction.ADD_VECTOR, PlanFallbackAction.CLARIFY]


def _plan_reason(
    query_type: QueryType,
    modes: list[RetrievalMode],
    request: RetrievalRequest,
    *,
    direct: bool,
) -> str:
    if direct:
        return "No retrieval selected because the request is conversational, formatting-only, or explicitly direct."
    if query_type is QueryType.MIXED:
        return "Uncertain classification routed conservatively to hybrid retrieval."
    if request.risk_level is RiskLevel.HIGH:
        return "High-risk request routed to source-backed retrieval with validation."
    return f"{query_type.value} query routed to {', '.join(mode.value for mode in modes)} retrieval."


def _classification_reason(query_type: QueryType, request: RetrievalRequest) -> str:
    if query_type is QueryType.MIXED:
        return "no strong exact, semantic, graph, freshness, or risk signal found"
    if query_type is QueryType.FRESH_DATA:
        return "freshness requirement or current-data phrasing detected"
    if query_type is QueryType.HIGH_RISK:
        return "high risk level requires source-backed retrieval"
    return f"{query_type.value} routing signal detected"


def _default_top_k(query_type: QueryType) -> int:
    if query_type is QueryType.EXACT:
        return 5
    if query_type in {QueryType.FRESH_DATA, QueryType.HIGH_RISK, QueryType.MULTI_HOP}:
        return 10
    if query_type is QueryType.MIXED:
        return 8
    return DEFAULT_TOP_K


def _default_latency_target_ms(query_type: QueryType) -> int:
    if query_type is QueryType.EXACT:
        return 400
    if query_type in {QueryType.FRESH_DATA, QueryType.HIGH_RISK, QueryType.MULTI_HOP}:
        return 1200
    return DEFAULT_LATENCY_TARGET_MS


def _default_cost_target(query_type: QueryType) -> float:
    if query_type is QueryType.EXACT:
        return 0.01
    if query_type in {QueryType.FRESH_DATA, QueryType.HIGH_RISK, QueryType.MULTI_HOP}:
        return 0.05
    return DEFAULT_COST_TARGET


def _default_max_repair_attempts(query_type: QueryType) -> int:
    if query_type in {QueryType.FRESH_DATA, QueryType.HIGH_RISK, QueryType.MULTI_HOP}:
        return 2
    return DEFAULT_MAX_REPAIR_ATTEMPTS


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _decision_log(
    correlation_id: str,
    operation_name: str,
    event_name: str,
    message: str,
    output_reference: str,
    details: dict[str, Any],
) -> LogEvent:
    merged = dict(details)
    merged.setdefault("event_name", event_name)
    return LogEvent(
        correlation_id=correlation_id,
        partition=Partition.PLANNING,
        event_type=LogEventType.DECISION,
        operation_name=operation_name,
        message=message,
        output_reference=output_reference,
        details=merged,
    )


def _execute_plan_retrieval(
    query: str,
    planning: PlanningResult,
    repository: InMemoryStorageRepository,
    *,
    principal: str | None,
    principal_scopes: Iterable[str],
    use_case: str,
    top_k: int,
    correlation_id: str,
) -> tuple[HybridSearchResult, tuple[RetrievalMode, ...]]:
    modes = tuple(planning.plan.selected_modes)
    if RetrievalMode.GRAPH in modes:
        graph_result = run_graph_retrieval(
            query,
            repository,
            request_id=planning.request.request_id,
            top_k=top_k,
            correlation_id=correlation_id,
        )
        access = apply_access_filter(
            graph_result.candidates,
            repository,
            principal=principal,
            principal_scopes=principal_scopes,
            use_case=use_case,
            correlation_id=correlation_id,
        )
        graph_candidates = merge_evidence_candidates(access.candidates, top_k=top_k)
        if graph_candidates or RetrievalMode.HYBRID not in modes:
            log = create_success_log_event(
                correlation_id=correlation_id,
                partition=Partition.RETRIEVAL,
                operation_name="run_retrieval",
                event_name="retrieval_completed",
                message="Completed graph retrieval.",
                output_reference=",".join(candidate.evidence_id for candidate in graph_candidates) or None,
                details={
                    "query": query,
                    "request_id": planning.request.request_id,
                    "input_count": len(graph_result.candidates),
                    "allowed_count": len(access.candidates),
                    "merged_count": len(graph_candidates),
                    "excluded_count": access.excluded_count,
                    "modes": [RetrievalMode.GRAPH.value],
                    "graph_degraded": graph_result.degraded,
                },
            )
            repository.add_log(log)
            return (
                HybridSearchResult(
                    candidates=graph_candidates,
                    logs=(*graph_result.logs, *access.logs, log),
                    errors=access.errors,
                    excluded_count=access.excluded_count,
                ),
                (RetrievalMode.GRAPH,),
            )

        text_result = run_hybrid_search(
            query,
            repository,
            request_id=planning.request.request_id,
            principal=principal,
            principal_scopes=principal_scopes,
            use_case=use_case,
            top_k=top_k,
            correlation_id=correlation_id,
        )
        return (
            HybridSearchResult(
                candidates=text_result.candidates,
                logs=(*graph_result.logs, *access.logs, *text_result.logs),
                errors=(*access.errors, *text_result.errors),
                excluded_count=access.excluded_count + text_result.excluded_count,
            ),
            (RetrievalMode.GRAPH, RetrievalMode.HYBRID),
        )

    if RetrievalMode.HYBRID in modes:
        return (
            run_hybrid_search(
                query,
                repository,
                request_id=planning.request.request_id,
                principal=principal,
                principal_scopes=principal_scopes,
                use_case=use_case,
                top_k=top_k,
                correlation_id=correlation_id,
            ),
            (RetrievalMode.HYBRID,),
        )
    if RetrievalMode.KEYWORD in modes:
        return (
            _run_single_mode_retrieval(
                query,
                repository,
                mode=RetrievalMode.KEYWORD,
                request_id=planning.request.request_id,
                principal=principal,
                principal_scopes=principal_scopes,
                use_case=use_case,
                top_k=top_k,
                correlation_id=correlation_id,
            ),
            (RetrievalMode.KEYWORD,),
        )
    if RetrievalMode.VECTOR in modes:
        return (
            _run_single_mode_retrieval(
                query,
                repository,
                mode=RetrievalMode.VECTOR,
                request_id=planning.request.request_id,
                principal=principal,
                principal_scopes=principal_scopes,
                use_case=use_case,
                top_k=top_k,
                correlation_id=correlation_id,
            ),
            (RetrievalMode.VECTOR,),
        )

    return (
        run_hybrid_search(
            query,
            repository,
            request_id=planning.request.request_id,
            principal=principal,
            principal_scopes=principal_scopes,
            use_case=use_case,
            top_k=top_k,
            correlation_id=correlation_id,
        ),
        (RetrievalMode.HYBRID,),
    )


def _run_single_mode_retrieval(
    query: str,
    repository: InMemoryStorageRepository,
    *,
    mode: RetrievalMode,
    request_id: str,
    principal: str | None,
    principal_scopes: Iterable[str],
    use_case: str,
    top_k: int,
    correlation_id: str,
) -> HybridSearchResult:
    if mode is RetrievalMode.KEYWORD:
        raw_candidates = run_keyword_retrieval(query, repository, request_id=request_id, top_k=top_k)
    else:
        raw_candidates = run_vector_retrieval(query, repository, request_id=request_id, top_k=top_k)

    access = apply_access_filter(
        raw_candidates,
        repository,
        principal=principal,
        principal_scopes=principal_scopes,
        use_case=use_case,
        correlation_id=correlation_id,
    )
    merged = merge_evidence_candidates(access.candidates, top_k=top_k)
    log = create_success_log_event(
        correlation_id=correlation_id,
        partition=Partition.RETRIEVAL,
        operation_name="run_retrieval",
        event_name="retrieval_completed",
        message=f"Completed {mode.value} retrieval.",
        output_reference=",".join(candidate.evidence_id for candidate in merged) or None,
        details={
            "query": query,
            "request_id": request_id,
            "input_count": len(raw_candidates),
            "allowed_count": len(access.candidates),
            "merged_count": len(merged),
            "excluded_count": access.excluded_count,
            "modes": [mode.value],
        },
    )
    repository.add_log(log)
    return HybridSearchResult(
        candidates=merged,
        logs=(*access.logs, log),
        errors=access.errors,
        excluded_count=access.excluded_count,
    )


from .orchestration_runtime import (
    LangGraphCompatibleOrchestrationAdapter,
    LocalPlannedQueryGraphApp,
    OrchestrationCapability,
    OrchestrationHealthCheck,
    OrchestrationRunResult,
    OrchestrationRuntimeAdapter,
    OrchestrationRuntimeConfig,
    OrchestrationStatus,
)

__all__ = [
    "PARTITION",
    "DirectResponseDecision",
    "LangGraphCompatibleOrchestrationAdapter",
    "LocalPlannedQueryGraphApp",
    "OrchestrationCapability",
    "OrchestrationHealthCheck",
    "OrchestrationRunResult",
    "OrchestrationRuntimeAdapter",
    "OrchestrationRuntimeConfig",
    "OrchestrationStatus",
    "PlannerTrace",
    "PlanningResult",
    "PlannedQueryResult",
    "RepairExecutionTrace",
    "classify_query",
    "create_retrieval_plan",
    "create_retrieval_request",
    "normalize_query",
    "plan_request",
    "run_planned_query",
    "select_retrieval_modes",
    "set_retrieval_budget",
]

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime
import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

from shared import (
    AccessDecision,
    AnswerRecord,
    CitationStatus,
    ClaimRecord,
    EvidenceCandidate,
    FreshnessStatus,
    RankedEvidence,
    RelevanceLabel,
    RepairAction,
    RetrievalMode,
    SupportStatus,
    SupportType,
    ValidationCriterion,
    ValidationRecord,
    ValidationStatus,
)


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "src" / "synthesis" / "evidence_bundle.py"


def _load_adapter():
    spec = importlib.util.spec_from_file_location("evidence_bundle_adapter_for_test", ADAPTER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _candidate(
    evidence_id: str,
    source_id: str | None,
    *,
    request_id: str = "req_bundle",
    text: str = "MARACA preserves cited evidence for answer export.",
) -> EvidenceCandidate:
    return EvidenceCandidate(
        request_id=request_id,
        retrieval_mode=RetrievalMode.HYBRID,
        source_id=source_id,
        document_id=f"doc_{evidence_id}",
        chunk_id=f"chunk_{evidence_id}",
        entity_ids=["entity_1"],
        relation_ids=["relation_1"],
        text_snippet=text,
        score=12.5,
        normalized_score=0.875,
        published_at=date(2026, 5, 20),
        retrieved_at=datetime(2026, 5, 21, 10, 30, tzinfo=UTC),
        citation_link=f"https://example.test/{evidence_id}",
        access_decision=AccessDecision.ALLOWED,
        license_constraints=["cite source"],
        evidence_id=evidence_id,
    )


def _records():
    evidence_1 = _candidate("ev_1", "src_1")
    evidence_2 = _candidate("ev_2", "src_1", text="A second chunk keeps source IDs de-duplicated.")
    ranked = RankedEvidence(
        evidence_id="ev_2",
        rank=1,
        rerank_score=0.99,
        relevance_label=RelevanceLabel.HIGH,
        selection_reason="best cited chunk",
        ranked_evidence_id="ranked_1",
    )
    validation = ValidationRecord(
        request_id="req_bundle",
        evidence_ids=["ev_2", "ev_1"],
        validation_status=ValidationStatus.REPAIR_NEEDED,
        freshness_status=FreshnessStatus.FRESH,
        citation_status=CitationStatus.PARTIAL,
        repair_action=RepairAction.RETRIEVE_MORE,
        failed_criteria=[ValidationCriterion.SUFFICIENCY],
        stop_reason="more evidence requested",
        validator_notes="Need one more independent citation.",
        validation_id="validation_1",
    )
    claim = ClaimRecord(
        request_id="req_bundle",
        answer_id="answer_1",
        claim_text="MARACA preserves cited evidence for answer export.",
        support_type=SupportType.PARAPHRASE,
        evidence_id="ev_1",
        evidence_span="chunk_ev_1",
        source_quote="MARACA preserves cited evidence for answer export.",
        support_status=SupportStatus.SUPPORTED,
        confidence=0.82,
        validator_notes="Supported by ev_1.",
        claim_id="claim_1",
    )
    answer = AnswerRecord(
        request_id="req_bundle",
        answer_id="answer_1",
        validation_id="validation_1",
        answer_text="MARACA preserves cited evidence for answer export. [1]",
        citation_map={"claim_1": ["ev_1", "https://example.test/ev_1"]},
        claim_records=[claim],
        limitations=["Needs one more independent source."],
        generated_at=datetime(2026, 5, 21, 11, 0, tzinfo=UTC),
        model_used="test-synthesis",
    )
    return evidence_1, evidence_2, ranked, validation, claim, answer


def test_export_maps_records_sources_validation_notes_and_answer_claims() -> None:
    adapter = _load_adapter()
    evidence_1, evidence_2, ranked, validation, claim, answer = _records()

    payload = adapter.export_evidence_bundle(
        evidence=[evidence_1, evidence_2],
        ranked_evidence=[ranked],
        validations=[validation],
        answers=[answer],
    )

    assert payload["bundle_type"] == "maraca.evidence_bundle"
    assert payload["schema_version"] == "1.0"
    assert payload["request_ids"] == ["req_bundle"]
    assert payload["source_ids"] == ["src_1"]
    assert [item["evidence_id"] for item in payload["evidence"]] == ["ev_1", "ev_2"]
    assert payload["evidence"][0]["retrieval_mode"] == "hybrid"
    assert payload["evidence"][0]["published_at"] == "2026-05-20"
    assert payload["evidence"][0]["retrieved_at"] == "2026-05-21T10:30:00+00:00"
    assert payload["ranked_evidence"][0]["relevance_label"] == "high"
    assert payload["evidence_sources"] == [
        {
            "evidence_id": "ev_1",
            "source_id": "src_1",
            "document_id": "doc_ev_1",
            "chunk_id": "chunk_ev_1",
            "citation_link": "https://example.test/ev_1",
        },
        {
            "evidence_id": "ev_2",
            "source_id": "src_1",
            "document_id": "doc_ev_2",
            "chunk_id": "chunk_ev_2",
            "citation_link": "https://example.test/ev_2",
        },
    ]
    assert payload["validation_statuses"] == [
        {
            "validation_id": "validation_1",
            "request_id": "req_bundle",
            "evidence_ids": ["ev_2", "ev_1"],
            "validation_status": "repair_needed",
            "failed_criteria": ["sufficiency"],
            "repair_action": "retrieve_more",
            "stop_reason": "more evidence requested",
        }
    ]
    assert payload["validation_notes"] == [
        {
            "validation_id": "validation_1",
            "request_id": "req_bundle",
            "validator_notes": "Need one more independent citation.",
        }
    ]
    assert payload["answers"][0]["claim_records"][0]["claim_id"] == "claim_1"
    assert payload["claims"][0]["support_status"] == "supported"
    assert payload["answer_claims"] == [
        {
            "answer_id": "answer_1",
            "request_id": "req_bundle",
            "validation_id": "validation_1",
            "claim_ids": ["claim_1"],
            "citation_map": {"claim_1": ["ev_1", "https://example.test/ev_1"]},
        }
    ]
    assert payload["claim_evidence"] == [
        {
            "claim_id": "claim_1",
            "answer_id": "answer_1",
            "evidence_id": "ev_1",
            "support_status": "supported",
            "support_type": "paraphrase",
        }
    ]


def test_export_is_deterministic_and_does_not_mutate_inputs() -> None:
    adapter = _load_adapter()
    evidence_1, evidence_2, ranked, validation, claim, answer = _records()
    before = {
        "evidence_1": deepcopy(evidence_1.to_dict()),
        "evidence_2": deepcopy(evidence_2.to_dict()),
        "ranked": deepcopy(ranked.to_dict()),
        "validation": deepcopy(validation.to_dict()),
        "claim": deepcopy(claim.to_dict()),
        "answer": deepcopy(answer.to_dict()),
    }

    first = adapter.export_evidence_bundle(evidence_1, [evidence_2, ranked], validation, answer)
    second = adapter.export_evidence_bundle(evidence_1, [evidence_2, ranked], validation, answer)

    assert first == second
    assert evidence_1.to_dict() == before["evidence_1"]
    assert evidence_2.to_dict() == before["evidence_2"]
    assert ranked.to_dict() == before["ranked"]
    assert validation.to_dict() == before["validation"]
    assert claim.to_dict() == before["claim"]
    assert answer.to_dict() == before["answer"]


def test_accepts_synthesis_result_shape_without_importing_synthesis_result() -> None:
    adapter = _load_adapter()
    evidence_1, _, _, _, claim, answer = _records()
    result_shape = SimpleNamespace(
        answer=answer,
        claims=(claim,),
        used_evidence=(evidence_1,),
        logs=("ignored",),
        errors=("ignored",),
    )

    payload = adapter.export_evidence_bundle(synthesis_result=result_shape)

    assert payload["evidence"][0]["evidence_id"] == "ev_1"
    assert payload["answers"][0]["answer_id"] == "answer_1"
    assert [item["claim_id"] for item in payload["claims"]] == ["claim_1"]
    assert "logs" not in payload
    assert "errors" not in payload


def test_adapter_has_no_retrieval_execution_or_boundary_imports() -> None:
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_prefixes = (
        "retrieval",
        "planning",
        "repository",
        "service",
        "client",
        "os",
        "subprocess",
        "requests",
        "http",
        "urllib",
    )
    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imported_modules
        for prefix in forbidden_prefixes
    )


def test_export_payload_has_no_side_effect_terms() -> None:
    adapter = _load_adapter()
    evidence_1, _, _, validation, claim, answer = _records()

    payload_text = repr(adapter.export_evidence_bundle(evidence_1, validation, claim, answer)).lower()

    for term in (
        "api_key",
        "credential",
        "publishing",
        "scrape",
        "scheduler",
        "service",
        "retrieval.run_",
        "apply_access_filter",
        "run_planned_query",
    ):
        assert term not in payload_text

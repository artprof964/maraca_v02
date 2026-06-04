from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, datetime
import inspect
import json
import unittest

import ingestion.social_source_candidates as social_source_candidates
from ingestion.social_source_candidates import (
    DEFAULT_JOB_STARTED_AT,
    SocialSourceCandidate,
    SocialSourceCandidateMapping,
    map_social_source_candidate,
    map_social_source_candidates,
    normalize_social_source_candidate,
    social_source_candidate_payload,
)
from shared import (
    AccessMethod,
    FreshnessPolicy,
    IngestionStatus,
    IngestionTriggerType,
    LicensePolicy,
    ReliabilityLevel,
    SourceStatus,
    SourceType,
)


class DictLikeCandidate:
    def to_dict(self) -> dict[str, object]:
        return {
            "id": "dict-like",
            "source": "fixture",
            "title": "Dict-like candidate",
            "url": "https://example.invalid/dict-like",
            "metadata": {"source_type": "api", "access_method": "api"},
        }


class SocialSourceCandidateTests(unittest.TestCase):
    def test_records_are_frozen_plain_dataclasses(self) -> None:
        for record_type in (SocialSourceCandidate, SocialSourceCandidateMapping):
            self.assertTrue(is_dataclass(record_type))
            self.assertTrue(record_type.__dataclass_params__.frozen)

        candidate = SocialSourceCandidate(
            candidate_id="cand-001",
            work_id="work-001",
            source_name="manual",
        )

        with self.assertRaises(FrozenInstanceError):
            candidate.title = "changed"

    def test_watch_candidate_payload_maps_to_source_and_ingestion_records(self) -> None:
        started_at = datetime(2026, 6, 3, 8, 0, tzinfo=UTC)

        mapping = map_social_source_candidate(
            {
                "candidate_id": "raw-001",
                "work_id": "work-003",
                "source_name": "fixture",
                "title": "First candidate",
                "summary": "Plain text only.",
                "reference": "https://example.invalid/item/1",
                "tags": ["alpha", "beta"],
                "metadata": {
                    "owner": "watch-team",
                    "license_policy": LicensePolicy.ALLOWED,
                    "reliability_level": ReliabilityLevel.LOW,
                    "reliability_score": "0.42",
                    "freshness_sla": "P1D",
                    "refresh_interval": "PT6H",
                    "trigger_type": IngestionTriggerType.WEBHOOK,
                    "correlation_id": "corr-watch-003",
                    "quality_flags": ["candidate-only"],
                },
            },
            started_at=started_at,
        )

        self.assertEqual(mapping.candidate.candidate_id, "raw-001")
        self.assertEqual(mapping.source.source_name, "First candidate")
        self.assertIs(mapping.source.source_type, SourceType.WEB)
        self.assertIs(mapping.source.access_method, AccessMethod.URL)
        self.assertEqual(mapping.source.external_link, "https://example.invalid/item/1")
        self.assertEqual(mapping.source.owner, "watch-team")
        self.assertIs(mapping.source.license_policy, LicensePolicy.ALLOWED)
        self.assertIs(mapping.source.reliability_level, ReliabilityLevel.LOW)
        self.assertEqual(mapping.source.reliability_score, 0.42)
        self.assertIs(mapping.source.freshness_policy, FreshnessPolicy.EVENT_DRIVEN)
        self.assertEqual(mapping.source.freshness_sla, "P1D")
        self.assertEqual(mapping.source.refresh_interval, "PT6H")
        self.assertIs(mapping.source.status, SourceStatus.PENDING)
        self.assertTrue(mapping.source.source_id.startswith("src_social_"))
        self.assertIn("candidate_id=raw-001", mapping.source.notes or "")
        self.assertEqual(mapping.ingestion_job.source_id, mapping.source.source_id)
        self.assertIs(mapping.ingestion_job.trigger_type, IngestionTriggerType.WEBHOOK)
        self.assertIs(mapping.ingestion_job.status, IngestionStatus.QUEUED)
        self.assertEqual(mapping.ingestion_job.started_at, started_at)
        self.assertEqual(mapping.ingestion_job.correlation_id, "corr-watch-003")
        self.assertEqual(mapping.ingestion_job.quality_flags, ["candidate-only"])

    def test_defaults_remain_inert_and_deterministic(self) -> None:
        candidate = {
            "id": "no-link",
            "work_id": "work-defaults",
            "source": "manual-note",
        }

        first = map_social_source_candidate(candidate)
        second = map_social_source_candidate(candidate)

        self.assertEqual(first.source.source_id, second.source.source_id)
        self.assertEqual(
            first.ingestion_job.ingestion_job_id,
            second.ingestion_job.ingestion_job_id,
        )
        self.assertIs(first.source.source_type, SourceType.WEB)
        self.assertIs(first.source.access_method, AccessMethod.MANUAL)
        self.assertIs(first.source.license_policy, LicensePolicy.UNKNOWN)
        self.assertIs(first.source.reliability_level, ReliabilityLevel.UNVERIFIED)
        self.assertIs(first.source.freshness_policy, FreshnessPolicy.EVENT_DRIVEN)
        self.assertIs(first.source.status, SourceStatus.PENDING)
        self.assertIs(first.ingestion_job.trigger_type, IngestionTriggerType.MANUAL)
        self.assertIs(first.ingestion_job.status, IngestionStatus.QUEUED)
        self.assertEqual(first.ingestion_job.started_at, DEFAULT_JOB_STARTED_AT)

    def test_enum_strings_and_social_source_type_alias_are_coerced(self) -> None:
        mapping = map_social_source_candidate(
            {
                "candidate_id": "enum-001",
                "work_id": "work-enums",
                "source_name": "fixture",
                "metadata": {
                    "source_type": "social",
                    "access_method": "api",
                    "freshness_policy": "event_driven",
                    "license": "restricted",
                    "reliability": "medium",
                    "source_status": "active",
                    "ingestion_status": "partial",
                    "ingestion_trigger_type": "repair",
                },
            }
        )

        self.assertIs(mapping.source.source_type, SourceType.WEB)
        self.assertIs(mapping.source.access_method, AccessMethod.API)
        self.assertIs(mapping.source.freshness_policy, FreshnessPolicy.EVENT_DRIVEN)
        self.assertIs(mapping.source.license_policy, LicensePolicy.RESTRICTED)
        self.assertIs(mapping.source.reliability_level, ReliabilityLevel.MEDIUM)
        self.assertIs(mapping.source.status, SourceStatus.ACTIVE)
        self.assertIs(mapping.ingestion_job.status, IngestionStatus.PARTIAL)
        self.assertIs(mapping.ingestion_job.trigger_type, IngestionTriggerType.REPAIR)

    def test_dict_like_candidates_and_batches_are_supported(self) -> None:
        mappings = map_social_source_candidates(
            [
                DictLikeCandidate(),
                SocialSourceCandidate(
                    candidate_id="frozen-001",
                    work_id="work-batch",
                    source_name="local",
                    reference="https://example.invalid/frozen",
                ),
            ]
        )

        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[0].candidate.candidate_id, "dict-like")
        self.assertIs(mappings[0].source.source_type, SourceType.API)
        self.assertIs(mappings[0].source.access_method, AccessMethod.API)
        self.assertEqual(mappings[1].candidate.candidate_id, "frozen-001")
        self.assertIs(mappings[1].source.access_method, AccessMethod.URL)

    def test_input_metadata_is_copied_sanitized_and_not_mutated(self) -> None:
        raw = {
            "candidate_id": "immut-001",
            "work_id": "work-immut",
            "source_name": "fixture",
            "tags": ["review"],
            "metadata": {
                "allowed_principals": ["role:analyst"],
                "nested": {"token": "hidden", "kept": "yes"},
                "api_key": "hidden",
            },
        }

        normalized = normalize_social_source_candidate(raw)
        mapping = map_social_source_candidate(raw)

        raw["tags"].append("mutated")
        raw["metadata"]["allowed_principals"].append("role:mutated")
        raw["metadata"]["nested"]["kept"] = "changed"

        self.assertEqual(normalized.tags, ("review",))
        self.assertEqual(
            normalized.metadata,
            {
                "allowed_principals": ("role:analyst",),
                "nested": {"kept": "yes"},
            },
        )
        self.assertEqual(mapping.source.allowed_principals, ["role:analyst"])
        self.assertNotIn("api_key", mapping.candidate.metadata)
        self.assertEqual(mapping.candidate.metadata["nested"], {"kept": "yes"})

    def test_plain_payload_serializes_existing_record_shapes(self) -> None:
        payload = social_source_candidate_payload(
            {
                "candidate_id": "payload-001",
                "work_id": "work-payload",
                "source_name": "fixture",
                "title": "Payload candidate",
                "url": "https://example.invalid/payload",
                "tags": ("payload",),
                "metadata": {"license_policy": "allowed"},
            }
        )

        roundtripped = json.loads(json.dumps(payload))

        self.assertEqual(roundtripped["candidate"]["tags"], ["payload"])
        self.assertEqual(roundtripped["source"]["source_name"], "Payload candidate")
        self.assertEqual(roundtripped["source"]["source_type"], "web")
        self.assertEqual(roundtripped["source"]["access_method"], "url")
        self.assertEqual(roundtripped["source"]["license_policy"], "allowed")
        self.assertEqual(roundtripped["source"]["freshness_policy"], "event-driven")
        self.assertEqual(roundtripped["ingestion_job"]["status"], "queued")
        self.assertEqual(
            roundtripped["ingestion_job"]["started_at"],
            "1970-01-01T00:00:00+00:00",
        )

    def test_mapper_has_no_runtime_or_external_side_effect_hooks(self) -> None:
        blocked = (
            "re" + "quests",
            "ht" + "tpx",
            "url" + "lib",
            "so" + "cket",
            "sub" + "process",
            "start_" + "ingestion_job",
            "run_" + "ingestion_job",
            "extract_" + "source_content",
            "sche" + "duler",
            "pub" + "lish",
            "sc" + "rape",
            "sle" + "ep",
            "thr" + "ead",
            "tim" + "er",
            "Path" + "(",
            "open" + "(",
        )
        source = inspect.getsource(social_source_candidates)
        lowered = source.lower()

        self.assertIn("from shared.records import", source)
        self.assertNotIn("from ingestion import", source)
        self.assertNotIn("source_registry", lowered)
        for term in blocked:
            self.assertNotIn(term.lower(), lowered)


if __name__ == "__main__":
    unittest.main()

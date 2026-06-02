"""Dependency-free graph extraction for chunk enrichment."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import re
from typing import Iterable

from shared.contracts import LogEvent, Partition, new_correlation_id
from shared.ids import stable_id
from shared.policies import create_success_log_event
from shared.records import ChunkRecord, EntityRecord, EntityType, RelationRecord, RelationType

PARTITION = "enrichment"

_ENTITY_RE = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[-_/:][A-Za-z0-9]+)*(?:\s+[A-Z][A-Za-z0-9]*(?:[-_/:][A-Za-z0-9]+)*){0,3}\b")
_RELATION_ENDPOINT = r"[A-Z][-A-Za-z0-9_/:]*(?:\s+[A-Z][-A-Za-z0-9_/:]*){0,3}"
_RELATION_PATTERNS: tuple[tuple[re.Pattern[str], RelationType], ...] = (
    (re.compile(rf"\b(?P<subject>{_RELATION_ENDPOINT})\s+depends\s+on\s+(?P<object>{_RELATION_ENDPOINT})\b"), RelationType.DEPENDS_ON),
    (re.compile(rf"\b(?P<subject>{_RELATION_ENDPOINT})\s+supports\s+(?P<object>{_RELATION_ENDPOINT})\b"), RelationType.SUPPORTS),
    (re.compile(rf"\b(?P<subject>{_RELATION_ENDPOINT})\s+updates\s+(?P<object>{_RELATION_ENDPOINT})\b"), RelationType.UPDATES),
)
_BOUNDARY_WORDS = {
    "and",
    "but",
    "because",
    "while",
    "with",
    "from",
    "into",
    "then",
    "when",
    "where",
    "which",
    "that",
    "the",
    "a",
    "an",
}


@dataclass(frozen=True, slots=True)
class GraphExtractionResult:
    """Extracted graph records plus updated chunks and extraction logs."""

    entities: tuple[EntityRecord, ...]
    relations: tuple[RelationRecord, ...]
    chunks: tuple[ChunkRecord, ...]
    skipped_chunk_ids: tuple[str, ...] = ()
    log: LogEvent | None = None


def extract_graph_records(
    chunks: Iterable[ChunkRecord],
    *,
    correlation_id: str | None = None,
) -> GraphExtractionResult:
    """Extract deterministic entities and simple fixture relations from chunks."""

    chunk_tuple = tuple(chunks)
    entity_mentions: dict[str, set[str]] = defaultdict(set)
    entity_sources: dict[str, set[str]] = defaultdict(set)
    entity_chunks: dict[str, set[str]] = defaultdict(set)
    relation_mentions: dict[tuple[str, RelationType, str], set[str]] = defaultdict(set)
    skipped_chunk_ids: list[str] = []

    for chunk in chunk_tuple:
        text = chunk.text or ""
        if not text.strip():
            skipped_chunk_ids.append(chunk.chunk_id)
            continue
        for name in _entity_names(text):
            key = _entity_key(name)
            entity_mentions[key].add(name)
            entity_sources[key].add(chunk.source_id)
            entity_chunks[key].add(chunk.chunk_id)
        for subject, relation_type, object_ in _relation_mentions(text):
            subject_key = _entity_key(subject)
            object_key = _entity_key(object_)
            entity_mentions[subject_key].add(subject)
            entity_mentions[object_key].add(object_)
            entity_sources[subject_key].add(chunk.source_id)
            entity_sources[object_key].add(chunk.source_id)
            entity_chunks[subject_key].add(chunk.chunk_id)
            entity_chunks[object_key].add(chunk.chunk_id)
            relation_mentions[(subject_key, relation_type, object_key)].add(chunk.chunk_id)

    entities_by_key: dict[str, EntityRecord] = {}
    for key in sorted(entity_mentions):
        names = sorted(entity_mentions[key], key=lambda value: (len(value), value.lower()))
        canonical_name = names[0]
        aliases = [name for name in sorted(entity_mentions[key]) if name != canonical_name]
        entity = EntityRecord(
            entity_name=canonical_name,
            entity_type=_entity_type(canonical_name),
            aliases=aliases,
            confidence=_entity_confidence(entity_chunks[key]),
            source_ids=sorted(entity_sources[key]),
            entity_id=stable_id("entity", key),
        )
        entities_by_key[key] = entity

    relations: list[RelationRecord] = []
    for subject_key, relation_type, object_key in sorted(
        relation_mentions,
        key=lambda item: (item[0], item[1].value, item[2]),
    ):
        evidence_chunk_ids = sorted(relation_mentions[(subject_key, relation_type, object_key)])
        relation = RelationRecord(
            subject_entity_id=entities_by_key[subject_key].entity_id,
            object_entity_id=entities_by_key[object_key].entity_id,
            relation_type=relation_type,
            evidence_chunk_ids=evidence_chunk_ids,
            confidence=_relation_confidence(evidence_chunk_ids),
            relation_id=stable_id(
                "rel",
                subject_key,
                relation_type.value,
                object_key,
                "|".join(evidence_chunk_ids),
            ),
        )
        relations.append(relation)

    entity_ids_by_chunk = _entity_ids_by_chunk(entities_by_key, entity_chunks)
    relation_ids_by_chunk = _relation_ids_by_chunk(relations)
    updated_chunks = tuple(
        _with_graph_flags(
            chunk,
            entity_ids=entity_ids_by_chunk.get(chunk.chunk_id, ()),
            relation_ids=relation_ids_by_chunk.get(chunk.chunk_id, ()),
            skipped=chunk.chunk_id in skipped_chunk_ids,
        )
        for chunk in chunk_tuple
    )
    log = _enrichment_log(
        correlation_id=correlation_id,
        event_name="graph_extraction_skipped" if skipped_chunk_ids and not entities_by_key else "graph_extraction_completed",
        output_reference=",".join([*(entity.entity_id for entity in entities_by_key.values()), *(relation.relation_id for relation in relations)]) or None,
        details={
            "chunk_count": len(chunk_tuple),
            "entity_count": len(entities_by_key),
            "relation_count": len(relations),
            "skipped_chunk_ids": skipped_chunk_ids,
        },
    )
    return GraphExtractionResult(
        entities=tuple(entities_by_key[key] for key in sorted(entities_by_key)),
        relations=tuple(relations),
        chunks=updated_chunks,
        skipped_chunk_ids=tuple(skipped_chunk_ids),
        log=log,
    )


def _entity_names(text: str) -> tuple[str, ...]:
    names: list[str] = []
    for match in _ENTITY_RE.finditer(text):
        name = _clean_entity_name(match.group(0))
        if (len(name) <= 1 and not name.isupper()) or (name.lower() in _BOUNDARY_WORDS and not name.isupper()):
            continue
        names.append(name)
    return tuple(dict.fromkeys(names))


def _relation_mentions(text: str) -> tuple[tuple[str, RelationType, str], ...]:
    mentions: list[tuple[str, RelationType, str]] = []
    for pattern, relation_type in _RELATION_PATTERNS:
        for match in pattern.finditer(text):
            subject = _clean_relation_endpoint(match.group("subject"))
            object_ = _clean_relation_endpoint(match.group("object"))
            if subject and object_:
                mentions.append((subject, relation_type, object_))
    return tuple(mentions)


def _clean_relation_endpoint(value: str) -> str:
    words = [word.strip(" ,.;:()[]{}") for word in value.split()]
    cleaned: list[str] = []
    for word in words:
        lowered = word.lower()
        if lowered in _BOUNDARY_WORDS and cleaned:
            break
        if lowered in {"depends", "supports", "updates", "on"}:
            break
        if word:
            cleaned.append(word)
    while cleaned and cleaned[0].lower() in _BOUNDARY_WORDS and not cleaned[0].isupper():
        cleaned.pop(0)
    return _clean_entity_name(" ".join(cleaned))


def _clean_entity_name(value: str) -> str:
    return " ".join(value.strip(" ,.;:()[]{}").split())


def _entity_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def _entity_type(name: str) -> EntityType:
    if any(separator in name for separator in ("_", "/", ".", ":")):
        return EntityType.SYSTEM
    if name.isupper() and len(name) <= 8:
        return EntityType.SYSTEM
    return EntityType.CONCEPT


def _entity_confidence(chunk_ids: set[str]) -> float:
    return min(0.95, round(0.65 + (0.1 * len(chunk_ids)), 2))


def _relation_confidence(chunk_ids: list[str]) -> float:
    return min(0.95, round(0.75 + (0.05 * len(chunk_ids)), 2))


def _entity_ids_by_chunk(
    entities_by_key: dict[str, EntityRecord],
    entity_chunks: dict[str, set[str]],
) -> dict[str, tuple[str, ...]]:
    ids_by_chunk: dict[str, list[str]] = defaultdict(list)
    for key, entity in entities_by_key.items():
        for chunk_id in sorted(entity_chunks[key]):
            ids_by_chunk[chunk_id].append(entity.entity_id)
    return {chunk_id: tuple(sorted(entity_ids)) for chunk_id, entity_ids in ids_by_chunk.items()}


def _relation_ids_by_chunk(relations: Iterable[RelationRecord]) -> dict[str, tuple[str, ...]]:
    ids_by_chunk: dict[str, list[str]] = defaultdict(list)
    for relation in relations:
        for chunk_id in relation.evidence_chunk_ids:
            ids_by_chunk[chunk_id].append(relation.relation_id)
    return {chunk_id: tuple(sorted(relation_ids)) for chunk_id, relation_ids in ids_by_chunk.items()}


def _with_graph_flags(
    chunk: ChunkRecord,
    *,
    entity_ids: Iterable[str],
    relation_ids: Iterable[str],
    skipped: bool,
) -> ChunkRecord:
    graph_flags = [f"graph:entity:{entity_id}" for entity_id in entity_ids]
    graph_flags.extend(f"graph:relation:{relation_id}" for relation_id in relation_ids)
    if skipped:
        graph_flags.append("graph_extraction_skipped")
    quality_flags = tuple(dict.fromkeys([*chunk.quality_flags, *graph_flags]))
    return replace(chunk, quality_flags=list(quality_flags))


def _enrichment_log(
    *,
    correlation_id: str | None,
    event_name: str,
    output_reference: str | None = None,
    details: dict[str, object] | None = None,
) -> LogEvent:
    return create_success_log_event(
        correlation_id=correlation_id or new_correlation_id("enrichment"),
        partition=Partition.ENRICHMENT,
        operation_name="extract_graph_records",
        event_name=event_name,
        output_reference=output_reference,
        details=details,
    )


__all__ = [
    "PARTITION",
    "GraphExtractionResult",
    "extract_graph_records",
]

# Change Requests

Updated: 2026-06-24 Europe/Vienna

## Documentation Normalization

CR-DOC-001 / CR-DOC-XREPO-001 records MARACA's role and env requirements for the cross-repo manual. This is a docs-only update.

## Relevant MARACA CRs

| CR | Status | Notes |
|---|---|---|
| CR-MAR-001 | done_local | Evidence bundle export adapter. |
| CR-MAR-002 | done_local | Social source candidate mapping. |
| CR-MAR-003 | done_local | AI-Art-style connection registry and `deepseek-open-art` standard key. |
| CR-MAR-004 | done_local | `QDRANT_COLLECTION` and `NEO4J_DATABASE` wired into health/runtime defaults. |
| CR-DOC-001 / CR-DOC-XREPO-001 | done_local | Docs/status/manual normalization across Harness, `agent_runtime_maraca`, AI-Art, and MARACA. |

## Guardrails

- Do not document MARACA as the thestone Telegram runtime owner.
- Keep `.env.example` as the source of truth for runtime env names.
- Keep strict service validation tied to running Qdrant and Neo4j.

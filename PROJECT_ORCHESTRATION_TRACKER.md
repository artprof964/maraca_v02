# Project Orchestration Tracker

Updated: 2026-06-24 Europe/Vienna

## Milestones

| ID | Milestone | Status | Verification |
|---|---|---|---|
| MAR-ENV | Env schema documented | done | `.env.example`, README, manual, and service docs list LLM, Qdrant, Neo4j, and storage/profile settings. |
| MAR-HEALTH | Health/smoke validation documented | done | `rag-center-health`, `rag-center-smoke`, unittest, and pytest commands recorded. |
| MAR-DOC-001 | Cross-repo docs normalization | done | MARACA boundary and env requirements reflected in root docs and `docs/*` runbooks. |

## Validation Matrix

| Check | Command |
|---|---|
| Dependency check | `.\.venv\Scripts\python.exe -m pip check` |
| Lenient health | `.\.venv\Scripts\rag-center-health.exe --env-file .env` |
| Strict health | `.\.venv\Scripts\rag-center-health.exe --strict-services --env-file .env` |
| Smoke | `.\.venv\Scripts\rag-center-smoke.exe` |
| Unit tests | `.\.venv\Scripts\python.exe -m unittest discover -s tests` |
| Pytest | `.\.venv\Scripts\python.exe -m pytest` |

## Boundary

MARACA is a retrieval backend dependency. AI-Art owns live Compose bot containers; `agent_runtime_maraca` owns thestone scripts/snapshots; Harness owns cross-repo docs.

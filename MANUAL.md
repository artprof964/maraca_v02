# MARACA Manual

Updated: 2026-06-24 Europe/Vienna

## Purpose

MARACA v2 is the hybrid retrieval backend dependency for the broader project. It owns retrieval, source registry, evidence bundle export, Qdrant/Neo4j runtime adapters, and backend health checks. It does not own the live thestone Telegram bot containers.

## Environment Requirements

Copy `.env.example` to `.env` before running local services:

```powershell
Copy-Item .env.example .env
```

Required or documented settings:

| Area | Env vars |
|---|---|
| LLM | `deepseek-open-art`, `LLM_API_URL`, `LLM_PRIMARY_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_CLASSIFIER_MODEL`, `LLM_EMBEDDING_MODEL` |
| Qdrant | `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` |
| Neo4j | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` |
| Local storage | `RAG_STORAGE_ROOT`, `RAG_MODEL_PROFILE` |

`deepseek-open-art` is the standard LLM key name. `DEEPSEEK_API_KEY` is accepted only where code explicitly documents it as a backward-compatible alias.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[full]"
Copy-Item .env.example .env
docker compose up -d qdrant neo4j
```

## Validation

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\rag-center-health.exe --env-file .env
.\.venv\Scripts\rag-center-smoke.exe
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m pytest
```

Use `.\.venv\Scripts\rag-center-health.exe --strict-services --env-file .env` only after Qdrant and Neo4j are running.

## Cross-Repo Boundary

- Harness reads MARACA-style evidence through injected boundaries and docs the cross-repo status.
- AI-Art owns the local Compose stack and thestone Telegram bot containers.
- `agent_runtime_maraca` owns thestone scripts/snapshots.
- MARACA owns retrieval backend env requirements and validation.

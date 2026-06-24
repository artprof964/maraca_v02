# Project Status

Updated: 2026-06-24 Europe/Vienna

## Summary

MARACA v2 is current as the retrieval backend dependency. The documented env schema includes LLM, Qdrant, Neo4j, and local storage/profile settings. No thestone Telegram runtime is owned by this repo.

## Current State

- `.env.example` documents `deepseek-open-art`, `QDRANT_COLLECTION`, and `NEO4J_DATABASE`.
- README documents local setup, health checks, and validation commands.
- Local services are Qdrant and Neo4j through this repo's `docker-compose.yml`.
- Cross-repo docs normalization is documentation-only and does not change MARACA code or service state.

## Validation

- `.\.venv\Scripts\python.exe -m pip check`
- `.\.venv\Scripts\rag-center-health.exe --env-file .env`
- `.\.venv\Scripts\rag-center-smoke.exe`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`
- `.\.venv\Scripts\python.exe -m pytest`

## Risks

- Strict service checks require running Qdrant and Neo4j containers.
- `deepseek-open-art` should remain the documented key name to avoid drift with AI-Art/Harness connection settings.

## Keyword Log

`CR_DOC_001`; `CR_DOC_XREPO_001`; `MARACA_ENV_REQUIREMENTS`; `QDRANT_COLLECTION`; `NEO4J_DATABASE`; `DEEPSEEK_OPEN_ART_STANDARD`

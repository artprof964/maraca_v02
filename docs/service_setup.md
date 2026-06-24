# Service Setup

The local backend can run fully in dependency-free mode, but the preferred full stack also has optional service boundaries for Qdrant, Neo4j, LangGraph, and LlamaIndex.

## Install Python Extras

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[full]"
```

Or run the setup script:

```powershell
PowerShell -ExecutionPolicy Bypass -File scripts\setup_full_backend.ps1
```

## Configure Environment

Copy the example file and adjust values if needed:

```powershell
Copy-Item .env.example .env
```

The default service URLs are:

- Qdrant: `http://localhost:6333`
- Neo4j Bolt: `bolt://localhost:7687`
- Neo4j Browser: `http://localhost:7474`

Required documented env names from `.env.example`:

- `deepseek-open-art`, `LLM_API_URL`, `LLM_PRIMARY_MODEL`, `LLM_FALLBACK_MODEL`, `LLM_CLASSIFIER_MODEL`, `LLM_EMBEDDING_MODEL`
- `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- `RAG_STORAGE_ROOT`, `RAG_MODEL_PROFILE`

## Start Services

Docker is required for the bundled local services:

```powershell
docker compose up -d qdrant neo4j
```

If Docker Desktop is missing and you want the script to request installation through Winget:

```powershell
PowerShell -ExecutionPolicy Bypass -File scripts\setup_full_backend.ps1 -InstallDocker
```

Docker Desktop may require Windows administrator/UAC approval and a restart. After that, rerun:

```powershell
PowerShell -ExecutionPolicy Bypass -File scripts\setup_full_backend.ps1 -StartServices
```

Stop services:

```powershell
docker compose down
```

## Check Health

Lenient check, useful before Docker is available:

```powershell
rag-center-health
```

Strict service check, useful after containers are running:

```powershell
rag-center-health --strict-services
```

## Validate Backend

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m pytest
rag-center-smoke
```

Or run the full validation script:

```powershell
PowerShell -ExecutionPolicy Bypass -File scripts\test_full_backend.ps1
```

## Current Host Caveat

Strict service checks require Qdrant and Neo4j containers to be started from this repo's `docker-compose.yml`. The Python clients, injected-client adapters, fallback runtimes, health reporting, setup/test scripts, and short keyword backend path are validated locally; container health is a runtime prerequisite.

Cross-repo boundary: these services support retrieval backend validation only. They are not the live thestone Telegram bot runtime.

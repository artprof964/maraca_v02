# MARACA

MARACA is an agent-orchestrated hybrid retrieval backend. The repository is
currently centered on a Python package named
`agent-orchestrated-hybrid-retrieval-center`, with optional local service
boundaries for vector search, graph storage, orchestration, and document
indexing.

## Stack Overview

### Runtime

- Python `>=3.11`
- Current validated local version: Python `3.12.13`
- Python packaging: `pyproject.toml` with `setuptools`
- Source layout: `src/`
- Test layout: `tests/`

### Python Backend Packages

The default project dependency list is intentionally empty. Backend integrations
are installed through optional extras:

- `backend`
  - `langgraph>=1.2.2`
  - `llama-index-core>=0.14.22`
  - `neo4j>=6.2.0`
  - `qdrant-client>=1.18.0`
- `test`
  - `pytest>=8`
- `full`
  - all backend packages
  - `pytest>=8`

Install the full backend stack with:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[full]"
```

### Local Services

Local service infrastructure is defined in `docker-compose.yml`.

| Service | Image | Purpose | Ports |
| --- | --- | --- | --- |
| Qdrant | `qdrant/qdrant:v1.18.0` | Vector search backend | `6333`, `6334` |
| Neo4j | `neo4j:5.26-community` | Graph backend | `7474`, `7687` |

The Qdrant image is aligned with the installed `qdrant-client>=1.18.0` package
to avoid client/server compatibility warnings.

### Backend Components

- `backend_app`: health and smoke-test console entry points
- `storage`: in-memory, Qdrant-compatible, and Neo4j-compatible storage adapters
- `retrieval`: keyword, vector, and hybrid retrieval execution
- `planning`: orchestration runtime with LangGraph-compatible integration points
- `source_registry`: source metadata registry
- `ingestion`, `ranking`, `enrichment`, `feedback`, `evaluation`, `synthesis`,
  and `validation`: retrieval pipeline domains
- `shared`: contracts, records, policies, fixtures, environment, and stack metadata

### Console Commands

The package installs two local commands:

```powershell
rag-center-health
rag-center-smoke
```

Use the direct venv executable form if the active shell has not sourced the
virtual environment:

```powershell
.\.venv\Scripts\rag-center-health.exe
.\.venv\Scripts\rag-center-smoke.exe
```

## Environment

Copy the example environment file before starting local services:

```powershell
Copy-Item .env.example .env
```

Default local values:

```dotenv
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=evidence_chunks

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=localdevpassword
NEO4J_DATABASE=neo4j

RAG_STORAGE_ROOT=.local/storage
RAG_MODEL_PROFILE=local-dev
```

## Local Setup

### 1. Create Or Activate A Virtual Environment

If `.venv` already exists:

```powershell
.\.venv\Scripts\Activate.ps1
```

If it does not exist:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If the `py` launcher is unavailable, create the virtual environment with an
installed Python `>=3.11` executable.

### 2. Install The Full Backend

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[full]"
```

You can also run the setup helper:

```powershell
PowerShell -ExecutionPolicy Bypass -File scripts\setup_full_backend.ps1
```

### 3. Configure Environment

```powershell
Copy-Item .env.example .env
```

### 4. Start Local Services

Docker Desktop or another Docker Engine with Compose support is required.

```powershell
docker compose up -d qdrant neo4j
```

Stop services with:

```powershell
docker compose down
```

If Docker is running from a restricted user session that cannot read the normal
Docker config, point Docker at a writable local config directory for that shell:

```powershell
New-Item -ItemType Directory -Force .docker-codex | Out-Null
$env:DOCKER_CONFIG=(Resolve-Path .docker-codex).Path
docker compose up -d qdrant neo4j
```

## Health Checks

Check installed clients, environment variables, Docker availability, and runtime
status:

```powershell
.\.venv\Scripts\rag-center-health.exe --env-file .env
```

After Qdrant and Neo4j are running, perform strict service checks:

```powershell
.\.venv\Scripts\rag-center-health.exe --strict-services --env-file .env
```

Expected strict-service results include:

- Qdrant client installed
- Neo4j driver installed
- LangGraph installed
- LlamaIndex core installed
- Docker Compose available
- Qdrant service reachable
- Neo4j service reachable

The health command injects a local planned-query graph app, so the LangGraph
runtime should report `ready` in the full local setup.

## Validation

Run dependency validation:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Run the smoke flow:

```powershell
.\.venv\Scripts\rag-center-smoke.exe
```

Run the standard-library test suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Run the pytest suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run the combined backend validation script:

```powershell
PowerShell -ExecutionPolicy Bypass -File scripts\test_full_backend.ps1 -StrictServices
```

Latest validated local results:

- `pip check`: no broken requirements
- `rag-center-health --env-file .env.example`: passed in lenient mode
- `rag-center-smoke`: passed
- focused P5.3 pytest: 30 tests passed
- backend-adjacent phase pytest: 70 tests passed
- `unittest`: 141 tests passed
- `pytest`: 307 tests passed

Strict service health was skipped in the latest 2026-06-04 validation because
the Docker daemon/API pipe was unavailable on this host.

## Development Notes

- `.env` and `.local/` are intentionally ignored.
- Docker volumes persist Qdrant and Neo4j state between container restarts.
- The project can exercise most behavior without live services through injected
  clients and local fallback paths.
- Keep `qdrant-client` and the `qdrant/qdrant` image on compatible minor
  versions when updating the stack.

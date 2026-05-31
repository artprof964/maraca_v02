# Local Environment

## Current Setup

The project has a functioning local Python environment at the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
```

The environment uses Python 3.12.13 and installs the project in editable mode with full backend and test extras:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[full]"
```

## Backend Validation

Run the dependency check:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Check optional backend services and tooling:

```powershell
rag-center-health
```

For a strict service check after Qdrant and Neo4j are running:

```powershell
rag-center-health --strict-services
```

Run the standard-library test gate:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Run the pytest gate:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run the short keyword backend manual:

```powershell
rag-center-smoke
```

Latest validated results on 2026-05-29:

- Backend imports: OK.
- Optional backend imports: OK for Qdrant client, Neo4j driver, LangGraph, and LlamaIndex core.
- Dependency check: no broken requirements.
- Service health command: installed clients OK; Docker CLI unavailable on this host. Strict service mode fails until Qdrant and Neo4j are running.
- Standard-library unittest discovery: 115 tests passed.
- Pytest: 205 tests passed.
- Short keyword manual: `rag-center-smoke` completed with one keyword candidate, keyword execution mode, one citation, and a cited answer.
- Setup artifact checks: console commands, package extras, `.env.example`, Docker Compose, and PowerShell setup/test scripts are covered.

## Runtime Notes

The full local environment installs Qdrant client, Neo4j driver, LangGraph, and LlamaIndex core through the `full` extra. External database servers and model service credentials are still runtime integrations; the current tests use injected clients and local fallback paths.

Local Qdrant and Neo4j service definitions live in `docker-compose.yml`. Docker is not installed on the current host, so those containers were not started during this validation run.

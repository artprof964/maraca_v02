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

Docker is not installed on the current host, so Qdrant and Neo4j containers were not started here. The Python clients, injected-client adapters, fallback runtimes, health reporting, setup/test scripts, and short keyword backend path are validated locally.

# Short Keyword Manual

This manual verifies the shortest useful backend path:

1. Register the public fixture source.
2. Ingest and chunk the source.
3. Commit metadata, raw artifact, and chunks.
4. Build vector and sparse keyword indexes.
5. Run an exact keyword query.
6. Route the same query through the planner and synthesize a cited answer.

## Run It

Activate the local environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run the built-in smoke command:

```powershell
rag-center-smoke
```

Expected output includes:

```text
keyword_candidates: 1
executed_modes: keyword
citations: 1
answer:
```

## Direct Python Form

```powershell
.\.venv\Scripts\python.exe -m backend_app.manual
```

## What This Proves

- Source registration works.
- Ingestion and chunking work.
- Storage commits work.
- Keyword and vector indexes build.
- Keyword retrieval hydrates governed evidence.
- Planner routing chooses keyword mode for exact phrase queries.
- Synthesis returns a cited answer from approved evidence.

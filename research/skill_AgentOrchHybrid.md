# Skill: Agent-Orchestrated Hybrid Retrieval Center

## When To Use This Skill

Use this skill when designing, evaluating, or improving an AI retrieval system that combines adaptive agentic RAG with hybrid vector, keyword, and graph retrieval. It is especially useful for internal knowledge centers, research systems, enterprise search, technical support, compliance workflows, and source-backed assistants.

## Goal

Build a retrieval center that selects the right retrieval process for each query. The system should combine semantic recall, exact matching, graph reasoning, validation, and cited synthesis. It should avoid unnecessary retrieval for simple requests and perform deeper retrieval for complex, fresh, ambiguous, or high-risk questions.

## Core Design Pattern

1. Classify the query.
2. Choose the retrieval path.
3. Retrieve candidate evidence.
4. Rerank and filter evidence.
5. Expand through graph relationships when needed.
6. Validate evidence before synthesis.
7. Answer with citations and uncertainty where appropriate.
8. Record feedback and quality metrics.

## Required Components

### Source Registry

Track each source with name, type, owner, URL or access path, refresh schedule, license constraints, reliability level, last ingestion date, and source status.

### Ingestion Pipeline

Convert source data into clean text, chunks, tables, metadata, entities, relationships, embeddings, and graph links. Preserve source provenance and stable IDs.

### Vector Index

Store embeddings for semantic search. Use it for fuzzy matching, natural language questions, conceptual similarity, and unknown terminology.

### Keyword or Sparse Index

Store exact terms and sparse signals. Use it for IDs, names, error messages, rare terminology, legal clauses, and exact phrases.

### Knowledge Graph

Store entities, relations, document links, provenance, dates, and source confidence. Use it for relationship-heavy and multi-hop questions.

### Planner Agent

Classify query complexity and choose the retrieval workflow. Keep this agent predictable and low-cost. It should return a retrieval plan, not a final answer.

### Retrieval Tools

Provide separate tools for vector search, keyword search, graph traversal, database lookup, API lookup, web/source discovery, and metadata filtering.

### Reranker

Reorder candidate evidence by relevance, source quality, date, and diversity. Prefer a dedicated reranker or cross-encoder for precision-critical tasks.

### Validator Agent

Check that evidence is relevant, sufficient, fresh, cited, and non-contradictory. Reject weak evidence and request another retrieval pass when needed.

### Synthesis Agent

Produce final answers only from validated evidence. Cite sources clearly and state limitations when evidence is incomplete.

## Planner Routing Rules

- Use no retrieval when the request is purely conversational, procedural, or based only on provided context.
- Use keyword retrieval for exact IDs, names, quoted text, error messages, standards, and legal clauses.
- Use vector retrieval for broad semantic questions, vague wording, or exploratory discovery.
- Use hybrid keyword-vector retrieval for most general knowledge questions.
- Use graph retrieval when the query asks about relationships, dependencies, timelines, ownership, lineage, influence, or multi-hop reasoning.
- Use external retrieval when internal sources are stale, incomplete, or the query asks for recent information.
- Use iterative retrieval when evidence is insufficient, contradictory, or only partially answers the question.
- Use validator review for high-risk, source-backed, external, or multi-hop answers.

## Standard Workflow

1. Intake the user request and normalize it into a retrieval objective.
2. Planner assigns query type, risk level, freshness requirement, and retrieval route.
3. Retrieval tools collect candidate evidence from selected stores.
4. Reranker removes weak or duplicate results.
5. Graph agent expands entities or paths if relational evidence is needed.
6. Validator checks evidence quality.
7. If evidence fails validation, planner selects a repair action.
8. Synthesis agent answers from validated evidence.
9. System records trace, sources, latency, cost, and validation result.

## Repair Actions

- Rewrite the query.
- Add keyword search after weak vector results.
- Add vector search after overly narrow keyword results.
- Expand graph neighborhood.
- Resolve entity ambiguity.
- Retrieve newer sources.
- Ask for clarification if the user request is under-specified.
- Return uncertainty if reliable evidence is unavailable.

## Evidence Validation Checklist

- Does the evidence directly answer the query?
- Are all important claims traceable to sources?
- Are source dates appropriate?
- Are there contradictions between sources?
- Is there enough evidence to answer?
- Is the evidence too narrow or biased?
- Are graph entities correctly resolved?
- Are retrieved chunks linked to original sources?
- Does the answer need external verification?

## Output Rules

- Cite source-backed claims.
- Separate confirmed facts from inference.
- Mention uncertainty when evidence is incomplete.
- Do not hide source conflicts.
- Keep answers concise unless the user asks for depth.
- Prefer structured output for audits, comparisons, and implementation planning.

## Model Guidance

Planner:
Use a small-to-medium instruction model. Optimize for consistent routing, low latency, and low cost.

Retriever:
Use embedding models for semantic recall and BM25 or sparse vectors for exact matching. Graph traversal should be deterministic where possible.

Reranker:
Use a dedicated reranker or cross-encoder. Apply after broad retrieval, before validation.

Extraction:
Use a medium or large model for entity and relationship extraction during ingestion. Validate against schema rules and sample outputs.

Validator:
Use a strong reasoning-capable model. This role needs citation checking, contradiction detection, sufficiency grading, and freshness review.

Synthesis:
Use a medium model for standard answers. Use a larger model for high-risk, multi-hop, or conflict-heavy synthesis.

## Recommended Stack

Primary stack:
LlamaIndex, Neo4j, Qdrant, LangGraph.

Why:
LlamaIndex supports indexing and retrieval abstractions, Neo4j supports graph storage and Cypher traversal, Qdrant supports scalable vector and hybrid search, and LangGraph supports adaptive agent workflows.

Enterprise alternative:
Haystack, OpenSearch, Neo4j.

Why:
Haystack provides production retrieval pipelines, OpenSearch provides mature lexical and vector search, and Neo4j adds graph relationships.

Temporal-memory alternative:
Graphiti, Neo4j, Weaviate, LangGraph.

Why:
Graphiti supports evolving graph memory, Neo4j provides durable graph storage, Weaviate supports hybrid search, and LangGraph coordinates agents.

## Quality Metrics

- Retrieval recall.
- Citation precision.
- Unsupported claim rate.
- Validator rejection rate.
- Graph hit rate.
- Entity resolution accuracy.
- Reranker improvement.
- Answer usefulness.
- Latency per query.
- Cost per query.
- Freshness compliance.

## Common Failure Modes

- Planner chooses the wrong retrieval path.
- Vector search misses exact identifiers.
- Keyword search misses semantic matches.
- Graph contains duplicate or incorrect entities.
- Reranker over-filters useful evidence.
- Validator accepts weak citations.
- Synthesis adds unsupported claims.
- External sources are stale or unreliable.
- Feedback data is too sparse to tune the system.

## Best Practices

- Start with vector plus keyword retrieval before adding full graph workflows.
- Add graph retrieval where entities and relationships clearly matter.
- Keep planner decisions observable.
- Store every answer with evidence IDs and validation status.
- Evaluate retrieval and synthesis separately.
- Use human review for early validator calibration.
- Prefer incremental rollout over a full multi-agent system on day one.
- Treat external retrieval as a governed source with dates and reliability labels.

## Minimal Viable Version

The minimum useful system needs source registry, ingestion, chunks, metadata, vector search, keyword search, simple planner routing, reranking, answer synthesis, source citations, and feedback logging.

## Full Version

The mature system adds entity extraction, graph storage, graph traversal, iterative retrieval repair, external source discovery, validator agent review, contradiction handling, source freshness monitoring, evaluation dashboards, and cost-quality optimization.

## Project File Inventory

Use this section to understand the local project artifacts in this folder.

## GitHub Repository

Repository: `artprof964/MARACA`

URL: https://github.com/artprof964/MARACA

Default branch: `main`

Local remote:

```text
origin https://github.com/artprof964/MARACA.git
```

Authentication note: use the local environment variable `git_ai-artist_codex_token` for GitHub API or push operations. Do not write the token value into project files.

### research/method_detail_AgentOrchHybrid.md

Detailed architecture and method specification for the Agent-Orchestrated Hybrid Retrieval Center. Use it as the main technical design reference for data fields, partitions, interface protocols, try/error handling, logging, quality gates, routing logic, implementation phases, and governance rules.

### research/method_flow_AgentOrchHybrid.mmd

Standalone Mermaid flowchart for the detailed process. Use it when a visual process map is needed, especially for explaining source ingestion, retrieval routing, validation, repair loops, logging, and feedback.

### research/papers_database.csv

Spreadsheet-friendly paper database containing tracked research sources with title, date, source, topics, summary, URL, and external_link. Use it for quick review, manual editing, import into spreadsheets, or lightweight publication tracking.

### research/papers_database.sqlite

SQLite version of the paper database. Use it when structured querying is preferred over CSV editing, or when a local application needs to read publication records through a database.

### project_milestones.md

Development roadmap for the retrieval center. Use it to plan implementation across milestones: foundation, hybrid retrieval, planner, graph layer, validator, evaluation, and production hardening.

### research/project_summary_outline_AgentOrchHybrid.md

High-level project summary focused on the Agent-Orchestrated Hybrid Retrieval Center. Use it for quick orientation, stakeholder summaries, and explaining purpose, architecture, retrieval modes, agent roles, roadmap, and success criteria.

### project_tests.md

Test strategy and test catalog. Use it to design unit tests, validator tests, integration tests, logging/error tests, acceptance tests, and regression tests for every project partition.

### research/proposals.md

Consolidated proposal file containing the three architecture proposals, validator review, implementation stack options, model optimization guidance, and the ten researched data-retrieval methods. Use it for comparing strategic options and justifying why Agent-Orchestrated Hybrid Retrieval is the baseline.

### research/skill_AgentOrchHybrid.md

Reusable skill and operating guide for this project. Use it as the practical instruction file for routing rules, workflows, repair actions, validation checks, model guidance, metrics, failure modes, and the local project file inventory.

### research/top_10_methods.md

Research brief ranking ten likely methods for automated data-retrieving AI models. Use it when comparing RAG, GraphRAG, CAG, hybrid vector-graph retrieval, selective retrieval, reranking, cache compression, and evaluation-feedback methods.

## File Usage Priority

- For implementation design, start with `research/method_detail_AgentOrchHybrid.md`.
- For visual explanation, use `research/method_flow_AgentOrchHybrid.mmd`.
- For roadmap planning, use `project_milestones.md`.
- For test planning, use `project_tests.md`.
- For strategic comparison, use `research/proposals.md`.
- For research context, use `research/top_10_methods.md` and `research/papers_database.csv`.
- For database-backed paper tracking, use `research/papers_database.sqlite`.

## Decision Summary

The Agent-Orchestrated Hybrid Retrieval Center is the recommended baseline because it is practical, extensible, and compatible with both RAG and GraphRAG. It can begin as a simple hybrid retrieval system and evolve toward deeper graph reasoning and multi-agent validation as quality requirements increase.

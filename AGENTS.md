# PBL6 module contracts

- `labor_rag` owns legal parsing, ontology, chunking, retrieval, generation and file storage algorithms. It must never import `src.backend`, SQLAlchemy application models or FastAPI.
- `labor_rag/services` is the Python interface shared by HTTP and CLI. Preserve chunk IDs, amendments, appendix metadata and source locators across every stage.
- `src/backend/app` owns HTTP, sessions, PostgreSQL persistence, Redis cache, task orchestration and runtime configuration. Routers call services; they do not implement another RAG pipeline.
- `src/frontend` owns the Next.js UI. Browser requests use relative `/api` paths. Add public API schemas and matching TypeScript contracts together.
- Preserve the established UI layout and styling during architecture or API integration work. Bind real data and add navigation within the existing design; redesign only when the user asks for it.
- `src/UI` and `src/doc` are design references, not implementations or authoritative API documentation.
- Never return sample legal evidence, invented scores, fixed health indicators or successful verification after an exception. Empty and unavailable are valid states.
- Construct remote clients in application resources, not at import time. Settings are immutable per operation; do not mutate environment variables to reconfigure active clients.
- Cloud is the default. Local databases and embedding require explicit configuration. Do not recreate collections or clear datasets during uploads or startup.
- Generated files go under ignored data directories. Versioned projections, benchmarks and reports are not upload output directories.
- Test public tools without PostgreSQL, Redis or LLM access; mock external services in automated tests. Use isolated namespaces for cloud write tests.
- Run one backend process with one ingestion worker. Multiple processes require shared coordination for tasks and configuration.
- Dependencies live in `pyproject.toml`; requirements files only reference extras. Keep startup and architecture instructions in README.md and docs/SYSTEM.md.

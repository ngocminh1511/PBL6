"""Read-only service diagnostics, with sanitized errors and real counters."""
from contextlib import closing
from labor_rag.appendices.catalog import read_json
from labor_rag.appendices.runtime import usable


def health_status(runtime, *, probe=False):
    catalog, config = runtime.catalog, runtime.settings
    catalog.refresh_storage()
    result = {
        "demo_mode": config.DEMO_MODE, "config_version": runtime.version,
        "storage": {
            "backend": "r2" if any(a.get("storage_backend") == "r2" for a in catalog.artifacts.values()) else "local",
            "automatic_upload": False, "local_backups_retained": True,
            "r2_verified_files": sum(bool(a.get("r2", {}).get("verified_at")) for a in catalog.artifacts.values()),
            "r2": {"connection": "not_checked"},
        },
        "data": {"documents": len(catalog.report.get("documents", [])),
            "appendices": len(catalog.items), "chunks": len(catalog.chunks),
            "usable_appendices": sum(usable(a) for a in catalog.items.values()),
            "needs_review": sum(a.get("review_status") == "needs_review" for a in catalog.items.values()),
            "missing_documents": [d for d in catalog.report.get("documents", []) if d.get("extraction_status") != "extracted"]},
        "postgres": {"connection": "connected" if runtime.database.available else "unavailable",
                     "error_type": runtime.database.error_type},
        "redis": {"connection": runtime.cache().status},
        "embedding": {"backend": config.query_backend, "model": config.EMBEDDING_MODEL},
        "llm": {"provider": config.LLM_PROVIDER, "status": "not_probed"},
    }
    for key in ("neo4j", "qdrant"):
        report = read_json(catalog.directory / (key + "_load_report.json"), {"status": "not_checked"})
        result[key] = {k: v for k, v in report.items() if k in {
            "status", "nodes", "edges", "appendix_points", "base_unchanged", "error_type",
        }}
        result[key]["connection"] = "not_checked"
    if probe:
        from neo4j import GraphDatabase
        from qdrant_client import QdrantClient
        for name, action in [
            ("neo4j", lambda: _graph_probe(config, GraphDatabase)),
            ("qdrant", lambda: _vector_probe(config, QdrantClient)),
            ("storage", lambda: runtime.storage().check_bucket()),
        ]:
            target = result["storage"]["r2"] if name == "storage" else result[name]
            try:
                values = action()
                target.update(connection="connected", **(values or {}))
            except Exception as exc:
                target.update(connection="unavailable", error_type=type(exc).__name__)
    return result


def _graph_probe(config, graph):
    with graph.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
                      connection_timeout=5, max_transaction_retry_time=0) as driver:
        driver.verify_connectivity()
        with driver.session(database=config.NEO4J_DATABASE) as session:
            record = session.run(
                "MATCH (n {dataset_id:$dataset}) RETURN count(n) AS nodes",
                dataset=config.DATASET_ID,
            ).single()
            edges = session.run(
                "MATCH ()-[r {dataset_id:$dataset}]->() RETURN count(r) AS edges",
                dataset=config.DATASET_ID,
            ).single()
            return {"nodes": record["nodes"], "edges": edges["edges"]}


def _vector_probe(config, client_class):
    with closing(client_class(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY or None, timeout=8)) as client:
        info = client.get_collection(config.QDRANT_COLLECTION)
        params = info.config.params.vectors
        return {"points": info.points_count, "dimensions": getattr(params, "size", None)}

"""Read-only service diagnostics, with sanitized errors and real counters."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from threading import Lock
from labor_rag.appendices.catalog import read_json
from labor_rag.appendices.runtime import usable


logger = logging.getLogger(__name__)


class HealthMonitor:
    """The last service probe, shared by every page.

    Probes run on their own thread, outside runtime operations, so they never delay
    a configuration save. A result belongs to one configuration version and is
    dropped once the configuration changes.
    """
    MAX_AGE_SECONDS = 300

    def __init__(self, runtime):
        self.runtime = runtime
        self.lock = Lock()
        self.result = None  # (config version, monotonic time, probe result)
        self.pending = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="health-probe")

    def refresh(self):
        with self.lock:
            if self.pending is None or self.pending.done():
                self.pending = self.executor.submit(self._probe)
            return self.pending

    def _probe(self):
        version = self.runtime.version
        try:
            result = health_status(self.runtime, probe=True)
        except Exception as exc:
            logger.warning("Service probe failed (%s)", type(exc).__name__)
            return None
        with self.lock:
            if self.runtime.version == version:
                self.result = (version, time.monotonic(), result)
        return result

    def snapshot(self, *, force=False):
        """The cached probe for the current configuration; a missing or stale one is refreshed in the background."""
        version = self.runtime.version
        with self.lock:
            cached = self.result if self.result and self.result[0] == version else None
            refreshing = self.pending is not None and not self.pending.done()
        if force or cached is None or time.monotonic() - cached[1] >= self.MAX_AGE_SECONDS:
            self.refresh()
            refreshing = True
        current = cached[2] if cached else health_status(self.runtime, probe=False)
        return {**current, "refreshing": refreshing}

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)


def health_status(runtime, *, probe=False):
    catalog, config = runtime.catalog, runtime.settings
    catalog.refresh_storage()
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat() if probe else None,
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
        "redis": {"connection": "unavailable" if runtime.configuration_error else runtime.cache().status},
        "embedding": {"backend": config.query_backend, "model": config.EMBEDDING_MODEL},
        "llm": {"provider": config.LLM_PROVIDER, "status": "not_probed"},
    }
    for key in ("neo4j", "qdrant"):
        report = read_json(catalog.directory / (key + "_load_report.json"), {"status": "not_checked"})
        result[key] = {"last_load_status": report.get("status", "not_checked")}
        result[key]["connection"] = "not_checked"
    if runtime.configuration_error:
        for key in ("neo4j", "qdrant"):
            result[key]["connection"] = "unavailable"
        result["llm"]["status"] = "unavailable"
        return result
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
    from labor_rag.services.neo4j import create_neo4j_driver
    with create_neo4j_driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
                      driver_factory=graph.driver,
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

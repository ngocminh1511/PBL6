"""Stateless question-answer pipeline. Session persistence belongs to the caller."""
from copy import copy
from dataclasses import asdict
from time import perf_counter
from urllib.parse import quote
from uuid import uuid4


class PipelineError(RuntimeError):
    def __init__(self, stage, cause):
        self.stage = stage
        self.error_type = type(cause).__name__
        super().__init__(f"{stage}: {self.error_type}")


def evidence_dict(evidence, catalog):
    result = {**asdict(evidence), "citation": evidence.citation}
    result["amendments"] = [evidence_dict(item, catalog) for item in evidence.amendments]
    if evidence.appendix_id in catalog.items:
        result["view_url"] = catalog.public_item(catalog.items[evidence.appendix_id])["view_url"]
        if evidence.chunk_id in catalog.chunks:
            result["view_url"] += "?chunk_id=" + quote(evidence.chunk_id, safe="")
    return result


class ChatPipeline:
    def __init__(self, retriever, catalog, settings):
        self.retriever = retriever
        self.catalog = catalog
        self.settings = settings

    def ask(self, question, *, history=None, top_k=8, rerank_top_n=5, mode="hybrid"):
        # These imports are deliberately absent from the retrieval-only HTTP path.
        from labor_rag.generation.llm_client import use_settings
        from labor_rag.generation.answer import generate_answer
        from labor_rag.generation.citation_verify import verify_citations
        from labor_rag.retrieval.query_rewrite import rewrite_query
        from labor_rag.retrieval.rerank import rerank
        started = perf_counter()
        history = history or []
        timings = {}

        def run(stage, action):
            before = perf_counter()
            try:
                return action()
            except Exception as exc:
                raise PipelineError(stage, exc) from None
            finally:
                timings[stage] = round((perf_counter() - before) * 1000, 2)

        with use_settings(self.settings):
            query = run("query_rewrite", lambda: rewrite_query(history, question)) if history else question

            def retrieve():
                if mode == "vector_only":
                    items = self.retriever.vector_search(query, top_k=top_k)
                    self.retriever.attach_amendments(items)
                    return items
                if mode == "graph_only":
                    seeds = self.retriever.vector_search(query, top_k=2)
                    items = self.retriever.graph_expand([e.mapc for e in seeds if e.mapc], limit_per_node=top_k)
                    self.retriever.hydrate_from_qdrant(items)
                    items = [e for e in items if e.text][:top_k]
                    self.retriever.attach_amendments(items)
                    return items
                return self.retriever.retrieve(query, top_k=top_k)

            raw = run("retrieval", retrieve)
            picked = run("rerank", lambda: rerank(query, raw, top_n=rerank_top_n))
            # augment() stores output on its instance; a request-local shallow copy
            # shares only the read-only corpus and never another request's output.
            catalog = copy(self.catalog)
            picked = run("appendices", lambda: catalog.augment(query, list(picked), limit=6))
            warnings = list(catalog.last_warnings)
            graph_warning = getattr(self.retriever, "graph_warning", None)
            if graph_warning and mode == "hybrid":
                warnings.append(graph_warning)
            answer = run("generation", lambda: generate_answer(query, picked, context_notes=warnings))
            check = run("verification", lambda: verify_citations(answer, picked))
        elapsed = round((perf_counter() - started) * 1000)
        retained = {e.chunk_id for e in picked}
        scores = [e.score for e in raw if e.source == "vector"]
        trace = {
            "trace_id": "TR-" + uuid4().hex[:10], "execution_time_ms": elapsed,
            "step1_query_rewrite": {"activated": bool(history), "original_query": question, "standalone_query": query},
            "step2_hybrid_retrieval": {
                "vector_hits_count": sum(e.source == "vector" for e in raw),
                "vector_score_range": f"{min(scores):.4f} - {max(scores):.4f}" if scores else "",
                "graph_hops_count": sum(e.source.startswith("graph") for e in raw),
                "refers_to_targets": [e.citation for e in raw if e.source.startswith("graph")],
            },
            "step3_rerank": {"retained_count": len(picked),
                "pruned_count": sum(e.chunk_id not in retained for e in raw),
                "pruned_citations": [e.citation for e in raw if e.chunk_id not in retained]},
            "step4_verification": {"status": "Khớp chứng cứ truy hồi" if check["all_verified"] else "Có trích dẫn chưa xác minh",
                "verified_citations": check["verified"], "unverified_citations": check["unverified"]},
            "timings_ms": timings,
        }
        return {"standalone_query": query, "answer": answer, "evidence": picked,
                "citation_check": check, "attachments": catalog.last_attachments,
                "warnings": warnings, "pipeline_trace": trace, "execution_time_ms": elapsed}

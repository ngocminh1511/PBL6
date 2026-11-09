"""Read the versioned corpus without inventing sample document records."""
from collections import Counter, defaultdict
from functools import lru_cache
import json
from labor_rag.config import LAO_DONG_DIR


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


@lru_cache(maxsize=1)
class Corpus:
    def __init__(self):
        self.nodes = rows(LAO_DONG_DIR / "kg_nodes.jsonl")
        self.edges = rows(LAO_DONG_DIR / "kg_edges.jsonl")
        self.chunks = rows(LAO_DONG_DIR / "chunks.jsonl")
        self.documents = {}
        counts = Counter(c["document_id"] for c in self.chunks)
        for node in self.nodes:
            if node.get("label") == "VanBan" and node.get("document_id"):
                identity = node["document_id"]
                owned = {n["id"] for n in self.nodes if n.get("document_id") == identity}
                self.documents[identity] = {
                    "id": identity, "title": node.get("ten") or node.get("document_number") or identity,
                    "document_number": node.get("document_number"), "document_type": "phap_dien_html",
                    "domain": "lao_dong", "effective_from_date": node.get("effective_date"),
                    "status": "versioned_corpus", "chunks_count": counts[identity],
                    "nodes_count": len(owned), "edges_count": sum(e["source"] in owned for e in self.edges),
                    "created_at": "1970-01-01T00:00:00", "updated_at": "1970-01-01T00:00:00",
                }

    def tree(self, document_id):
        document = self.documents.get(document_id)
        if not document:
            return None
        owned = {n["id"]: n for n in self.nodes if n.get("document_id") == document_id}
        children = defaultdict(list)
        child_ids = set()
        source_of = {}
        for edge in self.edges:
            if edge["source"] not in owned or edge["target"] not in owned:
                continue
            if edge["type"] == "CONTAINS":
                children[edge["source"]].append(edge["target"])
                child_ids.add(edge["target"])
            elif edge["type"] == "DERIVED_FROM" and owned[edge["source"]].get("label") == "Dieu":
                source_of[edge["target"]] = edge["source"]
        # A Dieu and the source article it derives from are one article: its khoan sit under it.
        for article, dieu in source_of.items():
            children[dieu].extend(children.pop(article, []))

        def number_key(identity):
            node = owned[identity]
            return tuple((0, int(v), "") if str(v or "").isdigit() else (1, 0, str(v or ""))
                         for v in (node.get("article_number"), node.get("clause_number"), node.get("point_number"))) + (identity,)

        def title(node):
            if node.get("label") == "SourceComponent" and (node.get("clause_number") or node.get("point_number")):
                return (node.get("text") or "")[:90]
            return node.get("ten") or node.get("article_number") or node["id"]

        def build(identity, visited):
            node = owned[identity]
            if identity in visited:
                return None
            return {"id": identity, "type": node.get("label", "component"), "title": title(node),
                "text": node.get("text") or node.get("source_quote") or "",
                "article_number": node.get("article_number"), "clause_number": node.get("clause_number"),
                "point_number": node.get("point_number"),
                "children": [item for key in sorted(set(children[identity]), key=number_key)
                    if (item := build(key, visited | {identity})) is not None]}
        roots = sorted(set(owned) - child_ids - set(source_of), key=number_key)
        return {"id": document_id, "type": "document", "title": document["title"],
                "children": [build(key, set()) for key in roots]}

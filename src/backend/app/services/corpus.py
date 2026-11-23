"""Read the versioned corpus without inventing sample document records."""
from collections import Counter, defaultdict
from functools import lru_cache
import json
import re
from labor_rag.config import INTERIM_DIR, LAO_DONG_DIR


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _strip_prefix(value: str | None, prefix: str) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if text.lower().startswith(prefix.lower()):
        text = text[len(prefix):].strip()
    return text or None


def _natural_tokens(text: str):
    return [(0, int(part), "") if part.isdigit() else (1, 0, part) for part in re.split(r"(\d+)", str(text or "")) if part]


@lru_cache(maxsize=1)
class Corpus:
    def __init__(self):
        self.nodes = rows(LAO_DONG_DIR / "kg_nodes.jsonl")
        self.edges = rows(LAO_DONG_DIR / "kg_edges.jsonl")
        self.chunks = rows(LAO_DONG_DIR / "chunks.jsonl")
        self.documents = {}
        self._demuc_root_id = {}
        self._pdf_trees = {}

        self.total_articles = sum(1 for n in self.nodes if n.get("label") == "Dieu")
        self.total_clauses = sum(1 for n in self.nodes if n.get("clause_number") and not n.get("point_number"))
        self.total_points = sum(1 for n in self.nodes if n.get("point_number"))

        self._nodes_by_id = {n["id"]: n for n in self.nodes}
        self._vanban_numbers = {
            n["document_id"]: n.get("document_number")
            for n in self.nodes
            if n.get("label") == "VanBan" and n.get("document_id")
        }
        self._contains = defaultdict(list)
        self._derived_from = {}
        for edge in self.edges:
            if edge["type"] == "CONTAINS":
                self._contains[edge["source"]].append(edge["target"])
            elif edge["type"] == "DERIVED_FROM" and self._nodes_by_id.get(edge["source"], {}).get("label") == "Dieu":
                self._derived_from[edge["source"]] = edge["target"]

        # 1. Pháp điển entries grouped by Đề mục (20.2, 20.3, 20.4, 20.5, ...)
        for node in self.nodes:
            if node.get("label") != "DeMuc":
                continue
            item_num = node.get("ontology_vlpd__itemNumber")
            code = f"20.{item_num}" if item_num is not None else node["id"].split("#")[-1]
            owned_ids = set()
            stack = [node["id"]]
            while stack:
                nid = stack.pop()
                if nid in owned_ids or nid not in self._nodes_by_id:
                    continue
                owned_ids.add(nid)
                for child_id in self._contains.get(nid, []):
                    stack.append(child_id)
                source_art = self._derived_from.get(nid)
                if source_art and source_art in self._nodes_by_id:
                    for child_id in self._contains.get(source_art, []):
                        stack.append(child_id)

            owned_nodes = [self._nodes_by_id[nid] for nid in owned_ids]
            self._demuc_root_id[code] = node["id"]
            prefix = f"{code}."
            chunks_count = sum(1 for ch in self.chunks if str(ch.get("mapc") or "").startswith(prefix))
            self.documents[code] = {
                "id": code,
                "title": node.get("ten") or node.get("ontology_rdfs__label") or code,
                "document_number": f"Đề mục {code}",
                "document_type": "phap_dien_html",
                "domain": "lao_dong",
                "effective_from_date": None,
                "status": "versioned_corpus",
                "chunks_count": chunks_count,
                "nodes_count": len(owned_ids),
                "edges_count": sum(1 for e in self.edges if e["source"] in owned_ids),
                "articles_count": sum(1 for n in owned_nodes if n.get("label") == "Dieu"),
                "clauses_count": sum(1 for n in owned_nodes if n.get("clause_number") and not n.get("point_number")),
                "points_count": sum(1 for n in owned_nodes if n.get("point_number")),
                "created_at": "1970-01-01T00:00:00",
                "updated_at": "1970-01-01T00:00:00",
            }

        # 2. PDF OCR documents generated under data/interim/pdf_chunks/*_hierarchical.jsonl
        pdf_dir = INTERIM_DIR / "pdf_chunks"
        if pdf_dir.exists():
            for h_path in sorted(pdf_dir.glob("*_hierarchical.jsonl")):
                raw_lines = rows(h_path)
                if not raw_lines:
                    continue
                raw = raw_lines[0]
                doc_id = raw.get("document_id")
                if not doc_id:
                    continue
                meta = raw.get("metadata") or {}
                so_hieu = meta.get("so_hieu") or ""
                loai = meta.get("loai_van_ban") or ""
                title = raw.get("title") or (f"{loai} số {so_hieu}".strip() if so_hieu else doc_id)
                tree, counts = self._build_pdf_tree(raw, doc_id, title)
                self._pdf_trees[doc_id] = tree
                chunks_path = pdf_dir / f"{doc_id}_chunks.jsonl"
                chunk_rows = rows(chunks_path) if chunks_path.exists() else []
                chunks_count = len(chunk_rows) if chunk_rows else counts["articles"]
                pdf_domain = (chunk_rows[0].get("domain") if chunk_rows else None) or "lao_dong"
                self.documents[doc_id] = {
                    "id": doc_id,
                    "title": title,
                    "document_number": so_hieu or None,
                    "document_type": "pdf",
                    "domain": pdf_domain,
                    "effective_from_date": meta.get("ngay_hieu_luc") or meta.get("version_date") or None,
                    "status": "completed",
                    "chunks_count": chunks_count,
                    "nodes_count": 1 + counts["chapters"] + counts["sections"] + counts["articles"] + counts["clauses"] + counts["points"],
                    "edges_count": 0,
                    "articles_count": counts["articles"],
                    "clauses_count": counts["clauses"],
                    "points_count": counts["points"],
                    "created_at": "1970-01-01T00:00:00",
                    "updated_at": "1970-01-01T00:00:00",
                }

        self.total_demuc = sum(1 for d in self.documents.values() if d["document_type"] == "phap_dien_html")
        self.total_pdf_docs = sum(1 for d in self.documents.values() if d["document_type"] == "pdf")

    def _build_pdf_tree(self, raw: dict, doc_id: str, title: str):
        counts = {"chapters": 0, "sections": 0, "articles": 0, "clauses": 0, "points": 0}

        def build_point(pt):
            counts["points"] += 1
            text = pt.get("text") or ""
            return {
                "id": pt.get("point_id") or "",
                "type": "point",
                "title": text[:90],
                "text": text,
                "point_number": pt.get("point_label") or "",
                "children": [],
            }

        def build_clause(cl):
            counts["clauses"] += 1
            text = cl.get("text") or ""
            return {
                "id": cl.get("clause_id") or "",
                "type": "clause",
                "title": text[:90],
                "text": text,
                "clause_number": _strip_prefix(cl.get("clause_number"), "Khoản"),
                "children": [build_point(pt) for pt in cl.get("points") or []],
            }

        def build_article(art):
            counts["articles"] += 1
            return {
                "id": art.get("article_id") or "",
                "type": "article",
                "title": art.get("article_title") or "",
                "text": art.get("full_text") or "",
                "article_number": _strip_prefix(art.get("article_number"), "Điều"),
                "children": [build_clause(cl) for cl in art.get("clauses") or []],
            }

        def build_section(sec):
            counts["sections"] += 1
            sec_title = " ".join(v for v in [sec.get("section_number"), sec.get("section_title")] if v)
            return {
                "id": sec.get("section_id") or "",
                "type": "section",
                "title": sec_title,
                "text": "",
                "children": [build_article(art) for art in sec.get("articles") or []],
            }

        def build_chapter(ch):
            counts["chapters"] += 1
            ch_title = " ".join(v for v in [ch.get("chapter_number"), ch.get("chapter_title")] if v)
            children = [build_section(sec) for sec in ch.get("sections") or []]
            children.extend(build_article(art) for art in ch.get("articles") or [])
            return {
                "id": ch.get("chapter_id") or "",
                "type": "chapter",
                "title": ch_title,
                "text": "",
                "children": children,
            }

        def build_part(part):
            p_title = " ".join(v for v in [part.get("part_number"), part.get("part_title")] if v)
            return {
                "id": part.get("part_id") or "",
                "type": "part",
                "title": p_title,
                "text": "",
                "children": [build_chapter(ch) for ch in part.get("chapters") or []],
            }

        root_children = [build_part(p) for p in raw.get("parts") or []]
        root_children.extend(build_chapter(ch) for ch in raw.get("chapters") or [])
        root_children.extend(build_article(art) for art in raw.get("articles") or [])
        return {
            "id": doc_id,
            "type": "document",
            "title": title,
            "children": root_children,
        }, counts

    def tree(self, document_id):
        if document_id in self._pdf_trees:
            return self._pdf_trees[document_id]

        if document_id in self._demuc_root_id:
            root_id = self._demuc_root_id[document_id]
            doc_meta = self.documents[document_id]

            def sort_key(nid):
                node = self._nodes_by_id[nid]
                lbl = node.get("label")
                if lbl in ("Chuong", "Muc"):
                    m = re.search(r"(\d+)$", nid)
                    return (0, int(m.group(1)) if m else 0, "", nid)
                if lbl == "Dieu":
                    return (1, 0, _natural_tokens(node.get("mapc") or nid), nid)
                cl = node.get("clause_number") or ""
                pt = node.get("point_number") or ""
                cl_k = (0, int(cl), "") if str(cl).isdigit() else (1, 0, str(cl))
                return (2, cl_k, str(pt), nid)

            def node_title(node):
                lbl = node.get("label")
                if lbl == "SourceComponent" and (node.get("clause_number") or node.get("point_number")):
                    return (node.get("text") or "")[:90]
                if lbl == "Dieu":
                    ten = node.get("ten") or ""
                    doc_num = self._vanban_numbers.get(node.get("document_id"))
                    if ten and doc_num:
                        return f"{ten} ({doc_num})"
                    return ten or doc_num or node["id"]
                return node.get("ten") or node.get("article_number") or node["id"]

            def build_demuc_node(nid, visited):
                if nid in visited or nid not in self._nodes_by_id:
                    return None
                node = self._nodes_by_id[nid]
                next_visited = visited | {nid}
                child_ids = list(self._contains.get(nid, []))
                if node.get("label") == "Dieu":
                    source_art = self._derived_from.get(nid)
                    if source_art:
                        child_ids.extend(self._contains.get(source_art, []))
                children = []
                for cid in sorted(set(child_ids), key=sort_key):
                    item = build_demuc_node(cid, next_visited)
                    if item is not None:
                        children.append(item)
                return {
                    "id": nid,
                    "type": node.get("label", "component"),
                    "title": node_title(node),
                    "text": node.get("text") or node.get("source_quote") or "",
                    "article_number": node.get("article_number"),
                    "clause_number": node.get("clause_number"),
                    "point_number": node.get("point_number"),
                    "document_number": self._vanban_numbers.get(node.get("document_id"))
                    if node.get("label") == "Dieu" else None,
                    "children": children,
                }

            root = build_demuc_node(root_id, set())
            if root:
                root["title"] = f"Đề mục {document_id}: {doc_meta['title']}"
            return root

        # Fallback for individual VanBan lookups by id
        owned = {n["id"]: n for n in self.nodes if n.get("document_id") == document_id}
        if not owned:
            return None
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
        doc_title = self._vanban_numbers.get(document_id) or document_id
        return {"id": document_id, "type": "document", "title": doc_title,
                "children": [build(key, set()) for key in roots]}


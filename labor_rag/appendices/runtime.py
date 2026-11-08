"""Read-only local appendix catalog, attached to the existing cloud-backed retriever."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

from labor_rag.ingest.chunk_schema import ascii_fold, article_id
from .catalog import PROCESSED_DIR, load_manifest, local_path, read_json
from .graph import jsonl


def terms(text: str) -> set[str]:
    return {v for v in re.findall(r"[a-z0-9]+",ascii_fold(text).lower()) if len(v)>2 or v.isdigit()}


def usable(item: dict, today: str | None = None) -> bool:
    today=today or date.today().isoformat()
    return (item.get("review_status")!="needs_review" and item.get("kind")!="unknown" and item.get("still_valid",False)
            and (not item.get("effective_from_date") or item["effective_from_date"]<=today)
            and (not item.get("effective_to_date") or today<item["effective_to_date"]))


class AppendixCatalog:
    def __init__(self, directory: Path = PROCESSED_DIR):
        self.directory=directory
        self.reload()

    def reload(self):
        self.items={a["appendix_id"]:a for a in jsonl(self.directory/"appendices.jsonl")}
        self.chunks={c["chunk_id"]:c for c in jsonl(self.directory/"chunks.jsonl")}
        self.artifacts=read_json(self.directory/"artifacts.json",{})
        path=self.directory/"artifacts.json"
        self._storage_mtime=path.stat().st_mtime_ns if path.exists() else None
        self.report=read_json(self.directory/"manifest.json",{})
        from labor_rag.config import LAO_DONG_DIR
        nodes={n["id"]:n for n in jsonl(LAO_DONG_DIR/"kg_nodes.jsonl")}
        self.article_neighbors={}
        for edge in jsonl(LAO_DONG_DIR/"kg_edges.jsonl"):
            if edge["type"] not in {"REFERS_TO","CITES_COMPONENT","IMPLEMENTS_COMPONENT"}:
                continue
            left,right=nodes.get(edge["source"],{}),nodes.get(edge["target"],{})
            if left.get("document_id") and left.get("article_number") and right.get("document_id") and right.get("article_number"):
                key=(left["document_id"],str(left["article_number"]))
                self.article_neighbors.setdefault(key,set()).add((right["document_id"],str(right["article_number"])))
        self.last_attachments=[]
        self.last_warnings=[]
        from .extract import reference_rows
        self.references=reference_rows()

    def public_item(self, item: dict, *, detail: bool = False) -> dict:
        self.refresh_storage()
        result={k:v for k,v in item.items() if k not in {"blocks","text"}}
        key=quote(item["appendix_id"],safe="")
        result["view_url"]=f"/api/appendices/{key}/view"
        result["files"]=[]
        for file_id in item.get("artifact_ids",[]):
            artifact=self.artifacts.get(file_id)
            if artifact:
                result["files"].append({k:artifact.get(k) for k in ["artifact_id","file_name","format","bytes","role","source_url"]})
                result["files"][-1].update({"download_url":f"/api/files/{quote(file_id,safe='')}?download=true",
                                           "view_url":f"/api/files/{quote(file_id,safe='')}","label":"File nguồn; có thể chứa toàn văn và nhiều phụ lục"})
                remote=artifact.get("storage_backend")=="r2" and bool(artifact.get("r2",{}).get("verified_at"))
                result["files"][-1]["storage_backend"]=artifact.get("storage_backend","local")
                try:
                    result["files"][-1]["available"] = remote or local_path(artifact["path"]).is_file()
                except (ValueError, KeyError):
                    result["files"][-1]["available"] = remote
        if detail:
            result["text"]=item["text"]
        return result

    def find(self, query: str, *, kind: str | None = None) -> list[dict]:
        needles=terms(query)
        hits=[]
        for item in self.items.values():
            if kind and item["kind"]!=kind:
                continue
            metadata=item["title"]+" "+item["document_number"]+" "+" ".join(item["forms"])+" "+item["text"][:2500]
            score=len(needles & terms(metadata))
            requested=re.search(r"mau\s+(?:so\s*)?(\d+[a-z]?(?:/pl[ivx\d]+)?)",ascii_fold(query).lower())
            if requested and any(value.lower().lstrip("0")==requested[1].lstrip("0") for value in item["forms"]):
                score+=10
            if score:
                hits.append((score,item))
        return [item for _,item in sorted(hits,key=lambda pair:pair[0],reverse=True)]

    def augment(self, query: str, evidences: list, *, limit: int = 6) -> list:
        from labor_rag.retrieval.hybrid_retrieve import Evidence
        seeds={(e.document_id,str(e.meta_dieu)) for e in evidences if e.meta_dieu}
        seeds |= {neighbor for seed in list(seeds) for neighbor in self.article_neighbors.get(seed,set())}
        direct={e.appendix_id for e in evidences if e.appendix_id}
        linked={a["appendix_id"] for a in self.items.values()
                if any((ref["document_id"],str(ref["article_number"])) in seeds for ref in a["article_ids"])}
        candidates=direct|linked
        warnings=[]
        from labor_rag.ingest.chunk_schema import make_document_id
        for ref in self.references:
            seed=(make_document_id(ref["owner_document"]),ref["article"].rsplit(".",1)[-1])
            if seed not in seeds:
                continue
            target=make_document_id(ref["target_document"])
            label=ref.get("canonical_label")
            matches=[a for a in self.items.values() if a["document_id"]==target and (not label or a["key"]==label)]
            if not any(usable(a) for a in matches):
                warnings.append(f"Dẫn chiếu phụ lục {ref.get('label') or '(không ghi số)'} của {ref['target_document']}: chưa có nội dung đã xác minh và còn hiệu lực trong kho. Cần đối chiếu nguồn; không suy ra danh mục từ tên phụ lục.")
        # Metadata search also handles requests for unembedded forms.
        is_form_query=any(word in ascii_fold(query).lower() for word in ["mau","to khai","tai ve","don de nghi"])
        if is_form_query:
            candidates.update(a["appendix_id"] for a in self.find(query)[:3] if a["kind"]=="form")
        needles=terms(query)
        selected=[]
        seen={e.chunk_id for e in evidences}
        for chunk in self.chunks.values():
            if chunk["appendix_id"] not in candidates or not usable(self.items.get(chunk["appendix_id"],{})) or chunk["chunk_id"] in seen:
                continue
            score=len(needles & terms(chunk["text"]))
            selected.append((score,chunk))
        picked=sorted(selected,key=lambda pair:pair[0],reverse=True)[:limit]
        for _,chunk in picked:
            evidences.append(Evidence.from_payload(chunk,"appendix:linked"))
        added=len(picked)
        attachments=[]
        for appendix_id in candidates:
            item=self.items.get(appendix_id)
            if item:
                attachments.append(self.public_item(item))
                if usable(item) and added<limit and item["kind"]=="form" and not any(e.appendix_id==appendix_id for e in evidences):
                    payload={"chunk_id":appendix_id,"appendix_id":appendix_id,"appendix_number":item["number"],
                             "document_id":item["document_id"],"document_number":item["document_number"],
                             "ten":item["title"],"artifact_ids":item["artifact_ids"],"source_url":item["source_url"],
                             "text":f"Metadata biểu mẫu: {item['title']}. Các số mẫu nhận diện: {', '.join(item['forms']) or 'xem file nguồn'}. File nguồn có sẵn để xem/tải; không suy ra nội dung chưa cung cấp.","chunk_type":"appendix"}
                    evidences.append(Evidence.from_payload(payload,"appendix:form-metadata"))
                    added+=1
        self.last_attachments=sorted(attachments,key=lambda a:a["appendix_id"])
        self.last_warnings=list(dict.fromkeys(warnings))
        return evidences

    def refresh_storage(self):
        path=self.directory/"artifacts.json"
        modified=path.stat().st_mtime_ns if path.exists() else None
        if modified!=self._storage_mtime:
            self.artifacts=read_json(path,{})
            self._storage_mtime=modified

    def artifact(self, artifact_id: str):
        self.refresh_storage()
        artifact=self.artifacts.get(artifact_id)
        if not artifact:
            raise KeyError(artifact_id)
        return artifact

    def file_path(self, artifact_id: str):
        artifact=self.artifact(artifact_id)
        path=local_path(artifact["path"])
        if not path.is_file():
            raise FileNotFoundError(path.name)
        return path,artifact

    def render(self, appendix_id: str, chunk_id: str | None = None) -> str:
        import html
        item=self.items[appendix_id]
        chunk=self.chunks.get(chunk_id or "",{})
        highlights=set(chunk.get("locator",{}).get("block_ids",[])) if chunk.get("appendix_id")==appendix_id else set()
        body="\n".join(block["html"] for block in item["blocks"])
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(body,"lxml")
        for block_id in highlights:
            found=soup.find(id=block_id)
            if found:
                found["class"]="highlight"
        body="".join(str(n) for n in (soup.body or soup).contents)
        return f'''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(item['title'])}</title><style>body{{font:16px/1.65 system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 20px;color:#172c35}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border:1px solid #ccd7dc;padding:8px;vertical-align:top}}.highlight,.highlight td{{background:#fff0a5}}h1{{font-size:23px}}.meta{{color:#526c77}}</style>
<h1>{html.escape(item['title'])}</h1><p class="meta">Phụ lục {html.escape(item['number'])} · {html.escape(item['document_number'])} · {html.escape(item['review_status'])}</p>{body}
<script>const e=document.querySelector('.highlight');if(e)e.scrollIntoView({{block:'center'}})</script></html>'''

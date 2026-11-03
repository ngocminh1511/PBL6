"""Extract actual appendix headings and table/form blocks; never ingest the document's articles."""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup, Tag, NavigableString, Comment

from labor_rag.ingest.chunk_schema import MAX_TOKENS, TokenCounter, ascii_fold, content_hash, make_document_id, split_sentences
from labor_rag.appendices.labels import canonical_label
from .catalog import INTERIM_DIR, INVENTORY_DIR, PROCESSED_DIR, RAW_DIR, ROOT_DIR, load_manifest, local_path, now, read_json, register_bytes, relative, sha256, write_json, write_jsonl

HEADING = re.compile(r"^ph[ụu]\s*l[ụu]c\s*(?:s[ốo]\s*)?([IVXLCDM]+[ab]?|\d+[ab]?)?(?:\s*[.:–—-]\s*(.*))?$", re.I)
FORM_HEADING = re.compile(r"^m[ẫa]u\s+(?:s[ốo]\s*)?(\d+[a-z]?(?:/PL[IVX\d]+)?)(?:\s*[.:]\s*(.*))?$", re.I)
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"}
SAFE_TAGS = BLOCK_TAGS | {"div", "span", "strong", "em", "b", "i", "u", "li", "thead", "tbody", "tfoot", "tr", "td", "th", "br", "sup", "sub"}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def plain_text(node) -> str:
    # Word HTML can split Vietnamese glyphs across inline font/span tags.
    # Keep existing spaces instead of inserting spaces inside every word.
    return "".join(str(child) if isinstance(child,NavigableString) else " "
                   for child in node.descendants
                   if (isinstance(child,NavigableString) and not isinstance(child,Comment))
                   or (isinstance(child,Tag) and child.name in {"br","td","th","tr","p","div"}))


def sanitized(fragment: str) -> str:
    soup = BeautifulSoup(fragment, "lxml")
    for node in list(soup.find_all(["script", "style", "iframe", "object", "embed", "link", "meta", "input", "button", "textarea", "select"])):
        node.decompose()
    for node in list(soup.find_all(True)):
        if node.name in {"html", "body"}:
            continue
        if node.name not in SAFE_TAGS:
            node.unwrap()
            continue
        node.attrs = {k: str(v) for k, v in node.attrs.items()
                      if k in {"colspan", "rowspan"} and str(v).isdigit() and 0 < int(v) <= 100}
    return "".join(str(n) for n in (soup.body or soup).contents)


def blocks(node):
    for child in node.children:
        if not isinstance(child, Tag):
            if str(child).strip():
                yield BeautifulSoup(f"<p>{html.escape(str(child))}</p>", "lxml").p
            continue
        if child.name in {"script", "style", "head"}:
            continue
        if child.name in BLOCK_TAGS:
            yield child
        elif child.find(list(BLOCK_TAGS)):
            yield from blocks(child)
        elif child.get_text(" ", strip=True):
            yield child


def heading(text: str) -> tuple[str | None, str] | None:
    value = clean_text(text)
    if len(value) > 240 or re.search(r"\.(?:docx?|pdf|html)$", value, re.I):
        return None
    match = HEADING.fullmatch(value)
    if match:
        return match[1], (match[2] or "")
    # A heading can carry its uppercase title without a punctuation separator.
    match = re.match(r"^ph[ụu]\s*l[ụu]c\s+(?:s[ốo]\s*)?([IVXLCDM]+[ab]?|\d+[ab]?)\s+(.+)$", value, re.I)
    if match and match[2][:1].isupper() and not match[2].lower().startswith("ban hành"):
        return match[1], match[2]
    return None


def classify(title: str, text: str, forms: list[str], virtual_form: bool) -> str:
    if virtual_form:
        return "form"
    folded = ascii_fold(title).lower()
    reference = any(s in folded for s in ["danh muc", "muc tran", "dinh muc", "quy trinh", "chuong trinh", "doi chieu", "lo trinh", "tuoi nghi huu", "bang tuoi"])
    form = any(s in folded for s in ["bieu mau", "mau so", "to khai", "mau don", "cac mau", "mau ban", "mau bien ban", "mau giay", "mau hop dong", "mau bao cao", "mau de nghi"])
    if reference:
        return "mixed" if forms else "reference"
    if form or forms:
        return "form"
    return "unknown"


def normalize_sections(content: str, document_id: str) -> list[dict]:
    soup = BeautifulSoup(content, "lxml")
    items = list(blocks(soup.body or soup))
    first_formal = next((i for i,e in enumerate(items) if heading(clean_text(plain_text(e)))),len(items))
    last_article = max((i for i,e in enumerate(items[:first_formal])
                        if re.match(r"^Điều\s+\d+[a-zđ]?\.",clean_text(plain_text(e)))),default=-1)
    sections, current, unnumbered = [], None, 0
    for index, element in enumerate(items):
        text = clean_text(plain_text(element))
        if not text:
            continue
        match = heading(text)
        form_match = FORM_HEADING.fullmatch(text) if len(text) < 240 else None
        folded = ascii_fold(text).lower()
        standalone_title = any(folded.startswith(s) for s in ["danh muc ", "quy trinh ", "chuong trinh ", "dinh muc "])
        next_text = " ".join(clean_text(plain_text(e)) for e in items[index+1:index+4])
        if (not match and current is None and index > last_article and standalone_title and len(text) < 300
                and "ban hanh kem theo" in ascii_fold(next_text).lower()):
            match = (None, text)
        new_form = bool(form_match and (current is None or current.get("virtual_form")))
        if match or new_form:
            if match:
                label, title = match
                if label:
                    key = canonical_label(label)
                else:
                    unnumbered += 1
                    key = f"u{unnumbered}"
                display = label or "Không đánh số"
            else:
                key = "form"+re.sub(r"[^a-z0-9]+","-",form_match[1].lower())
                display, title = f"Mẫu {form_match[1]}", form_match[2] or text
            # Repeated page headings continue the same appendix.
            if current and current["key"] == key and match and not title:
                continue
            if any(s["key"] == key for s in sections):
                # Do not silently merge distinct sections sharing a number.
                key += f"-section{len(sections)+1}"
            current = {"appendix_id": f"{document_id}:pl{key}", "key": key,
                       "number": display, "title": title, "virtual_form": new_form,
                       "elements": [], "forms": []}
            sections.append(current)
        if current is None:
            continue
        if form_match and form_match[1] not in current["forms"]:
            current["forms"].append(form_match[1])
        current["elements"].append(element)
    for section in sections:
        if not section["title"]:
            # Heading, issuing caption, then the actual title or forms table.
            for el in section["elements"][1:8]:
                candidate = clean_text(plain_text(el))
                folded = ascii_fold(candidate).lower()
                if (candidate and candidate.strip("_–—- .")
                        and not folded.startswith(("(ban hanh", "(kem theo", "ban hanh kem", "ngay "))):
                    section["title"] = candidate[:300]
                    break
        section["title"] = section["title"] or f"Phụ lục {section['number']}"
        normalized, cursor = [], 0
        for el in section.pop("elements"):
            safe = BeautifulSoup(sanitized(str(el)), "lxml")
            element = next((n for n in (safe.body or safe).children if isinstance(n, Tag)), None)
            if element is None:
                continue
            block_id = f"b{len(normalized):04d}"
            element["id"] = block_id
            rows = []
            if element.name == "table":
                for tr in element.find_all("tr"):
                    if tr.find_parent("table") is not element:
                        continue
                    row_text = " | ".join(clean_text(plain_text(td)) for td in tr.find_all(["td", "th"], recursive=False))
                    if not row_text.strip(" |"):
                        continue
                    row_id = f"{block_id}-r{len(rows):04d}"
                    tr["id"] = row_id
                    rows.append({"id": row_id, "text": row_text, "start": cursor, "end": cursor+len(row_text),
                                 "header": bool(tr.find("th") or tr.find_parent("thead")) or not rows})
                    cursor += len(row_text) + 1
                block_text = "\n".join(r["text"] for r in rows)
                start = rows[0]["start"] if rows else cursor
                end = rows[-1]["end"] if rows else cursor
            else:
                block_text = clean_text(plain_text(element))
                start, end = cursor, cursor + len(block_text)
                cursor = end + 1
            normalized.append({"id": block_id, "html": str(element), "text": block_text, "start": start, "end": end,
                               "rows": rows, "page": el.get("data-page")})
        section["blocks"] = normalized
        section["text"] = "\n".join(b["text"] for b in normalized)
        section["kind"] = classify(section["title"], section["text"], section["forms"], section["virtual_form"])
        section["content_hash"] = content_hash(section["text"])
        section["text_sha256"] = sha256(section["text"].encode("utf-8"))
    return sections


def fallback_html(document: dict, errors: list[str]) -> tuple[str, str | None]:
    for artifact in sorted(document.get("files", []), key=lambda f: {"docx": 0, "pdf": 1, "doc": 2}.get(Path(f["file_name"]).suffix.lstrip("."), 3)):
        path = local_path(artifact["path"])
        try:
            if path.suffix.lower() == ".docx":
                from docx import Document
                doc = Document(path)
                fragments = []
                from docx.oxml.ns import qn
                from docx.table import Table
                from docx.text.paragraph import Paragraph
                for child in doc.element.body:
                    if child.tag == qn("w:p"):
                        fragments.append(f"<p>{html.escape(Paragraph(child,doc).text)}</p>")
                    elif child.tag == qn("w:tbl"):
                        fragments.append("<table>"+"".join("<tr>"+"".join(f"<td>{html.escape(c.text)}</td>" for c in row.cells)+"</tr>" for row in Table(child,doc).rows)+"</table>")
                content = "".join(fragments)
            elif artifact.get("format") == "pdf":
                import pymupdf
                fragments = []
                with pymupdf.open(path) as pdf:
                    for page in pdf:
                        text = page.get_text(sort=True)
                        if len(text.strip()) < 40:
                            if not page.get_images():
                                continue
                            if os.getenv("APPENDIX_ENABLE_OCR", "0") != "1":
                                raise ValueError("Scanned PDF needs an explicit --ocr extraction run")
                            from labor_rag.ocr import extract_text
                            single = pymupdf.open()
                            single.insert_pdf(pdf, from_page=page.number, to_page=page.number)
                            text = extract_text(single.tobytes(), filename="appendix.pdf").clean_text()
                            single.close()
                        tables=page.find_tables().tables if len(page.get_text().strip())>=40 else []
                        ordered=[]
                        for table in tables:
                            rows=table.extract()
                            markup="<table>"+"".join("<tr>"+"".join(f"<{'th' if i==0 else 'td'}>{html.escape(str(cell or ''))}</{'th' if i==0 else 'td'}>" for cell in row)+"</tr>" for i,row in enumerate(rows))+"</table>"
                            ordered.append((table.bbox[1],markup))
                        if tables:
                            for block in page.get_text("blocks",sort=True):
                                if any(pymupdf.Rect(block[:4]).intersects(pymupdf.Rect(t.bbox)) for t in tables):
                                    continue
                                ordered.append((block[1],"".join(f'<p data-page="{page.number+1}">{html.escape(line)}</p>' for line in block[4].splitlines() if line.strip())))
                            fragments.extend(markup for _,markup in sorted(ordered,key=lambda pair:pair[0]))
                        else:
                            fragments.extend(f'<p data-page="{page.number+1}">{html.escape(line)}</p>' for line in text.splitlines() if line.strip())
                content = "".join(fragments)
            elif artifact.get("format") == "doc":
                executable = os.getenv("LIBREOFFICE_PATH") or shutil.which("soffice") or shutil.which("soffice.com")
                bundled = ROOT_DIR / "data/tools/libreoffice/program" / ("soffice.bin" if os.name == "nt" else "soffice")
                if not executable and bundled.is_file():
                    executable = str(bundled)
                if not executable:
                    raise ValueError("Legacy DOC conversion needs LIBREOFFICE_PATH or soffice on PATH")
                cached = INTERIM_DIR / "converted" / f"{artifact['sha256']}.html"
                if cached.is_file():
                    content = cached.read_text(encoding="utf-8")
                    if normalize_sections(content, document["document_id"]):
                        return content, artifact["artifact_id"]
                    continue
                with tempfile.TemporaryDirectory(prefix="pbl6_appendix_") as directory:
                    profile = Path(directory, "profile").as_uri()
                    command=[executable, f"-env:UserInstallation={profile}", "--headless", "--convert-to", "html", "--outdir", directory, str(path)]
                    for attempt in range(3):
                        converted_result=subprocess.run(command, capture_output=True, timeout=120)
                        # Direct Windows .bin startup requests a restart after creating a fresh profile.
                        if converted_result.returncode not in {79,81}:
                            break
                    converted_result.check_returncode()
                    converted = list(Path(directory).glob("*.html"))
                    if not converted:
                        raise ValueError("DOC conversion produced no HTML")
                    content = converted[0].read_text(encoding="utf-8", errors="replace")
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    cached.write_text(content, encoding="utf-8")
            else:
                continue
            if normalize_sections(content, document["document_id"]):
                return content, artifact["artifact_id"]
        except Exception as exc:
            errors.append(f"{artifact['file_name']}: {type(exc).__name__}: {str(exc)[:180]}")
    return "", None


def reference_rows() -> list[dict]:
    path = INVENTORY_DIR / "appendix_references.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [r for r in csv.DictReader(handle) if not r.get("excluded_reason") and r.get("origin") == "body"]


def article_links(section: dict, document: dict, refs: list[dict]) -> list[dict]:
    found = []
    for ref in refs:
        if ref["target_document"] != document["document"]:
            continue
        key = ref.get("canonical_label") or ""
        if key and key != section["key"]:
            continue
        if not key and section["key"].startswith("form"):
            label=re.sub(r"[^a-z0-9]+","-",ref.get("label", "").lower()).lstrip("0")
            if ref.get("reference_type") != "form" or label != section["key"][4:].lstrip("0"):
                continue
        elif not key and not section["key"].startswith("u"):
            continue
        code = ref["article"]
        source_number = code.rsplit(".", 1)[-1]
        found.append({"mapc": code, "document_id": make_document_id(ref["owner_document"]),
                      "article_number": source_number, "basis": "explicit_text_reference"})
    return list({(r["document_id"], r["article_number"]): r for r in found}.values())


def review_overrides(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {r["appendix_id"]: r for r in csv.DictReader(handle)}


def make_chunks(section: dict, count) -> list[dict]:
    if section["kind"] not in {"reference", "mixed"} or section["review_status"] == "needs_review":
        return []
    header = f"Phụ lục {section['number']} — {section['document_number']}\n{section['title']}"
    budget = MAX_TOKENS - count(header) - 16
    units = []
    in_form = False
    for block in section["blocks"]:
        if section["kind"] == "mixed" and FORM_HEADING.fullmatch(block["text"]):
            in_form = True
        if in_form:
            continue
        rows = block["rows"] or [block]
        table_header = "\n".join(r["text"] for r in rows if r.get("header")) if block["rows"] else ""
        for row in rows:
            pieces = [row["text"]] if count(row["text"]) <= budget else split_sentences(row["text"], max(64,budget-count(table_header)-8), count)
            for piece in pieces:
                units.append({"text": piece, "id": row["id"], "start": row["start"], "end": row["end"],
                              "table_header": table_header if not row.get("header") else ""})
    groups, current = [], []
    def render(rows):
        columns = rows[0].get("table_header") if rows else ""
        return "\n".join(p for p in [header, columns, *(r["text"] for r in rows)] if p)
    for unit in units:
        if current and count(render(current+[unit])) > MAX_TOKENS:
            groups.append(current)
            current = []
        current.append(unit)
    if current:
        groups.append(current)
    chunks = []
    for index, group in enumerate(groups, 1):
        text = render(group)
        if count(text) > MAX_TOKENS:
            raise ValueError(f"Chunk exceeds {MAX_TOKENS} tokens: {section['appendix_id']}")
        chunks.append({
            "chunk_id": section["appendix_id"] + (f":p{index}" if len(groups)>1 else ""),
            "chunk_type": "appendix", "source": "appendix", "appendix_id": section["appendix_id"],
            "appendix_number": section["number"], "document_id": section["document_id"],
            "document_number": section["document_number"], "kind": section["kind"],
            "mapc": None, "meta_dieu": None, "meta_khoan": None, "meta_de_muc": section["document_number"],
            "ten": section["title"], "text": text, "content_hash": content_hash(text),
            "article_ids": section["article_ids"], "artifact_ids": section["artifact_ids"],
            "source_url": section["source_url"], "locator": {"block_ids": list(dict.fromkeys(r["id"] for r in group)),
                "start": min(r["start"] for r in group), "end": max(r["end"] for r in group), "text_sha256": section["text_sha256"]},
            "still_valid": section["still_valid"], "effective_from_date": section["effective_from_date"],
            "effective_to_date": section["effective_to_date"], "version_date": section["version_date"],
        })
    return chunks


def process(*, count=None, raw_dir: Path = RAW_DIR, output_dir: Path = PROCESSED_DIR) -> dict:
    manifest = load_manifest(raw_dir)
    refs = reference_rows()
    overrides = review_overrides(INVENTORY_DIR / "review_overrides.csv")
    overrides.update(review_overrides(raw_dir / "review.csv"))
    count = count or TokenCounter()
    appendices, chunks, summary_rows = [], [], []
    for document_id, doc in manifest["documents"].items():
        print(f"Extracting {doc['document']}...", flush=True)
        errors = []
        source_file = next((f for f in doc.get("files", []) if f.get("role") == "document_html"), None)
        content = local_path(source_file["path"]).read_text(encoding="utf-8") if source_file else ""
        sections = normalize_sections(content, document_id) if content else []
        source_id = source_file["artifact_id"] if source_file else None
        for section in sections:
            section["_source_id"]=source_id
        expected={r["canonical_label"] for r in refs if r["target_document"]==doc["document"] and r.get("canonical_label")}
        if not sections or expected-{s["key"] for s in sections}:
            fallback, fallback_id = fallback_html(doc, errors)
            existing={s["key"] for s in sections}
            for section in normalize_sections(fallback, document_id) if fallback else []:
                if section["key"] not in existing:
                    section["_source_id"]=fallback_id
                    sections.append(section)
                    existing.add(section["key"])
        metadata = doc.get("metadata", {})
        effect_names = " ".join(str(v.get("name", "")) for k,v in metadata.items() if isinstance(v,dict) and any(s in k.lower() for s in ['effect','status']))
        folded_effect = ascii_fold(effect_names).lower()
        expired = "het hieu luc" in folded_effect and "mot phan" not in folded_effect
        for section in sections:
            override = overrides.get(section["appendix_id"], {})
            if override.get("kind") in {"reference", "form", "mixed", "unknown"}:
                section["kind"] = override["kind"]
            links = article_links(section, doc, refs)
            if override.get("article_ids"):
                links = json.loads(override["article_ids"])
            section.update({"document_id": document_id, "document_number": doc["document"],
                "article_ids": links, "artifact_ids": [f["artifact_id"] for f in doc.get("files", [])],
                "content_artifact_id": section.pop("_source_id", source_id), "source_url": doc.get("canonical_url") or doc.get("source_url"),
                "review_status": override.get("review_status") or ("needs_review" if section["kind"] in {"unknown", "mixed"} or "-section" in section["key"] else "auto_accepted"),
                "download_status": doc.get("download_status", "missing"),
                "effective_from_date": override.get("effective_from_date") or (metadata.get("effFrom") or "")[:10] or None,
                "effective_to_date": override.get("effective_to_date") or (metadata.get("effTo") or "")[:10] or None,
                "version_date": override.get("version_date") or (metadata.get("effFrom") or "")[:10] or None,
                "still_valid": not expired, "effect_status": effect_names, "application_note": metadata.get("applicationNote"),
                "replaces_appendix_ids": json.loads(override.get("replaces_appendix_ids") or "[]"),
                "review_notes": override.get("notes") or "",
            })
            if override.get("still_valid"):
                section["still_valid"] = override["still_valid"].lower() in {"true", "1", "yes"}
            section["extraction_status"] = "extracted"
            appendices.append(section)
            chunks.extend(make_chunks(section, count))
        missing_labels=sorted(expected-{s["key"] for s in sections})
        doc["extraction_status"] = ("partial" if missing_labels else "extracted") if sections else "needs_review"
        doc["extraction_errors"] = errors
        summary_rows.append({"document_id": document_id, "document": doc["document"], "download_status": doc.get("download_status"),
                             "appendices": len(sections), "extraction_status": doc["extraction_status"], "missing_labels":missing_labels, "errors": errors})
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "appendices.jsonl", appendices)
    write_jsonl(output_dir / "chunks.jsonl", chunks)
    normalized_dir=output_dir/"normalized"
    normalized_dir.mkdir(exist_ok=True)
    for section in appendices:
        target=normalized_dir/(section["appendix_id"].replace(":","_")+".html")
        target.write_text('<!doctype html><html lang="vi"><meta charset="utf-8"><body>'+"\n".join(b["html"] for b in section["blocks"])+"</body></html>",encoding="utf-8")
    write_json(output_dir / "artifacts.json", manifest["artifacts"])
    summary = {"generated_at": now(), "storage_backend": manifest.get("storage_backend","local"), "documents": summary_rows,
               "appendices": len(appendices), "chunks": len(chunks), "kinds": {k:sum(a["kind"]==k for a in appendices) for k in ["reference","form","mixed","unknown"]}}
    write_json(output_dir / "manifest.json", summary)
    review_path = raw_dir / "review.csv"
    if not review_path.exists():
        with review_path.open("w",encoding="utf-8-sig",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=["appendix_id","kind","review_status","article_ids","effective_from_date","effective_to_date","version_date","still_valid","notes"])
            writer.writeheader()
    with (output_dir / "review_queue.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=["appendix_id","document_number","number","title","kind","review_status","application_note"])
        writer.writeheader()
        writer.writerows({k:a.get(k) for k in writer.fieldnames} for a in appendices if a["review_status"]=="needs_review")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr", action="store_true", help="Enable existing VietOCR for scanned PDF pages")
    args = parser.parse_args()
    if args.ocr:
        os.environ["APPENDIX_ENABLE_OCR"] = "1"
    result = process()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

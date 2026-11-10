"""Inventory appendix download requirements from local Phap dien HTML.

Reads source HTML without changing it. Reports are evidence inventories, not
legal-validity assessments or a claim that every old attachment is unique.
Run from the repository root: python scripts/inventory_appendices.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup

from labor_rag.ingest.build_abox import BROKEN_NUMBER_RE, SOURCE_RE, normalize_number
from labor_rag.ingest.chunk_schema import ascii_fold, make_document_id
from labor_rag.appendices.labels import canonical_label
from labor_rag.ingest.parse_demuc_html import (
    _content_blocks,
    _structural_class,
    iter_dieu,
    parse_demuc_nodes,
    split_dieu_heading,
)

APPENDIX_RE = re.compile(r"ph[ụu]\s*l[ụu]c", re.IGNORECASE)
LABEL_RE = re.compile(r"^\s*(?:s[ốo]\s*)?((?:\d{1,3}|[IVXLCDM]+)(?:[abAB])?)(?![\w])", re.IGNORECASE)
EXTERNAL_RE = re.compile(
    r"(?:Nghị\s+định|Thông\s+tư(?:\s+liên\s+tịch)?|Quyết\s+định|Luật)\s+(?:số\s+)?"
    r"(?P<number>\d+[a-z]?/\d{4}/[\wĐđ/-]+)", re.IGNORECASE,
)
FILE_RE = re.compile(r"\.(?:docx?|pdf|xlsx?|zip|rar)(?:[?#]|$)", re.IGNORECASE)
FORM_RE = re.compile(r"m[ẫa]u\s+(?:s[ốo]\s+)?(?P<label>\d+[a-z]?)(?!\w)", re.IGNORECASE)


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def base_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def file_document(label: str, article: dict) -> tuple[str, str]:
    """Use a filename date only when it matches a cited source document."""
    match = re.search(r"(?<!\d)(\d{1,3})[_. /-]+((?:19|20)\d{2})(?!\d)", label)
    if not match:
        return article["document"], "article_source_default"
    pair = (int(match[1]), match[2])
    candidates = []
    for source in article["cited_documents"]:
        number = re.match(r"(\d+)/(\d{4})/", source)
        if number and (int(number[1]),number[2]) == pair:
            candidates.append(source)
    if len(set(candidates)) == 1:
        return candidates[0], "filename_matches_citation"
    return article["document"], "filename_document_mismatch"


def scan_file(path: Path) -> tuple[list[dict], list[dict], dict]:
    text = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(text, "lxml")
    parsed = [d for d, _ in iter_dieu(parse_demuc_nodes(path))]
    articles = []
    for ordinal, d in enumerate(parsed, 1):
        matches = list(SOURCE_RE.finditer(BROKEN_NUMBER_RE.sub("-", d["citation"] or "")))
        match = matches[0] if matches else None
        articles.append({
            "source_file": path.name, "article_ordinal": ordinal,
            "article": d["so_hieu"], "anchor": d["mapc"],
            "article_number": match["article"] if match else "",
            "document": normalize_number(match["number"]) if match else "",
            "cited_documents": [normalize_number(m["number"]) for m in matches],
            "title": d["tieu_de"], "paragraphs": d["paragraphs"],
            "source_urls": [], "attachments": [],
        })
    links, seen_anchors = [], set()
    current, ordinal = None, 0
    for block in _content_blocks(soup):
        cls = _structural_class(block)
        if cls == "pDieu":
            current = articles[ordinal]
            ordinal += 1
            assert current["article"] == split_dieu_heading(block.get_text(" ", strip=True))[0]
        elif cls == "pChuong":
            current = None
        anchors = ([block] if block.name == "a" and block.get("href") else []) + block.find_all("a", href=True)
        for anchor in anchors:
            if id(anchor) in seen_anchors:
                continue
            seen_anchors.add(id(anchor))
            url = anchor["href"]
            if current is not None and cls == "pGhiChu" and "vbpl" in url.lower():
                current["source_urls"].append(url)
            if "appfile" not in url.lower() and not FILE_RE.search(url):
                continue
            assert current is not None, f"Attachment outside article: {path.name}: {url}"
            attachment_label = compact(anchor.get_text(" ", strip=True))
            target, basis = file_document(attachment_label, current)
            row = {
                "source_file": path.name, "article_ordinal": current["article_ordinal"],
                "article": current["article"], "owner_document": current["document"],
                "document": target, "document_basis": basis,
                "attachment_label": attachment_label,
                "appfile_url": url, "extension": Path(urlsplit(url).path).suffix.lower(),
            }
            links.append(row)
            current["attachments"].append(row)
    assert ordinal == len(articles)
    raw_urls = [a["href"] for a in soup.find_all("a", href=True)
                if "appfile" in a["href"].lower() or FILE_RE.search(a["href"])]
    assert Counter(raw_urls) == Counter(row["appfile_url"] for row in links), path.name
    for article in articles:
        source_url = article["source_urls"][0] if article["source_urls"] else ""
        for link in article["attachments"]:
            link["owner_source_url"] = base_url(source_url)
            link["source_url"] = base_url(source_url) if link["document"] == article["document"] else ""
    return articles, links, {
        "source_file": path.name, "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "articles": len(articles), "attachment_links": len(links),
        "articles_with_links": sum(bool(a["attachments"]) for a in articles),
    }


def references(article: dict) -> list[dict]:
    labels = {r["attachment_label"] for r in article["attachments"]}
    body = "\n".join([article["title"], *(p for p in article["paragraphs"] if p not in labels)])
    rows = []
    text_sources = [("body", body, article["document"], "article_source_document")]
    for label in sorted(labels):
        link = next(r for r in article["attachments"] if r["attachment_label"] == label)
        text_sources.append(("attachment_label", label, link["document"], link["document_basis"]))
    for origin, text, default_doc, default_basis in text_sources:
        for match in APPENDIX_RE.finditer(text):
            tail = text[match.end():match.end() + 360]
            folded = ascii_fold(tail).lower().lstrip()
            reason = ""
            if re.match(r"hop\s*dong\b", folded):
                reason = "contract_appendix"
            elif re.match(r"quyet dinh huong\b", folded):
                reason = "individual_benefit_decision_appendix"
            elif re.match(r"ban hanh kem theo noi quy lao dong\b", folded):
                reason = "employer_internal_rules_appendix"
            elif re.search(r"\bbai bo\b[^.!?]*$", ascii_fold(text[max(0,match.start()-150):match.start()]).lower()):
                reason = "repeal_reference_only"
            label = LABEL_RE.match(tail)
            explicit = EXTERNAL_RE.search(tail[:240])
            # Once "this decree/circular" has been named, a later document
            # reference in the same paragraph must not reassign the appendix.
            own = re.search(r"(?:thong tu|nghi dinh|quyet dinh) nay\b", folded[:180])
            external = explicit and (not own or explicit.start() < own.start())
            target = normalize_number(explicit["number"].rstrip(".;,)")) if external else default_doc
            start, end = max(0, match.start()-100), min(len(text), match.end()+270)
            context = compact(text[start:end])
            rows.append({
                "source_file": article["source_file"], "article_ordinal": article["article_ordinal"],
                "article": article["article"], "owner_document": article["document"],
                "target_document": target,
                "reference_type": "appendix",
                "label": label[1] if label else "",
                "canonical_label": canonical_label(label[1]) if label else "",
                "origin": origin, "excluded_reason": reason,
                "target_basis": "explicit_external_document" if external else default_basis,
                "source_url": base_url(article["source_urls"][0]) if article["source_urls"] and target == article["document"] else "",
                "context": context,
            })
    # Some decrees attach numbered forms without calling them "Phu luc".
    for match in FORM_RE.finditer(body):
        tail = body[match.end():match.end()+220]
        folded = ascii_fold(tail).lower()
        if not re.search(r"ban hanh kem theo (?:thong tu|nghi dinh|quyet dinh)", folded):
            continue
        explicit = EXTERNAL_RE.search(tail)
        own = re.search(r"(?:thong tu|nghi dinh|quyet dinh) nay\b", folded)
        external = explicit and (not own or explicit.start() < own.start())
        target = normalize_number(explicit["number"].rstrip(".;,)")) if external else article["document"]
        rows.append({
            "source_file": article["source_file"], "article_ordinal": article["article_ordinal"],
            "article": article["article"], "owner_document": article["document"],
            "target_document": target, "reference_type": "form",
            "label": match["label"], "canonical_label": "", "origin": "body",
            "excluded_reason": "", "target_basis": "explicit_external_document" if external else "article_source_document",
            "source_url": base_url(article["source_urls"][0]) if article["source_urls"] and target == article["document"] else "",
            "context": compact(body[max(0,match.start()-90):match.end()+250]),
        })
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/raw/bophapdien/linh_vuc/lao_dong")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/reports/appendix_inventory")
    parser.add_argument("--verbose", action="store_true", help="Print per-document details")
    args = parser.parse_args()
    articles, links, file_stats = [], [], []
    for path in sorted(args.input.glob("*.html")):
        records, attachments, stats = scan_file(path)
        articles.extend(records)
        links.extend(attachments)
        file_stats.append(stats)
    refs = [r for article in articles for r in references(article)]
    refs_by_doc, links_by_doc = defaultdict(list), defaultdict(list)
    for row in refs:
        if not row["excluded_reason"]:
            refs_by_doc[row["target_document"]].append(row)
    for row in links:
        links_by_doc[row["document"]].append(row)
    sources_by_doc = defaultdict(set)
    for article in articles:
        sources_by_doc[article["document"]].update(base_url(u) for u in article["source_urls"])
    for row in links:
        if not row["source_url"] and sources_by_doc.get(row["document"]):
            row["source_url"] = sorted(sources_by_doc[row["document"]])[0]
    for row in refs:
        if not row["source_url"] and sources_by_doc.get(row["target_document"]):
            row["source_url"] = sorted(sources_by_doc[row["target_document"]])[0]
    documents = []
    for doc in sorted(refs_by_doc.keys() | links_by_doc.keys(), key=make_document_id):
        doc_refs, doc_links = refs_by_doc.get(doc, []), links_by_doc.get(doc, [])
        labels_by_key = defaultdict(set)
        for ref in doc_refs:
            if ref["canonical_label"]:
                labels_by_key[ref["canonical_label"]].add(ref["label"])
        labels_display = ["/".join(sorted(labels_by_key[k])) for k in sorted(labels_by_key, key=lambda k:(int(re.match(r'\d+', k)[0]), k))]
        sources = sorted({base_url(u) for a in articles if a["document"] == doc for u in a["source_urls"]})
        inline = []
        for article in articles:
            if article["document"] == doc:
                for paragraph in article["paragraphs"]:
                    if re.fullmatch(r"PHỤ\s*LỤC\s+(?:\d{1,3}|[IVXLCDM]+)", paragraph.strip()):
                        inline.append(paragraph.strip())
        groups = {compact(ascii_fold(r["attachment_label"]).lower()) for r in doc_links}
        documents.append({
            "document": doc, "document_id": make_document_id(doc),
            "source_files": "; ".join(sorted({r["source_file"] for r in doc_refs + doc_links})),
            "attachment_links": len(doc_links),
            "filename_groups": len(groups),
            "articles_with_links": len({(r["source_file"],r["article_ordinal"]) for r in doc_links}),
            "articles_referencing": len({(r["source_file"],r["article_ordinal"]) for r in doc_refs}),
            "numbered_appendices_detected": len(labels_by_key), "appendix_labels": "; ".join(labels_display),
            "form_labels_detected": "; ".join(sorted({r["label"] for r in doc_refs if r["reference_type"] == "form"})),
            "related_amending_documents": "; ".join(sorted({s for a in articles if a["document"] == doc
                for s in a["cited_documents"][1:]})),
            "unspecified_reference_count": sum(r["reference_type"] == "appendix" and not r["canonical_label"] for r in doc_refs),
            "source_url": sources[0] if sources else "",
            "inline_appendix_headings": "; ".join(sorted(set(inline))),
            "article_title_examples": "; ".join(dict.fromkeys(a["title"] for a in articles if a["document"] == doc))[:450],
            "discovery": "attachment_link" if doc_links else (
                "text_reference_only" if any(r["reference_type"] == "appendix" for r in doc_refs) else "text_form_reference_only"),
            "download_status": "not_checked", "review_status": "needs_review",
        })
    args.output.mkdir(parents=True, exist_ok=True)
    asset_groups = defaultdict(list)
    for row in links:
        key = (row["document"], compact(ascii_fold(row["attachment_label"]).lower()))
        asset_groups[key].append(row)
    assets = []
    for (doc, filename), rows in sorted(asset_groups.items()):
        assets.append({
            "document": doc, "attachment_label": rows[0]["attachment_label"],
            "normalized_label": filename, "original_url_count": len({r["appfile_url"] for r in rows}),
            "article_count": len({(r["source_file"],r["article_ordinal"]) for r in rows}),
            "articles": "; ".join(sorted({r["article"] for r in rows})),
            "source_url": next((r["source_url"] for r in rows if r["source_url"]), ""),
            "example_appfile_url": rows[0]["appfile_url"],
            "review_required": any(r["document_basis"] == "filename_document_mismatch" for r in rows),
        })
    appendix_groups = defaultdict(list)
    for row in refs:
        if not row["excluded_reason"] and row["canonical_label"]:
            appendix_groups[(row["target_document"], row["canonical_label"])].append(row)
    numbered_appendices = []
    for (doc, label), rows in sorted(appendix_groups.items()):
        numbered_appendices.append({
            "document": doc, "canonical_label": label,
            "labels_in_html": "; ".join(sorted({r["label"] for r in rows})),
            "articles": "; ".join(sorted({r["article"] for r in rows})),
            "source_url": next((r["source_url"] for r in rows if r["source_url"]), ""),
            "evidence": next((r["context"] for r in rows if r["origin"] == "body"),rows[0]["context"]),
        })
    write_csv(args.output / "attachment_links.csv", links,
              ["source_file","article_ordinal","article","owner_document","document","document_basis","attachment_label","extension","appfile_url","source_url","owner_source_url"])
    write_csv(args.output / "appendix_references.csv", refs,
              ["source_file","article_ordinal","article","owner_document","target_document","reference_type","label","canonical_label","origin","excluded_reason","target_basis","source_url","context"])
    write_csv(args.output / "documents.csv", documents, list(documents[0]) if documents else ["document"])
    write_csv(args.output / "file_groups.csv", assets, list(assets[0]) if assets else ["document"])
    write_csv(args.output / "numbered_appendices.csv", numbered_appendices,
              list(numbered_appendices[0]) if numbered_appendices else ["document"])
    summary = {
        "input": str(args.input.relative_to(ROOT)) if args.input.is_relative_to(ROOT) else str(args.input),
        "files": file_stats, "articles": len(articles),
        "attachment_links": len(links), "unique_attachment_urls": len({r["appfile_url"] for r in links}),
        "articles_with_links": sum(bool(a["attachments"]) for a in articles),
        "attachment_documents": len(links_by_doc), "extensions": dict(Counter(r["extension"] for r in links)),
        "attachment_owner_documents": len({r["owner_document"] for r in links}),
        "filename_groups": sum(d["filename_groups"] for d in documents),
        "filename_document_mismatches": sum(r["document_basis"] == "filename_document_mismatch" for r in links),
        "candidate_documents": len(documents),
        "text_only_documents": len([d for d in documents if d["discovery"] != "attachment_link"]),
        "form_only_additional_documents": [d["document"] for d in documents if d["discovery"] == "text_form_reference_only"],
        "numbered_appendices_detected": sum(d["numbered_appendices_detected"] for d in documents),
        "documents_without_numbered_appendices": sum(not d["numbered_appendices_detected"] for d in documents),
        "excluded_reference_counts": dict(Counter(r["excluded_reason"] for r in refs if r["excluded_reason"])),
    }
    assert sum(d["attachment_links"] for d in documents) == len(links)
    assert sum(d["filename_groups"] for d in documents) == len(assets)
    assert summary["numbered_appendices_detected"] == len(numbered_appendices)
    assert summary["candidate_documents"] == summary["attachment_documents"] + summary["text_only_documents"]
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k != "files"}, ensure_ascii=False, indent=2))
    if args.verbose:
        for d in documents:
            print(json.dumps({k:d[k] for k in ["document","attachment_links","numbered_appendices_detected","appendix_labels","unspecified_reference_count","discovery"]},ensure_ascii=False))


if __name__ == "__main__":
    main()

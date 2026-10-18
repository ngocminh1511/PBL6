"""The ABox of one loaded PDF: the document, its Dieu, and what it changes in
other documents, with the same URIs as the Phap dien ABox (build_abox), so
ontology_to_jsonl merges them into one graph and Neo4j gets them too.

- vld:LegalDocument for the PDF (vld:effectiveDate only when the Phap dien
  ABox does not date it already: an interval has one validFrom);
- vld:Article per Dieu (vld:itemNumber, vld:heading), linked by vld:hasArticle;
- per khoan of an amending Dieu: vld:Clause + one vlt:AmendmentEvent per
  amended Dieu (vlr:amendmentAction, vlr:amendmentScope, vlt:amendsAt), not
  marked consolidated: the amended Dieu's text does not include it;
- per document named in "... thay thế / hết hiệu lực ...": vlr:replaces, and
  vlt:validTo = this document's effective date on the replaced one.

Written by pdf_to_chunks to ontology/abox/pdf/<document_id>.ttl.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

from rdflib import Literal, RDFS

from labor_rag.ingest.amending import replaced_documents
from labor_rag.ingest.build_abox import VLD, AboxBuilder
from labor_rag.ingest.chunk_schema import nfc
from labor_rag.ocr.schemas import LegalDocument

if TYPE_CHECKING:
    from labor_rag.ingest.pdf_to_chunks import KgIndex


def document_abox(doc: LegalDocument, kg: "KgIndex | None" = None) -> tuple[AboxBuilder | None, dict]:
    """(builder holding the ABox, counts); builder is None without a document number."""
    from labor_rag.ingest.pdf_to_chunks import amending_units, article_body, iter_articles

    meta = doc.metadata
    if not meta.so_hieu:
        return None, {}
    known = kg.document(doc.document_id) if kg else None
    builder = AboxBuilder()
    doc_uri = builder.document(
        meta.loai_van_ban or "Văn bản",
        meta.so_hieu,
        None,
        None if known else (meta.ngay_hieu_luc or None),
        meta.ngay_ban_hanh or None,
    )
    effective = (known or {}).get("effective_date") or meta.ngay_hieu_luc or None
    stats: Counter = Counter()
    seen: set[str] = set()
    for _, _, _, article in iter_articles(doc):
        meta_dieu = re.sub(r"^Điều\s+", "", article.article_number).strip()
        if meta_dieu in seen:
            continue  # an OCR misread; pdf_to_chunks keeps the first too
        seen.add(meta_dieu)
        article_uri = builder.source_article(doc_uri, meta_dieu)
        builder.add(doc_uri, VLD.hasArticle, article_uri)
        title = nfc(article.article_title.strip())
        if title:
            builder.add(article_uri, VLD.heading, Literal(title, lang="vi"))
        builder.add(article_uri, RDFS.label, Literal(nfc(f"Điều {meta_dieu}. {title}".strip(". ")), lang="vi"))
        stats["articles"] += 1

        for targets, khoan, _ in amending_units(article) or []:
            amending_uri = builder.source_clause(article_uri, doc_uri, khoan) if khoan else article_uri
            for target in targets:
                target_doc = builder.document(target.document.kind, target.document.number, None, None)
                amended_uri = builder.source_article(target_doc, target.dieu)
                builder.add_amendment(
                    amended_uri, target_doc, amending_uri, doc_uri, target.actions, effective, target.scope
                )
                stats["amendments"] += 1

        for ref in replaced_documents(article.article_title, nfc(article_body(article)), doc.document_id):
            builder.add_replacement(doc_uri, builder.document(ref.kind, ref.number, None, None), effective)
            stats["replaces"] += 1
    builder.finish_documents()
    return builder, dict(stats)

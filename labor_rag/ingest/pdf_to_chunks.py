"""Turn an OCR'd legal document (PDF/image, or a saved OCR tree) into chunk
schema v5 (docs/structural_jsonl.md), the same layout as the Phap dien chunks.

One chunk per Dieu, ids from the document number + the Dieu number, long
Dieu split by chunk_schema.split_article. When the document is already in
the Phap dien KG (kg_nodes.jsonl of LAO_DONG_DIR), each Dieu gets its mapc
and the document its Phap dien title and effective date, so the PDF chunks
line up with the Phap dien ones. Footnotes cut from the page bottoms are
written next to the chunks; reading their amendments is not done yet.

A Dieu that amends another document ("Sửa đổi, bổ sung một số điều của ...")
is cut per khoan instead of by length: each part starts with the change it
makes ("Sửa đổi khoản 2 Điều 35 Nghị định số 145/2020/NĐ-CP (Điều 35. ...)")
and has meta_khoan = that khoan.

What the document changes in others (amendments per khoan, replaced
documents) goes into its ABox, ontology/abox/pdf/<document_id>.ttl
(labor_rag/ingest/pdf_abox.py), not into the chunks: the graph is the one
place that holds it, and Qdrant only gets the validity dates derived from it.

Usage (from the repository root):
    python -m labor_rag.ingest.pdf_to_chunks --input docs/Luat_lao_dong.pdf
    python -m labor_rag.ingest.pdf_to_chunks --from-json data/interim/pdf_chunks/45-2019-qh14_hierarchical.jsonl
Then put its ABox into the graph and load the chunks without rebuilding the collection:
    python -m labor_rag.ingest.ontology_to_jsonl
    python -m labor_rag.ingest.load_neo4j --replace-dataset
    python -m labor_rag.ingest.embed_and_index --chunks data/interim/pdf_chunks/45-2019-qh14_chunks.jsonl --upsert
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterator

from labor_rag.config import INTERIM_DIR, LAO_DONG_DIR, PDF_ABOX_DIR
from labor_rag.ingest.amending import Target, document_in, is_amending, parse_targets
from labor_rag.ingest.chunk_schema import (
    MAX_TOKENS,
    Counter,
    TokenCounter,
    build_header,
    content_hash,
    heading_number,
    make_chunk_id,
    make_document_id,
    nfc,
    split_article,
)
from labor_rag.ocr.schemas import Article, Chapter, Clause, LegalDocument, Section

DEFAULT_OUT_DIR = INTERIM_DIR / "pdf_chunks"


class KgIndex:
    """Lookups into the Phap dien projection (kg_nodes.jsonl, schema v5)."""

    def __init__(
        self,
        mapc_by_article: dict[tuple[str, str], str],
        documents: dict[str, dict],
        titles: dict[tuple[str, str], str] | None = None,
    ) -> None:
        self.mapc_by_article = mapc_by_article
        self.documents = documents
        self.titles = titles or {}

    @classmethod
    def load(cls, kg_dir: Path) -> "KgIndex":
        mapc_by_article: dict[tuple[str, str], str] = {}
        documents: dict[str, dict] = {}
        titles: dict[tuple[str, str], str] = {}
        for line in (kg_dir / "kg_nodes.jsonl").read_text(encoding="utf-8").splitlines():
            node = json.loads(line)
            if node.get("label") == "Dieu" and node.get("document_id") and node.get("article_number"):
                key = (node["document_id"], str(node["article_number"]))
                mapc_by_article[key] = node["id"]
                if node.get("ten"):
                    titles[key] = str(node["ten"])
            elif node.get("label") == "VanBan" and node.get("document_number"):
                documents[make_document_id(str(node["document_number"]))] = node
        if not mapc_by_article:
            print(
                f"WARNING: no Dieu with document_id/article_number in {kg_dir}; "
                "regenerate it with ontology_to_jsonl (chunk schema v5) to get mapc values.",
                file=sys.stderr,
            )
        return cls(mapc_by_article, documents, titles)

    def mapc(self, document_id: str, meta_dieu: str) -> str | None:
        return self.mapc_by_article.get((document_id, meta_dieu))

    def title(self, document_id: str, meta_dieu: str) -> str | None:
        return self.titles.get((document_id, meta_dieu))

    def document(self, document_id: str) -> dict | None:
        return self.documents.get(document_id)


def heading(number: str | None, title: str | None) -> str | None:
    """'Chương I' + 'NHỮNG QUY ĐỊNH CHUNG' -> 'Chương I. NHỮNG QUY ĐỊNH CHUNG'."""
    if not number:
        return None
    return f"{number}. {title}" if title else number


def iter_articles(doc: LegalDocument) -> Iterator[tuple[str | None, Chapter | None, Section | None, Article]]:
    """(Phan heading, Chuong, Muc, Dieu) for every Dieu, in document order."""
    for article in doc.articles:
        yield None, None, None, article
    groups = [(None, chapter) for chapter in doc.chapters]
    groups += [(heading(part.part_number, part.part_title), chapter) for part in doc.parts for chapter in part.chapters]
    for part, chapter in groups:
        for article in chapter.articles:
            yield part, chapter, None, article
        for section in chapter.sections:
            for article in section.articles:
                yield part, chapter, section, article


def clause_number(clause: Clause) -> str:
    return re.sub(r"^Khoản\s+", "", clause.clause_number).strip()


def clause_lines(clause: Clause) -> list[str]:
    lines = [f"{clause_number(clause)}. {clause.text}".strip()]
    return lines + [f"{point.point_label}) {point.text}".strip() for point in clause.points]


def article_body(article: Article) -> str:
    """The Dieu as lines "lead", "1. ...", "a) ...", the layout split_article
    expects; the OCR tree strips these markers and joins lines with spaces."""
    lines = [article.full_text.strip()] if article.full_text.strip() else []
    for clause in article.clauses:
        lines += clause_lines(clause)
    return "\n".join(lines)


ACTION_WORDS = {"sua_doi": "sửa đổi", "bo_sung": "bổ sung", "bai_bo": "bãi bỏ", "thay_cum_tu": "thay cụm từ"}


def change_line(target: Target, kg: KgIndex | None) -> str:
    """'Sửa đổi, bổ sung khoản 2 Điều 35 Nghị định số 145/2020/NĐ-CP (Điều 35. Trợ cấp thôi việc)'."""
    words = ", ".join(ACTION_WORDS[action] for action in target.actions)
    known = kg.document(target.document.document_id) if kg else None
    document = str(known["ten"]) if known else f"{target.document.kind} số {target.document.number}"
    where = f"{target.scope} Điều {target.dieu}" if target.scope else f"Điều {target.dieu}"
    title = kg.title(target.document.document_id, target.dieu) if kg else None
    suffix = f" (Điều {target.dieu}. {title})" if title else ""
    return nfc(f"{words[:1].upper()}{words[1:]} {where} {document}{suffix}")


def amending_units(article: Article) -> list[tuple[list[Target], str | None, str]] | None:
    """[(targets, khoan, body)], one per khoan of an amending Dieu; None when
    the Dieu amends nothing that can be read."""
    if not is_amending(article.article_title):
        return None
    default_document = document_in(article.article_title) or document_in(article.full_text)
    units = [
        (parse_targets(clause.text, default_document), clause_number(clause), "\n".join(clause_lines(clause)))
        for clause in article.clauses
    ]
    if not units:  # "Điều 2. Bãi bỏ Điều 10 Nghị định số ..." without khoan
        instruction = f"{article.article_title} {article.full_text}"
        units = [(parse_targets(instruction, default_document), None, article_body(article))]
    return units if any(targets for targets, _, _ in units) else None


def document_to_chunks(
    doc: LegalDocument,
    kg: KgIndex | None = None,
    count: Counter | None = None,
    max_tokens: int = MAX_TOKENS,
    text_variant: str = "full",
) -> tuple[list[dict], list[str]]:
    """(chunks, warnings) for one document. Without a token counter a Dieu is
    never split."""
    meta = doc.metadata
    document_id = doc.document_id
    known = kg.document(document_id) if kg else None
    if known:
        meta_de_muc = str(known["ten"])  # same title as the Phap dien chunks of this document
    elif meta.so_hieu:
        meta_de_muc = f"{meta.loai_van_ban or 'Văn bản'} số {meta.so_hieu}"
    else:
        meta_de_muc = doc.title or document_id
    meta_de_muc = nfc(meta_de_muc)
    effective_from = (known or {}).get("effective_date") or meta.ngay_hieu_luc or None
    common = {
        "document_id": document_id,
        "source": "pdf",
        "meta_de_muc": meta_de_muc,
        "pd_chuong": None,
        "pd_muc": None,
        "effective_from_date": effective_from,
        # Set when a later document replaces this one (in the graph).
        "effective_to_date": (known or {}).get("valid_to"),
        "version_date": meta.version_date or effective_from,
        "still_valid": True,
    }

    def split(header: str, body: str) -> list[tuple[str, str | None]]:
        if count:
            return split_article(header, body, count, max_tokens)
        return [("\n".join(part for part in [header, body] if part), None)]

    chunks: list[dict] = []
    warnings: list[str] = []
    seen: dict[str, str] = {}
    for part, chapter, section, article in iter_articles(doc):
        meta_dieu = re.sub(r"^Điều\s+", "", article.article_number).strip()
        article_key = make_chunk_id(document_id, meta_dieu)
        ten = nfc(article.article_title.strip())
        if article_key in seen:
            warnings.append(
                f"Điều {meta_dieu} appears twice ({seen[article_key]!r} and {ten!r}); kept the first. "
                "Usually an OCR misread of the Dieu number."
            )
            continue
        seen[article_key] = ten

        chapter_heading = heading(chapter.chapter_number, chapter.chapter_title) if chapter else None
        section_heading = heading(section.section_number, section.section_title) if section else None
        context = " > ".join(p for p in [meta_de_muc, part, chapter_heading, section_heading] if p)
        body = nfc(article_body(article))
        header = build_header(context, meta_dieu, ten, variant=text_variant)
        units = amending_units(article)
        if units:
            # One part per khoan (more if it is long), headed by the change it makes.
            parts = [
                (text, khoan)
                for targets, khoan, unit_body in units
                for text, _ in split("\n".join([header, *(change_line(t, kg) for t in targets)]), nfc(unit_body))
            ]
        else:
            parts = split(header, body)
        mapc = kg.mapc(document_id, meta_dieu) if kg else None
        for index, (text, meta_khoan) in enumerate(parts, start=1):
            chunks.append(
                {
                    "chunk_id": make_chunk_id(document_id, meta_dieu, index if len(parts) > 1 else None),
                    "mapc": mapc,
                    "ten": ten,
                    "text": text,
                    "meta_chuong": heading_number(chapter.chapter_number) if chapter else None,
                    "meta_muc": heading_number(section.section_number) if section else None,
                    "meta_dieu": meta_dieu,
                    "meta_khoan": meta_khoan,
                    "content_hash": content_hash(body),
                    **common,
                }
            )

    # All appendices come out of the OCR tree as one block of lines.
    appendix = nfc("\n".join(line for line in doc.appendices if line.strip()))
    if appendix:
        parts = split(build_header(meta_de_muc, None, "Phụ lục"), appendix)
        for index, (text, _) in enumerate(parts, start=1):
            chunks.append(
                {
                    "chunk_id": f"{document_id}:pl1" + (f":p{index}" if len(parts) > 1 else ""),
                    "mapc": None,
                    "ten": "Phụ lục",
                    "text": text,
                    "meta_chuong": None,
                    "meta_muc": None,
                    "meta_dieu": None,
                    "meta_khoan": None,
                    "content_hash": content_hash(appendix),
                    **common,
                }
            )
    # Same key order as the Phap dien chunks, for readable diffs.
    order = [
        "chunk_id", "document_id", "mapc", "source", "ten", "text", "meta_de_muc", "meta_chuong", "meta_muc",
        "pd_chuong", "pd_muc", "meta_dieu", "meta_khoan", "effective_from_date", "effective_to_date",
        "version_date", "still_valid", "content_hash",
    ]
    return [{key: chunk[key] for key in order} for chunk in chunks], warnings


def load_document(path: Path) -> LegalDocument:
    """A document saved with `python -m labor_rag.ocr -f hierarchical` (or by this script)."""
    line = next(line for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return LegalDocument.model_validate_json(line)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="PDF or image to OCR")
    source.add_argument("--from-json", type=Path, help="saved OCR tree (<document_id>_hierarchical.jsonl)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--kg-dir", type=Path, default=LAO_DONG_DIR, help="Phap dien projection for mapc lookups")
    parser.add_argument("--abox-dir", type=Path, default=PDF_ABOX_DIR, help="where the document's ABox is written")
    parser.add_argument(
        "--max-tokens", type=int, default=MAX_TOKENS, help="split longer Dieu (0: never split, no tokenizer)"
    )
    parser.add_argument(
        "--text-variant",
        choices=["full", "minimal", "B", "A"],
        default="full",
        help="TH2/B: 'full' (đầy đủ ngữ cảnh, mặc định) | TH1/A: 'minimal' (chỉ Điều n. Tên)",
    )
    args = parser.parse_args()

    if args.from_json:
        doc = load_document(args.from_json)
    else:
        from labor_rag.ocr.export import export_hierarchical
        from labor_rag.ocr.pipeline import process_document

        doc = process_document(args.input).document
        # Keep the OCR tree so the chunks can be rebuilt without OCR'ing again.
        tree_path = export_hierarchical(doc, args.out_dir / f"{doc.document_id}_hierarchical.jsonl")
        print(f"OCR tree: {tree_path}")

    kg = KgIndex.load(args.kg_dir) if (args.kg_dir / "kg_nodes.jsonl").exists() else None
    if kg is None:
        print(f"WARNING: {args.kg_dir}/kg_nodes.jsonl not found; chunks get no mapc.", file=sys.stderr)
    count = TokenCounter() if args.max_tokens > 0 else None
    chunks, warnings = document_to_chunks(doc, kg, count, args.max_tokens, text_variant=args.text_variant)

    chunks_path = args.out_dir / f"{doc.document_id}_chunks.jsonl"
    footnotes_path = args.out_dir / f"{doc.document_id}_footnotes.jsonl"
    write_jsonl(chunks_path, chunks)
    write_jsonl(footnotes_path, doc.footnotes)

    from labor_rag.ingest.pdf_abox import document_abox

    builder, abox_stats = document_abox(doc, kg)
    abox_path = args.abox_dir / f"{doc.document_id}.ttl"
    if builder is None:
        print("WARNING: no document number, so no ABox: the graph will not know this document.", file=sys.stderr)
    else:
        builder.serialize(abox_path)

    meta = doc.metadata
    articles = {chunk["chunk_id"].split(":p")[0] for chunk in chunks if chunk["meta_dieu"]}
    summary = {
        "document_id": doc.document_id,
        "so_hieu": meta.so_hieu,
        "hop_nhat": meta.hop_nhat,
        "van_ban_sua_doi": meta.van_ban_sua_doi,
        "version_date": meta.version_date,
        "articles": len(articles),
        "chunks": len(chunks),
        "split_articles": sum(1 for chunk in chunks if chunk["chunk_id"].endswith(":p1") and chunk["meta_dieu"]),
        "articles_without_mapc": sorted(
            {chunk["meta_dieu"] for chunk in chunks if chunk["meta_dieu"] and not chunk["mapc"]},
            key=lambda d: (int(re.match(r"\d+", d).group()) if re.match(r"\d+", d) else 0, d),
        ),
        "footnotes": len(doc.footnotes),
        "abox": abox_stats,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    print(f"Wrote {chunks_path} and {footnotes_path}" + (f", ABox {abox_path}" if builder else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

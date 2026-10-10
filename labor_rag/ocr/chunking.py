"""Two-tier chunking of a parsed legal document.

Tier 1 (structure-aware): flatten the Phần > ... > Điểm tree into one
FlatRecord per smallest unit (Điểm, else Khoản, else Điều), each carrying
its full hierarchy path. Lead-in text of a Điều before its first Khoản, and
of a Khoản before its first Điểm, becomes its own record.

Tier 2 (size): records longer than CHUNK_MAX_CHARS are split, either
semantically (cut where the cosine similarity of consecutive sentences
drops, needs OCR_SEMANTIC_CHUNKING=1) or recursively at Điều / Khoản / Điểm
/ paragraph / line / sentence boundaries. Sub-records keep all hierarchy
fields and get chunk_index / total_chunks.
"""
from __future__ import annotations

import logging
import re

from labor_rag.ocr import settings
from labor_rag.ocr.schemas import Article, Chapter, FlatRecord, LegalDocument

logger = logging.getLogger(__name__)


# ============================================================
# Tier 1: flatten
# ============================================================

def _hierarchy(*labels: str | None) -> str:
    return " > ".join(label for label in labels if label)


def flatten_document(doc: LegalDocument) -> list[FlatRecord]:
    records: list[FlatRecord] = []
    base = {"document_id": doc.document_id, "document_title": doc.title}

    def add_article(article: Article, context: dict) -> None:
        info = {
            **base, **context,
            "article_id": article.article_id,
            "article_number": article.article_number,
            "article_title": article.article_title,
        }
        path = [context.get("part_number"), context.get("chapter_number"),
                context.get("section_number"), article.article_number]

        if article.full_text:
            records.append(FlatRecord(**info, level="article", hierarchy=_hierarchy(*path), text=article.full_text))
        for clause in article.clauses:
            clause_info = {**info, "clause_id": clause.clause_id, "clause_number": clause.clause_number}
            clause_path = [*path, clause.clause_number]
            if clause.text:
                records.append(FlatRecord(**clause_info, level="clause", hierarchy=_hierarchy(*clause_path), text=clause.text))
            for point in clause.points:
                records.append(FlatRecord(
                    **clause_info,
                    point_id=point.point_id,
                    point_label=point.point_label,
                    level="point",
                    hierarchy=_hierarchy(*clause_path, f"Điểm {point.point_label}"),
                    text=point.text,
                ))

    def add_chapter(chapter: Chapter, context: dict) -> None:
        chapter_ctx = {
            **context,
            "chapter_id": chapter.chapter_id,
            "chapter_number": chapter.chapter_number,
            "chapter_title": chapter.chapter_title,
        }
        for article in chapter.articles:
            add_article(article, chapter_ctx)
        for section in chapter.sections:
            section_ctx = {
                **chapter_ctx,
                "section_id": section.section_id,
                "section_number": section.section_number,
                "section_title": section.section_title,
            }
            for article in section.articles:
                add_article(article, section_ctx)

    if doc.preamble.strip():
        records.append(FlatRecord(**base, level="preamble", hierarchy="Lời nói đầu", text=doc.preamble))
    for article in doc.articles:
        add_article(article, {})
    for chapter in doc.chapters:
        add_chapter(chapter, {})
    for part in doc.parts:
        part_ctx = {"part_id": part.part_id, "part_number": part.part_number, "part_title": part.part_title}
        for chapter in part.chapters:
            add_chapter(chapter, part_ctx)
    if doc.appendices:
        records.append(FlatRecord(**base, level="appendix", hierarchy="Phụ lục", text="\n".join(doc.appendices)))

    return [r for r in records if r.text.strip()]


# ============================================================
# Tier 2: split over-long records
# ============================================================

def chunk_long_records(records: list[FlatRecord], max_chars: int | None = None) -> list[FlatRecord]:
    max_chars = max_chars or settings.CHUNK_MAX_CHARS
    out: list[FlatRecord] = []
    for record in records:
        chunks = chunk_long_text(record.text, max_chars)
        if len(chunks) <= 1:
            out.append(record)
            continue
        for idx, chunk in enumerate(chunks):
            out.append(record.model_copy(update={"text": chunk, "chunk_index": idx, "total_chunks": len(chunks)}))
    return out


def chunk_long_text(text: str, max_chars: int | None = None, use_semantic: bool | None = None) -> list[str]:
    max_chars = max_chars or settings.CHUNK_MAX_CHARS
    if use_semantic is None:
        use_semantic = settings.SEMANTIC_CHUNKING
    if len(text) <= max_chars:
        return [text]
    if use_semantic:
        return _semantic_chunk(text, max_chars)
    return _recursive_chunk(text, max_chars)


# --- recursive splitting -------------------------------------

# Highest-priority boundary first.
_SEPARATORS = [
    re.compile(r"\n(?=Điều\s+\d+)"),
    re.compile(r"\n(?=\d+\.\s+)"),
    re.compile(r"\n(?=[a-zđ]\)\s+)"),
    re.compile(r"\n\n"),
    re.compile(r"\n"),
    re.compile(r"(?<=[.;])\s+"),
]


def _recursive_chunk(text: str, max_chars: int) -> list[str]:
    return [c for c in _recursive_split(text, _SEPARATORS, max_chars) if c.strip()]


def _recursive_split(text: str, separators: list[re.Pattern], max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    if not separators:
        # No boundary left: hard cut with overlap.
        overlap = settings.CHUNK_OVERLAP_CHARS
        chunks, start = [], 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunks.append(text[start:end])
            start = end - overlap if end < len(text) else end
        return chunks

    splits = [s.strip() for s in separators[0].split(text) if s.strip()]
    if len(splits) <= 1:
        return _recursive_split(text, separators[1:], max_chars)

    chunks: list[str] = []
    current = ""
    for piece in splits:
        if not current:
            current = piece
        elif len(current) + len(piece) + 1 <= max_chars:
            current += "\n" + piece
        else:
            chunks.extend(_recursive_split(current, separators[1:], max_chars))
            current = piece
    if current:
        chunks.extend(_recursive_split(current, separators[1:], max_chars))
    return chunks


# --- semantic splitting --------------------------------------

_embedding_model = None
_SENTENCE_SPLIT = re.compile(r"(?<=[.;!?])\s+(?=[A-ZÀ-Ỹa-zà-ỹ\d\(])")


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading semantic-chunking model %s", settings.SEMANTIC_MODEL)
        _embedding_model = SentenceTransformer(settings.SEMANTIC_MODEL)
    return _embedding_model


def _split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for sent in _SENTENCE_SPLIT.split(text):
        sent = sent.strip()
        if not sent:
            continue
        if sentences and len(sent) < 15:
            sentences[-1] += " " + sent  # too short to stand alone
        else:
            sentences.append(sent)
    return sentences


def _semantic_chunk(text: str, max_chars: int) -> list[str]:
    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        return _recursive_chunk(text, max_chars)

    embeddings = _get_embedding_model().encode(sentences, normalize_embeddings=True)
    # Cut after sentence i when it is dissimilar to sentence i + 1.
    breaks = [
        i for i in range(len(sentences) - 1)
        if float(embeddings[i] @ embeddings[i + 1]) < settings.SEMANTIC_SIMILARITY_THRESHOLD
    ]
    groups, start = [], 0
    for bp in breaks + [len(sentences) - 1]:
        groups.append(" ".join(sentences[start:bp + 1]))
        start = bp + 1

    # Greedily merge small neighbouring groups, then re-split oversized ones.
    merged: list[str] = []
    buffer = ""
    for group in groups:
        if buffer and len(buffer) + len(group) + 1 <= max_chars:
            buffer += " " + group
        else:
            if buffer:
                merged.append(buffer)
            buffer = group
    if buffer:
        if merged and len(buffer) < settings.SEMANTIC_MIN_CHUNK_CHARS:
            merged[-1] += " " + buffer
        else:
            merged.append(buffer)

    result: list[str] = []
    for chunk in merged:
        result.extend(_recursive_chunk(chunk, max_chars) if len(chunk) > max_chars else [chunk])
    return result

"""Pydantic models for a parsed Vietnamese legal document.

Hierarchy: Phan (Part) > Chuong (Chapter) > Muc (Section) > Dieu (Article)
> Khoan (Clause) > Diem (Point).
"""
from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, Field


class Point(BaseModel):
    point_id: str = Field(..., description="vd: dieu_1_khoan_1_diem_a")
    point_label: str = Field(..., description="a, b, c, đ, ...")
    text: str


class Clause(BaseModel):
    clause_id: str = Field(..., description="vd: dieu_1_khoan_1")
    clause_number: str = Field(..., description="Khoản 1, Khoản 2, ...")
    text: str = Field(default="", description="Nội dung trước các Điểm")
    points: list[Point] = Field(default_factory=list)


class Article(BaseModel):
    article_id: str = Field(..., description="vd: dieu_5")
    article_number: str = Field(..., description="Điều 1, Điều 2, ...")
    article_title: str = ""
    full_text: str = Field(default="", description="Nội dung của Điều nằm ngoài các Khoản")
    clauses: list[Clause] = Field(default_factory=list)


class Section(BaseModel):
    section_id: str = Field(..., description="vd: chuong_i_muc_1")
    section_number: str = Field(..., description="Mục 1, Mục 2, ...")
    section_title: str = ""
    articles: list[Article] = Field(default_factory=list)


class Chapter(BaseModel):
    chapter_id: str = Field(..., description="vd: chuong_i")
    chapter_number: str = Field(..., description="Chương I, Chương II, ...")
    chapter_title: str = ""
    sections: list[Section] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list, description="Điều không qua Mục")


class Part(BaseModel):
    part_id: str = Field(..., description="vd: phan_nhất")
    part_number: str = Field(..., description="Phần thứ nhất, Phần I, ...")
    part_title: str = ""
    chapters: list[Chapter] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    so_hieu: str = Field(default="", description="vd: 45/2019/QH14")
    loai_van_ban: str = Field(default="", description="Luật, Nghị định, Thông tư, ...")
    ngay_ban_hanh: str = Field(default="", description="YYYY-MM-DD")
    co_quan_ban_hanh: str = ""
    source_file: str = ""
    total_pages: int = 0
    extraction_method: str = Field(default="", description="text / ocr / mixed")
    scanned_pages: list[int] = Field(default_factory=list, description="Trang đã OCR (0-based)")
    hop_nhat: bool = Field(default=False, description="Văn bản hợp nhất (VBHN)")
    so_hieu_vbhn: str = Field(default="", description="Số của chính VBHN, vd: 01/VBHN-VPQH")
    van_ban_sua_doi: list[dict] = Field(
        default_factory=list, description="Văn bản sửa đổi được hợp nhất: [{so_hieu, ngay_hieu_luc}]"
    )
    ngay_hieu_luc: str = Field(default="", description="Ngày văn bản gốc có hiệu lực, YYYY-MM-DD")
    version_date: str = Field(
        default="", description="Ngày hiệu lực mới nhất của nội dung (văn bản gốc hoặc lần sửa đổi được hợp nhất)"
    )


class LegalDocument(BaseModel):
    document_id: str
    title: str = ""
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    preamble: str = Field(default="", description="Quốc hiệu, căn cứ, ... trước Điều đầu tiên")
    parts: list[Part] = Field(default_factory=list)
    chapters: list[Chapter] = Field(default_factory=list, description="Chương không thuộc Phần")
    articles: list[Article] = Field(default_factory=list, description="Điều không thuộc Chương")
    footnotes: list[dict] = Field(
        default_factory=list, description="Chú thích cuối trang đã tách khỏi nội dung: [{page, number, text}]"
    )
    appendices: list[str] = Field(default_factory=list)
    full_text: str = Field(default="", description="Toàn văn đã làm sạch")

    def iter_articles(self):
        yield from self.articles
        chapters = list(self.chapters) + [c for p in self.parts for c in p.chapters]
        for chapter in chapters:
            yield from chapter.articles
            for section in chapter.sections:
                yield from section.articles


class FlatRecord(BaseModel):
    """Smallest text unit with its full hierarchy path (one JSONL line)."""
    document_id: str
    document_title: str = ""
    part_id: Optional[str] = None
    part_number: Optional[str] = None
    part_title: Optional[str] = None
    chapter_id: Optional[str] = None
    chapter_number: Optional[str] = None
    chapter_title: Optional[str] = None
    section_id: Optional[str] = None
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    article_id: Optional[str] = None
    article_number: Optional[str] = None
    article_title: Optional[str] = None
    clause_id: Optional[str] = None
    clause_number: Optional[str] = None
    point_id: Optional[str] = None
    point_label: Optional[str] = None
    level: str = Field(..., description="preamble/article/clause/point/appendix")
    hierarchy: str = Field(default="", description="vd: Chương I > Điều 1 > Khoản 1")
    text: str
    # Set when an over-long record was split by the chunker.
    chunk_index: Optional[int] = None
    total_chunks: Optional[int] = None

    def to_json_line(self) -> str:
        return json.dumps(self.model_dump(exclude_none=True), ensure_ascii=False)

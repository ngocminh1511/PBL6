"""Unit tests for labor_rag.ocr: normalisation, cleaning, structure parsing,
chunking, export and the OCR quality metrics. No OCR model is loaded.

Run from the repository root:
  python tests/test_ocr_pipeline.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.ocr.chunking import chunk_long_records, chunk_long_text, flatten_document
from labor_rag.ocr.cleaner import (
    clean_and_merge,
    detect_duplicate_pages,
    detect_headers_footers,
    fix_line_breaks,
    normalize_whitespace,
    remove_page_numbers,
    split_footnotes,
)
from labor_rag.ocr.engine import _cut_wide, _find_lines, _line_pieces
from labor_rag.ocr.export import export_document
from labor_rag.ocr.normalize import full_normalize, replace_special_chars
from labor_rag.ocr.quality import cer, quality_report, wer
from labor_rag.ocr.schemas import FlatRecord
from labor_rag.ocr.structure import StructureLevel, extract_metadata, parse_line, parse_structure

SAMPLE_LAW = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
QUỐC HỘI
Số: 45/2019/QH14
BỘ LUẬT LAO ĐỘNG
Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;
Chương I. NHỮNG QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Bộ luật này quy định như sau:
1. Bộ luật này quy định tiêu chuẩn lao động.
2. Người lao động có các quyền sau đây:
a) Làm việc, tự do lựa chọn việc làm;
b) Hưởng lương phù hợp với trình độ;
Điều 2. Đối tượng áp dụng
1. Người lao động Việt Nam.
2. Người sử dụng lao động.
Chương II. VIỆC LÀM
Mục 1. Quy định chung
Điều 3. Quyền làm việc
1. Mọi người đều có quyền làm việc.
"""


# --- normalize ------------------------------------------------

def test_normalize():
    assert full_normalize("Việt Nam") == "Việt Nam"
    assert replace_special_chars("“A” – … ​") == '"A" - ... '
    assert full_normalize("ðiều 5, Ðiều 6") == "điều 5, Điều 6"


# --- cleaner --------------------------------------------------

def test_headers_footers_and_page_numbers():
    pages = [f"BỘ LUẬT LAO ĐỘNG\nNội dung trang {i}\nTrang {i}" for i in range(1, 5)]
    headers, _ = detect_headers_footers(pages)
    assert "BỘ LUẬT LAO ĐỘNG" in headers
    assert remove_page_numbers("Nội dung\n42\n- 3 -\nTrang 5\nTiếp") == "Nội dung\nTiếp"


def test_duplicate_pages():
    page = "Điều 1. Phạm vi điều chỉnh. " * 20
    assert detect_duplicate_pages([page, "Điều 2. Khác hẳn.", page]) == {2}


def test_line_breaks_and_whitespace():
    assert "ngắt giữa" in fix_line_breaks("Đây là câu bị ngắt\ngiữa chừng.")
    assert fix_line_breaks("Nội dung trước\nĐiều 1. Phạm vi") == "Nội dung trước\nĐiều 1. Phạm vi"
    assert normalize_whitespace("  Quá   nhiều \t space  ") == "Quá nhiều space"
    merged = clean_and_merge(["Điều 1. A\nnội dung bị\nngắt dòng.", "Điều 2. B"])
    assert "nội dung bị ngắt dòng." in merged


# --- structure ------------------------------------------------

def test_parse_line_levels():
    cases = {
        "PHẦN THỨ NHẤT": StructureLevel.PART,
        "Phần thứ hai": StructureLevel.PART,
        "Chương I. NHỮNG QUY ĐỊNH CHUNG": StructureLevel.CHAPTER,
        "CHƯƠNG XIV": StructureLevel.CHAPTER,
        "Mục 1. Quy định chung": StructureLevel.SECTION,
        "Điều 220. Quy định cuối": StructureLevel.ARTICLE,
        "25. Nội dung khoản 25": StructureLevel.CLAUSE,
        "đ) Điểm đ rất hay bị bỏ qua": StructureLevel.POINT,
        "2019. Không phải khoản": StructureLevel.TEXT,
        "Điêu 25. Thời gian thử việc": StructureLevel.ARTICLE,  # OCR tone-mark error
        "4, Người có liên quan": StructureLevel.CLAUSE,
        "4, 5 và 6 tháng": StructureLevel.TEXT,
        "Đây là nội dung bình thường": StructureLevel.TEXT,
    }
    for line, level in cases.items():
        assert parse_line(line).level == level, line
    assert parse_line("Điều 1. Phạm vi điều chỉnh").title == "Phạm vi điều chỉnh"


def test_parse_structure_tree():
    doc = parse_structure(SAMPLE_LAW, document_id="test_doc")
    assert doc.document_id == "test_doc"
    assert doc.title == "BỘ LUẬT LAO ĐỘNG"
    assert [c.chapter_number for c in doc.chapters] == ["Chương I", "Chương II"]

    dieu1 = doc.chapters[0].articles[0]
    assert dieu1.article_number == "Điều 1"
    assert dieu1.full_text == "Bộ luật này quy định như sau:"
    khoan2 = dieu1.clauses[1]
    assert khoan2.text == "Người lao động có các quyền sau đây:"
    assert [p.point_label for p in khoan2.points] == ["a", "b"]

    muc1 = doc.chapters[1].sections[0]
    assert muc1.section_id == "chuong_ii_muc_1"
    assert muc1.articles[0].article_number == "Điều 3"


def test_document_id_falls_back_to_unknown_only_without_id():
    assert parse_structure("Điều 1. A\n1. B.", document_id="nd_145").document_id == "nd_145"
    assert parse_structure("Điều 1. A\n1. B.").document_id == "unknown"


def test_section_without_chapter_keeps_articles():
    doc = parse_structure("Mục 1. Chung\nĐiều 1. A\n1. Nội dung.", document_id="x")
    assert [a.article_number for a in doc.articles] == ["Điều 1"]


def test_metadata():
    meta = extract_metadata(SAMPLE_LAW + "Hà Nội, ngày 20 tháng 11 năm 2019", title="BỘ LUẬT LAO ĐỘNG")
    assert meta.so_hieu == "45/2019/QH14"
    assert meta.loai_van_ban == "Bộ luật"
    assert meta.co_quan_ban_hanh == "QUỐC HỘI"
    assert meta.ngay_ban_hanh == "2019-11-20"
    nd = extract_metadata("CHÍNH PHỦ\nSố: 145/2020/NĐ-CP\nNGHỊ ĐỊNH\nCăn cứ Luật Tổ chức Chính phủ;", title="NGHỊ ĐỊNH")
    assert nd.loai_van_ban == "Nghị định"
    assert nd.so_hieu == "145/2020/NĐ-CP"


# --- chunking -------------------------------------------------

def test_flatten_keeps_lead_in_text():
    records = flatten_document(parse_structure(SAMPLE_LAW, document_id="t"))
    by_path = {r.hierarchy: r for r in records}
    assert by_path["Chương I > Điều 1"].level == "article"
    assert by_path["Chương I > Điều 1 > Khoản 2"].text == "Người lao động có các quyền sau đây:"
    point_a = by_path["Chương I > Điều 1 > Khoản 2 > Điểm a"]
    assert point_a.level == "point" and point_a.chapter_title == "NHỮNG QUY ĐỊNH CHUNG"
    assert by_path["Chương II > Mục 1 > Điều 3 > Khoản 1"].section_number == "Mục 1"
    assert records[0].level == "preamble"


def test_chunk_long_records():
    long_text = "\n".join(f"{i}. " + "nội dung khoản rất dài " * 20 for i in range(1, 11))
    chunks = chunk_long_text(long_text, max_chars=1000, use_semantic=False)
    assert len(chunks) > 1 and all(len(c) <= 1000 for c in chunks)
    record = FlatRecord(document_id="t", level="article", article_number="Điều 9", text=long_text)
    split = chunk_long_records([record], max_chars=1000)
    assert [r.chunk_index for r in split] == list(range(len(split)))
    assert all(r.total_chunks == len(split) and r.article_number == "Điều 9" for r in split)


# --- export ---------------------------------------------------

def test_export_formats():
    doc = parse_structure(SAMPLE_LAW, document_id="t")
    records = flatten_document(doc)
    with tempfile.TemporaryDirectory() as tmp:
        out = export_document(doc, records, Path(tmp), ("flat", "hierarchical", "training"))
        flat = [json.loads(line) for line in out["flat"].read_text(encoding="utf-8").splitlines()]
        assert len(flat) == len(records) and flat[1]["document_id"] == "t"
        tree = json.loads(out["hierarchical"].read_text(encoding="utf-8"))
        assert tree["chapters"][0]["articles"][0]["article_number"] == "Điều 1"
        assert "Điều" in out["training"].read_text(encoding="utf-8")  # ensure_ascii=False


# --- engine segmentation (no model needed) --------------------

def test_line_segmentation():
    ink = np.zeros((200, 1000), dtype=bool)
    ink[20:50, 100:300] = True  # left column of line 1
    ink[20:50, 700:900] = True  # right column of line 1, far away
    ink[14:17, 150:200] = True  # diacritics just above line 1
    ink[100:130, 100:900] = True  # line 2
    lines = _find_lines(ink)
    assert len(lines) == 2 and lines[0][0] <= 14
    y0, y1 = lines[0]
    assert len(_line_pieces(ink[y0:y1], page_width=1000, max_width=10_000)) == 2


def test_tall_bands_are_split_into_lines():
    ink = np.zeros((1200, 1000), dtype=bool)
    for top in range(50, 1000, 200):  # five separate single lines, 50-60 px tall
        ink[top:top + 50 + top % 3 * 5, 100:900] = True
    # Two lines whose diacritics touch: one 116 px band with a thin bridge.
    ink[1040:1096, 100:900] = True
    ink[1096:1100, 400:420] = True
    ink[1100:1156, 100:900] = True
    lines = _find_lines(ink)
    assert len(lines) == 7
    y0, y1 = lines[-2]
    assert 1090 <= y1 <= 1106 and y1 - y0 < 70


def test_cut_wide_prefers_word_gaps():
    has_ink = np.ones(1000, dtype=bool)
    has_ink[380:400] = False  # a word gap in the right half of the first window
    has_ink[450:452] = False  # a narrow letter gap
    pieces = _cut_wide(0, 1000, has_ink, max_width=500)
    assert pieces[0] == (0, 390)
    assert all(b - a <= 500 for a, b in pieces) and pieces[-1][1] == 1000


# --- quality --------------------------------------------------

GOOD_OCR = """BỘ LUẬT LAO ĐỘNG
Chương I. NHỮNG QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
1. Bộ luật này quy định tiêu chuẩn lao động, quyền, nghĩa vụ của người lao động.
2. Người sử dụng lao động."""
BAD_OCR = """LU¤T LAO ÐÃ–NG №※◊
Chuong I NHÜNG QUY §¶µ ÐINH CHUNG ¥£€¢
cua ♫♬♩ ngxtqz lao dong bcdfg va ×÷± nguoi su dung
b) Ã¢Ã©Ã¨ Quyen loi ℃℉ cua nguoi ∞≈≠"""


def test_quality_report():
    good, bad = quality_report(GOOD_OCR), quality_report(BAD_OCR)
    assert good["heuristic_score"] >= 90 and good["garbage_sequences"] == 0
    assert bad["heuristic_score"] < 60 and bad["mojibake"] > 0
    assert cer("lao động", "lao động") == 0.0
    assert abs(cer("abcd", "abed") - 0.25) < 1e-9
    assert abs(wer("người lao động", "người lao dong") - 1 / 3) < 1e-9
    assert quality_report("abc", ground_truth="abc")["cer"] == 0.0


def test_document_id_from_so_hieu():
    from labor_rag.ocr.pipeline import _document_id

    head = "QUỐC HỘI\nLuật số: 45/2019/QH14\nBỘ LUẬT LAO ĐỘNG"
    metadata = extract_metadata(head, "BỘ LUẬT LAO ĐỘNG")
    assert metadata.so_hieu == "45/2019/QH14"
    assert _document_id(metadata.so_hieu, head) == "45-2019-qh14"
    assert extract_metadata("Số : 40/2021/QĐ-TTg\n").so_hieu == "40/2021/QĐ-TTg"
    no_number = _document_id("", "nội dung không có số hiệu")
    assert no_number.startswith("doc-") and no_number == _document_id("", "nội dung không có số hiệu")


# --- inserted Dieu/Khoan, Dieu headings, footnotes, van ban hop nhat ---

def test_inserted_article_and_clause_numbers():
    assert parse_line("Điều 35a. Trợ cấp bổ sung").number == "35a"
    assert parse_line("Điều 35đ. Khác").number == "35đ"
    assert parse_line("Điều 35 của Bộ luật này").number == "35"
    clause = parse_line("1a. Người học nghề.")
    assert clause.level == StructureLevel.CLAUSE and clause.number == "1a"
    doc = parse_structure("Điều 35. A\n1. B.\nĐiều 35a. C\n1a. D.")
    assert [a.article_number for a in doc.iter_articles()] == ["Điều 35", "Điều 35a"]


def test_article_heading_not_joined_to_first_sentence():
    text = fix_line_breaks(
        "Điều 1. Phạm vi điều chỉnh\nBộ luật Lao động quy định tiêu chuẩn lao động.\n"
        "Điều 5. Quyền và nghĩa vụ của người\nlao động"
    )
    assert text.split("\n") == [
        "Điều 1. Phạm vi điều chỉnh",
        "Bộ luật Lao động quy định tiêu chuẩn lao động.",
        "Điều 5. Quyền và nghĩa vụ của người lao động",  # a title wrapped onto two lines is still joined
    ]


VBHN_PAGE = """BỘ LUẬT
LAO ĐỘNG
Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019 của Quốc hội, có hiệu lực kể từ ngày 01 tháng 01 năm 2021, được sửa đổi, bổ sung bởi:
1. Luật Công nghiệp công nghệ số số 71/2025/QH15 ngày 14 tháng 6 năm 2025 của Quốc hội, có hiệu lực kể từ ngày 01 tháng 01 năm 2026;
2. Luật Dân số số 113/2025/QH15 ngày 10 tháng 12 năm 2025 của Quốc hội, có hiệu lực kể từ ngày 01 tháng 7 năm 2026;
3. Luật Giáo dục nghề nghiệp số 124/2025/QH15 ngày 10 tháng 12 năm 2025 của Quốc hội, có hiệu lực kể từ ngày 01 tháng 01 năm 2026.
Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;
Quốc hội ban hành Bộ luật Lao động1.
Chương I
NHỮNG QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Bộ luật Lao động quy định tiêu chuẩn lao động.
1 Luật Công nghiệp công nghệ số số 71/2025/QH15 có căn cứ ban hành như sau:
"Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;
Quốc hội ban hành Luật Công nghiệp công nghệ số.".
2 Khoản này được sửa đổi, bổ sung theo quy định tại khoản 2 Điều 63 của Luật Giáo dục nghề nghiệp số 124/2025/QH15, có hiệu lực kể từ ngày 01 tháng 01 năm 2026."""


def test_split_footnotes():
    body, notes = split_footnotes(VBHN_PAGE)
    assert body.endswith("Bộ luật Lao động quy định tiêu chuẩn lao động.")
    assert [note["number"] for note in notes] == [1, 2]
    assert notes[0]["text"].startswith("Luật Công nghiệp công nghệ số số 71/2025/QH15 có căn cứ ban hành")
    assert "Quốc hội ban hành Luật Công nghiệp công nghệ số." in notes[0]["text"]
    assert notes[1]["text"].startswith("Khoản này được sửa đổi, bổ sung theo quy định tại khoản 2 Điều 63")
    # A page whose last lines are numbered khoan has no footnotes.
    page = "Điều 2. Đối tượng áp dụng\n1. Người lao động.\n2. Người sử dụng lao động."
    assert split_footnotes(page) == (page, [])
    # Numbered lines without amendment wording stay in the body.
    page = "Bảng\n1 Hà Nội 200\n2 Huế 100"
    assert split_footnotes(page) == (page, [])
    # Body text after the numbered lines: not a footnote block.
    page = VBHN_PAGE + "\nĐiều 5. Quyền của người lao động\n1. Làm việc."
    assert split_footnotes(page) == (page, [])


def test_footnotes_collected_with_page_numbers():
    footnotes: list[dict] = []
    text = clean_and_merge(["Trang một.", VBHN_PAGE], footnotes, [4, 5])
    assert "Khoản này được sửa đổi" not in text
    assert [(note["page"], note["number"]) for note in footnotes] == [(5, 1), (5, 2)]


def test_van_ban_hop_nhat_metadata():
    metadata = extract_metadata(VBHN_PAGE, "BỘ LUẬT LAO ĐỘNG")
    assert metadata.so_hieu == "45/2019/QH14"
    assert metadata.hop_nhat
    assert metadata.ngay_hieu_luc == "2021-01-01"
    assert metadata.van_ban_sua_doi == [
        {"so_hieu": "71/2025/QH15", "ngay_hieu_luc": "2026-01-01"},
        {"so_hieu": "113/2025/QH15", "ngay_hieu_luc": "2026-07-01"},
        {"so_hieu": "124/2025/QH15", "ngay_hieu_luc": "2026-01-01"},
    ]
    assert metadata.version_date == "2026-07-01"
    numbered = extract_metadata("Số: 05/VBHN-VPQH\nLUẬT VIỆC LÀM\n" + VBHN_PAGE)
    assert numbered.so_hieu_vbhn == "05/VBHN-VPQH" and numbered.so_hieu == "45/2019/QH14"


def test_effective_date_of_original_document():
    metadata = extract_metadata(SAMPLE_LAW + "Điều 220. Hiệu lực thi hành\nBộ luật này có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021.")
    assert not metadata.hop_nhat
    assert metadata.ngay_hieu_luc == "2021-01-01" and metadata.version_date == "2021-01-01"
    assert extract_metadata("Nghị định này có hiệu lực từ ngày 1/2/2021.").ngay_hieu_luc == "2021-02-01"


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

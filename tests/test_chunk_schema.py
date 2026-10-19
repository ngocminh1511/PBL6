"""Unit tests for labor_rag.ingest.chunk_schema (chunk schema v5): ids, text,
and splitting long Dieu. Tokens are counted as words, so
no tokenizer is downloaded.

Run from the repository root:
  python tests/test_chunk_schema.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.ingest.chunk_schema import (
    article_id,
    build_header,
    citation,
    content_hash,
    heading_number,
    is_so_hieu,
    join_parts,
    make_chunk_id,
    make_document_id,
    part_number,
    point_id,
    split_article,
)


def words(text: str) -> int:
    return len(text.split()) + 2  # + [CLS]/[SEP]


HEADER = "Lao động > Bộ luật số 45/2019/QH14 > Chương I. CHUNG\nĐiều 5. Quyền của người lao động"
LEAD = "Người lao động có các quyền sau đây:"


def clause(number: int, n_words: int) -> str:
    return f"{number}. " + " ".join(f"w{number}_{i}" for i in range(n_words))


def test_document_id_from_so_hieu():
    assert make_document_id("45/2019/QH14") == "45-2019-qh14"
    assert make_document_id("145/2020/NĐ-CP") == "145-2020-nd-cp"
    assert make_document_id("145/2020/NÐ-CP") == make_document_id("145/2020/NĐ-CP")  # OCR eth
    assert make_document_id("01/2020/TT-BLĐTBXH") == "01-2020-tt-bldtbxh"


def test_is_so_hieu():
    assert is_so_hieu("45/2019/QH14")
    assert is_so_hieu("40/2021/QĐ-TTg")
    assert is_so_hieu("145/2020/NÐ-CP")
    assert not is_so_hieu("Bộ luật Lao động")
    assert not is_so_hieu("")


def test_chunk_id():
    assert make_chunk_id("45-2019-qh14", "1") == "45-2019-qh14:d1"
    assert make_chunk_id("45-2019-qh14", "4a") == "45-2019-qh14:d4a"
    assert make_chunk_id("45-2019-qh14", "35đ") == "45-2019-qh14:d35dd"
    assert make_chunk_id("45-2019-qh14", "35d") != make_chunk_id("45-2019-qh14", "35đ")
    assert make_chunk_id("45-2019-qh14", "35", 2) == "45-2019-qh14:d35:p2"
    assert article_id("45-2019-qh14:d35:p2") == "45-2019-qh14:d35"
    assert article_id("45-2019-qh14:d35") == "45-2019-qh14:d35"
    assert part_number("45-2019-qh14:d35:p12") == 12 and part_number("45-2019-qh14:d35") == 0
    assert point_id("45-2019-qh14:d1") == point_id("45-2019-qh14:d1") != point_id("45-2019-qh14:d2")


def test_content_hash_ignores_whitespace_and_normalization():
    composed = "Người lao động"
    decomposed = "Người lao động"
    assert content_hash(composed + "  \n") == content_hash(decomposed)
    assert content_hash("a b") != content_hash("a c")


def test_heading_number_and_citation():
    assert heading_number("Chương III. HỢP ĐỒNG LAO ĐỘNG") == "III"
    assert heading_number("Mục 4. HỢP ĐỒNG LAO ĐỘNG VÔ HIỆU") == "4"
    assert heading_number(None) is None
    chunk = {"meta_dieu": "35", "meta_khoan": "4-5", "meta_de_muc": "Nghị định số 145/2020/NĐ-CP"}
    assert citation(chunk) == "Điều 35 khoản 4-5 Nghị định số 145/2020/NĐ-CP"
    assert citation({**chunk, "meta_khoan": None}) == "Điều 35 Nghị định số 145/2020/NĐ-CP"


def test_short_article_is_not_split():
    body = "\n".join([LEAD, clause(1, 10), clause(2, 10)])
    parts = split_article(HEADER, body, words, max_tokens=200)
    assert parts == [(HEADER + "\n" + body, None)]


def test_split_by_khoan():
    body = "\n".join([LEAD, *(clause(n, 40) for n in range(1, 7))])
    parts = split_article(HEADER, body, words, max_tokens=150)
    assert len(parts) > 1
    seen = []
    for text, meta_khoan in parts:
        assert words(text) <= 150, words(text)
        assert text.startswith(HEADER + "\n" + LEAD)  # header and lead repeated in every part
        seen += [line.split(".")[0] for line in text.split("\n") if line[:1].isdigit()]
        assert meta_khoan
    assert seen == [str(n) for n in range(1, 7)]  # every khoan once, in order, never cut
    assert parts[0][1].startswith("1-") and parts[-1][1].endswith("6")


def test_balanced_parts():
    # 5 khoan of 40 words in a 150-token budget: 2 parts of 3+2 (or 2+3) khoan, not 3+1+1.
    body = "\n".join([LEAD, *(clause(n, 40) for n in range(1, 6))])
    parts = split_article(HEADER, body, words, max_tokens=150)
    sizes = [words(text) for text, _ in parts]
    assert max(sizes) - min(sizes) <= 45, sizes


def test_long_khoan_split_by_diem_repeats_khoan_lead():
    points = [f"{letter}) " + " ".join(f"p{letter}{i}" for i in range(30)) for letter in "abcde"]
    long_clause = "\n".join(["2. Các trường hợp sau đây:", *points])
    body = "\n".join([LEAD, clause(1, 10), long_clause, clause(3, 10)])
    parts = split_article(HEADER, body, words, max_tokens=120)
    with_points = [text for text, _ in parts if "a)" in text or "e)" in text]
    assert with_points and all("2. Các trường hợp sau đây:" in text for text in with_points)
    for text, _ in parts:
        assert words(text) <= 120, words(text)
    joined = " ".join(text for text, _ in parts)
    for letter in "abcde":
        assert f"p{letter}29" in joined


def test_text_without_khoan_split_by_sentence():
    sentences = [" ".join(f"s{n}_{i}" for i in range(20)) + "." for n in range(12)]
    body = " ".join(sentences)
    parts = split_article(HEADER, body, words, max_tokens=100)
    assert len(parts) > 1
    for text, meta_khoan in parts:
        assert words(text) <= 100 and meta_khoan is None
    joined = " ".join(text for text, _ in parts)
    assert all(f"s{n}_19." in joined for n in range(12))


def test_join_parts_rebuilds_article():
    body = "\n".join([LEAD, *(clause(n, 40) for n in range(1, 7))])
    parts = split_article(HEADER, body, words, max_tokens=150)
    assert join_parts([text for text, _ in parts]) == HEADER + "\n" + body


def test_build_header_variants():
    context = "Lao động > Nghị định 145/2020 > Chương III. HỢP ĐỒNG"
    # TH2 / B (full context): default
    header_full = build_header(context, "10", "Hợp đồng vô hiệu", variant="full")
    assert header_full == f"{context}\nĐiều 10. Hợp đồng vô hiệu"
    assert build_header(context, "10", "Hợp đồng vô hiệu") == header_full

    # TH1 / A (minimal: only Điều n. Tên)
    header_minimal = build_header(context, "10", "Hợp đồng vô hiệu", variant="minimal")
    assert header_minimal == "Điều 10. Hợp đồng vô hiệu"
    assert build_header(context, "10", "Hợp đồng vô hiệu", variant="A") == "Điều 10. Hợp đồng vô hiệu"


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

"""Tests for fine-tune alignment, leakage filtering, splitting and synthetic capping."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from labor_rag.finetune.align import V5Index, align_record, doc_year, tier_of
from labor_rag.finetune.build_dataset import LeakFilter, cap_synthetic, selectable, split_by_article
from labor_rag.finetune.sources import doc_id_from_text, is_labor_query, record

P1 = ("Người lao động làm việc đủ 12 tháng cho một người sử dụng lao động thì được nghỉ hằng năm "
      "hưởng nguyên lương theo hợp đồng lao động như sau mười hai ngày làm việc đối với người làm công việc "
      "trong điều kiện bình thường")
P2 = ("Người sử dụng lao động có trách nhiệm quy định lịch nghỉ hằng năm sau khi tham khảo ý kiến của người "
      "lao động và phải thông báo trước cho người lao động biết người lao động có thể thỏa thuận với người sử "
      "dụng lao động để nghỉ hằng năm thành nhiều lần")
OTHER = ("Thời giờ làm việc bình thường không quá 08 giờ trong 01 ngày và không quá 48 giờ trong 01 tuần "
         "người sử dụng lao động có quyền quy định thời giờ làm việc theo ngày hoặc tuần nhưng phải thông báo")


def chunk(chunk_id: str, text: str, mapc: str = "20.2.LQ.113", valid: bool = True) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": chunk_id.split(":")[0],
        "mapc": mapc,
        "text": f"Lao động > Bộ luật số 45/2019/QH14 > Chương VII\nĐiều 113. Nghỉ hằng năm\n{text}",
        "still_valid": valid,
    }


def index() -> V5Index:
    return V5Index([
        chunk("45-2019-qh14:d113:p1", P1),
        chunk("45-2019-qh14:d113:p2", P2),
        chunk("45-2019-qh14:d105", OTHER, "20.2.LQ.105"),
    ])


def test_alignment_picks_the_matching_part_not_the_first():
    rec = record("vilegal", 1, "Có được chia nghỉ phép năm thành nhiều lần không?", passage="Theo quy định: " + P2,
                 cited_doc="45-2019-qh14", exact_chunk_ids=["45-2019-qh14:d113:p1", "45-2019-qh14:d113:p2"])
    out = align_record(rec, index())
    assert out["positive_chunk_ids"][0] == "45-2019-qh14:d113:p2"
    assert out["tier"] == "A" and out["temporal"] == "keep" and out["match"] == "exact_verified"


def test_wrong_exact_mapping_falls_back_to_content():
    rec = record("vilegal", 2, "Thời giờ làm việc bình thường là bao lâu?", passage=OTHER,
                 cited_doc="45-2019-qh14", exact_chunk_ids=["45-2019-qh14:d113:p1"])
    out = align_record(rec, index())
    assert out["positive_chunk_ids"] == ["45-2019-qh14:d105"]
    assert out["match"] == "exact_rejected"


def test_old_document_with_same_content_is_remapped():
    rec = record("bkai", 3, "Nghỉ hằng năm bao nhiêu ngày?", passage=P1, cited_doc="10-2012-qh13")
    out = align_record(rec, index())
    assert out["tier"] == "A" and out["temporal"] == "remap"


def test_unmatched_records_are_pending_or_outside():
    idx = index()
    newer = align_record(record("vlsp", 4, "Trợ cấp thất nghiệp 2026?", cited_doc="74-2025-qh15"), idx)
    older = align_record(record("vlsp", 5, "Hợp đồng mùa vụ?", cited_doc="10-2012-qh13"), idx)
    assert newer["tier"] == "C" and newer["temporal"] == "pending"
    assert older["tier"] == "C" and older["temporal"] == "outside"


def test_expired_chunk_is_never_a_positive():
    idx = V5Index([chunk("45-2019-qh14:d113:p1", P1, valid=False)])
    out = align_record(record("bkai", 6, "Nghỉ hằng năm?", passage=P1), idx)
    assert out["temporal"] == "outside"
    assert selectable(out, True, 0.3) == "temporal_outside"


def test_unverified_exact_ids_are_tier_b_and_rejected_by_default():
    out = align_record(record("vlsp", 7, "Nghỉ hằng năm?", exact_chunk_ids=["45-2019-qh14:d113:p1"]), index())
    assert out["tier"] == "B" and out["score"] is None
    assert selectable(out, True, 0.3) == "tier_B_below_min"


def test_tier_thresholds_and_year_parsing():
    assert [tier_of(s) for s in (None, 0.05, 0.1, 0.49, 0.5)] == ["C", "C", "B", "B", "A"]
    assert doc_year("45-2019-qh14") == 2019
    assert doc_year("2919-nq-hdql") is None
    assert doc_id_from_text("Thông tư 09/2015/TT-BGTVT quy định") == "09-2015-tt-bgtvt"
    assert is_labor_query("Có được nghỉ phép năm không?") and not is_labor_query("Mức phạt vượt đèn đỏ?")


def test_leak_filter_catches_paraphrases():
    leak = LeakFilter(["Người lao động cần đáp ứng những điều kiện nào để được hưởng chế độ tai nạn lao động?"], 0.5)
    assert leak.leaks("Người lao động cần đáp ứng những điều kiện gì để được hưởng chế độ tai nạn lao động?")
    assert not leak.leaks("Mức lương tối thiểu vùng năm nay là bao nhiêu?")


def aligned(qid: str, article: str, *, synthetic: bool = False, tier: str = "A") -> dict:
    return {"qid": qid, "is_synthetic": synthetic, "tier": tier, "articles": [article],
            "positive_chunk_ids": [article]}


def test_split_and_cap():
    idx = V5Index([chunk(f"45-2019-qh14:d{i}", P1 + f" điều {i}", f"20.2.LQ.{i}") for i in range(20)])
    records = [aligned(f"q{i}", f"45-2019-qh14:d{i}") for i in range(20)]
    val = split_by_article(records, idx, 0.1, random.Random(0))
    assert len(val) == 2

    real = records[:6]
    synthetic = [aligned(f"s{i}", f"45-2019-qh14:d{i}", synthetic=True) for i in range(4, 14)]
    kept, dropped = cap_synthetic(real, synthetic, 0.4, random.Random(0))
    assert len(kept) == 4 and len(dropped) == 6
    covered = {r["articles"][0] for r in real}
    assert all(r["articles"][0] not in covered for r in kept)

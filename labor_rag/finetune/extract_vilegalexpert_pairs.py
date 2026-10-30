"""Trích xuất và lọc các cặp truy hồi (Query -> Positive Passage) từ ViLegalExpert cho Luật Lao Động.

Quy trình xử lý:
1. Nạp 1.481 chunks của lao_dong_v5 từ data/processed/lao_dong_v5/chunks.jsonl.
2. Nạp toàn bộ câu hỏi trong các bộ benchmark (v1, v2, v3) để chống rò rỉ dữ liệu (data leakage).
3. Nạp data/finetune/ViLegalExpert/train_data.json.
4. Nhận diện các câu hỏi & điều luật thuộc Lĩnh vực Lao động, Tiền lương, Việc làm,
   Bảo hiểm xã hội, An toàn vệ sinh lao động, Kỷ luật lao động...
5. Đối chiếu số hiệu văn bản và số Điều với chunks của lao_dong_v5:
   - Nếu khớp với chunk trong v5 -> xuất ra query kèm chunk_id và positive_text chuẩn (dùng cho in-corpus retrieval).
   - Xuất thêm tập mở rộng tất cả các cặp hỏi đáp lao động (để có thể pre-train / contrastive learning diện rộng).
6. Lưu kết quả ra:
   - data/processed/lao_dong_v5/finetune/vilegalexpert_queries.jsonl (In-corpus matched)
   - data/processed/lao_dong_v5/finetune/vilegalexpert_all_labor_pairs.jsonl (Tất cả cặp lao động)
   - data/processed/lao_dong_v5/finetune/vilegalexpert_extraction_stats.json (Thống kê chi tiết)

Cách chạy:
    python -m labor_rag.finetune.extract_vilegalexpert_pairs
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from labor_rag.config import (
    BENCHMARKS_DIR,
    DATA_DIR,
    EVALUATION_DIR,
    FINETUNE_DIR,
    LAO_DONG_DIR,
    ROOT_DIR,
)

DEFAULT_VILEGALEXPERT = DATA_DIR / "finetune" / "ViLegalExpert" / "train_data.json"
DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_MATCHED_OUTPUT = FINETUNE_DIR / "vilegalexpert_queries.jsonl"
DEFAULT_ALL_LABOR_OUTPUT = FINETUNE_DIR / "vilegalexpert_all_labor_pairs.jsonl"
DEFAULT_STATS_OUTPUT = FINETUNE_DIR / "vilegalexpert_extraction_stats.json"

LABOR_KEYWORDS = [
    "lao động", "tiền lương", "hợp đồng lao động", "thử việc", "sa thải", "thôi việc",
    "bảo hiểm xã hội", "bảo hiểm thất nghiệp", "tai nạn lao động", "bệnh nghề nghiệp",
    "kỷ luật lao động", "công đoàn", "thời giờ làm việc", "thời giờ nghỉ ngơi",
    "chế độ thai sản", "người sử dụng lao động", "người lao động", "trợ cấp mất việc",
    "tiền lương làm thêm giờ", "nghỉ phép năm", "đơn phương chấm dứt", "thỏa ước lao động",
    "trợ cấp thôi việc", "nội quy lao động", "tiền lương làm việc vào ban đêm",
    "tiền thưởng", "thang lương", "bảng lương", "bảo hộ lao động", "vệ sinh lao động"
]

DOC_NAME_TO_ID = {
    "bộ luật lao động 2019": "45-2019-qh14",
    "bộ luật lao động": "45-2019-qh14",
    "luật an toàn, vệ sinh lao động 2015": "84-2015-qh13",
    "luật an toàn vệ sinh lao động": "84-2015-qh13",
    "luật an toàn, vệ sinh lao động": "84-2015-qh13",
    "luật việc làm 2013": "38-2013-qh13",
    "luật việc làm": "38-2013-qh13",
    "luật bảo hiểm xã hội 2014": "58-2014-qh13",
    "luật bảo hiểm xã hội": "58-2014-qh13",
    "luật công đoàn 2012": "12-2012-qh13",
    "luật công đoàn": "12-2012-qh13",
    "nghị định 145/2020/nđ-cp": "145-2020-nd-cp",
    "nghị định 145/2020": "145-2020-nd-cp",
    "nghị định 152/2020/nđ-cp": "152-2020-nd-cp",
    "nghị định 152/2020": "152-2020-nd-cp",
    "nghị định 28/2015/nđ-cp": "28-2015-nd-cp",
    "nghị định 28/2015": "28-2015-nd-cp",
    "nghị định 12/2022/nđ-cp": "12-2022-nd-cp",
    "nghị định 12/2022": "12-2022-nd-cp",
    "nghị định 112/2021/nđ-cp": "112-2021-nd-cp",
    "nghị định 112/2021": "112-2021-nd-cp",
    "thông tư 10/2020/tt-bldtbxh": "10-2020-tt-bldtbxh",
    "thông tư 10/2020": "10-2020-tt-bldtbxh"
}


def clean_text(s: str) -> str:
    """Làm sạch văn bản để so khớp: viết thường, chuẩn hóa khoảng trắng và dấu câu."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(
        r"[^a-z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ\s]",
        " ",
        s,
    )
    return re.sub(r"\s+", " ", s).strip()


def normalize_so_hieu(so_hieu: str) -> list[str]:
    """Chuẩn hóa số hiệu văn bản thành các định dạng doc_id có thể có trong chunks v5."""
    if not so_hieu:
        return []
    s = so_hieu.strip().lower()
    s = s.replace("đ", "d").replace("Đ", "d")
    s = s.replace("/", "-").replace("_", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    variants = [s]
    # Ví dụ: 1-2020-tt-bldtbxh <-> 01-2020-tt-bldtbxh
    m = re.match(r"^(\d+)-(.*)$", s)
    if m:
        num, rest = m.groups()
        if len(num) == 1:
            variants.append(f"0{num}-{rest}")
        elif len(num) == 2 and num.startswith("0"):
            variants.append(f"{num[1:]}-{rest}")
    return variants


def load_frozen_benchmark_queries() -> set[str]:
    """Tải tất cả các câu hỏi benchmark hiện có để lọc trùng lặp, chống Data Leakage."""
    benchmarks: set[str] = set()
    files_to_check = [
        EVALUATION_DIR / "benchmark_questions.jsonl",
        EVALUATION_DIR / "benchmark_questions_v2.jsonl",
        EVALUATION_DIR / "results" / "benchmark_questions_v3.jsonl",
        BENCHMARKS_DIR / "lao_dong_v5" / "v1.jsonl",
        BENCHMARKS_DIR / "lao_dong_v5" / "v1.gold.jsonl",
    ]

    for p in files_to_check:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rec = json.loads(line)
                            q = clean_text(rec.get("question", ""))
                            if q:
                                benchmarks.add(q)
                        except Exception:
                            pass
    return benchmarks


def load_v5_chunks(chunks_path: Path):
    """Nạp danh bạ 1.481 chunks của lao_dong_v5 để map trực tiếp."""
    chunks = []
    doc_dieu_to_chunk = {}
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            chunks.append(c)
            doc_id = str(c.get("document_id", "")).lower().strip()
            dieu = str(c.get("meta_dieu", "")).strip()
            if doc_id and dieu:
                doc_dieu_to_chunk[(doc_id, dieu)] = c
    return chunks, doc_dieu_to_chunk


def extract_vilegalexpert(
    vilegal_path: Path = DEFAULT_VILEGALEXPERT,
    chunks_path: Path = DEFAULT_CHUNKS,
    matched_out_path: Path = DEFAULT_MATCHED_OUTPUT,
    all_labor_out_path: Path = DEFAULT_ALL_LABOR_OUTPUT,
    stats_out_path: Path = DEFAULT_STATS_OUTPUT,
) -> dict[str, Any]:
    print("1. Nạp danh bạ chunks lao_dong_v5...")
    chunks, doc_dieu_to_chunk = load_v5_chunks(chunks_path)
    print(f"   Đã nạp {len(chunks)} chunks từ {chunks_path}")

    print("2. Nạp câu hỏi benchmark để ngăn ngừa Data Leakage...")
    frozen_benchmarks = load_frozen_benchmark_queries()
    print(f"   Đã nạp {len(frozen_benchmarks)} câu hỏi benchmark cần loại trừ.")

    print(f"3. Nạp dữ liệu ViLegalExpert từ {vilegal_path}...")
    with vilegal_path.open("r", encoding="utf-8") as f:
        vle_data = json.load(f)
    print(f"   Tổng số bản ghi ViLegalExpert: {len(vle_data):,}")

    matched_queries = []
    all_labor_pairs = []
    leakage_count = 0
    duplicate_query_count = 0
    seen_queries: set[str] = set()
    covered_chunk_ids: set[str] = set()
    doc_counts = Counter()

    print("4. Xử lý và trích xuất câu hỏi thuộc Lĩnh vực Lao động...")
    for qid, item in vle_data.items():
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        if not question:
            continue

        clean_q = clean_text(question)
        if clean_q in frozen_benchmarks:
            leakage_count += 1
            continue

        if clean_q in seen_queries:
            duplicate_query_count += 1
            continue
        seen_queries.add(clean_q)

        # Kiểm tra nội dung có thuộc lĩnh vực lao động không
        full_text = (question + " " + answer).lower()
        is_labor_keyword = any(kw in full_text for kw in LABOR_KEYWORDS)

        contexts = item.get("contexts", {})
        matched_chunk = None
        matched_doc_id = None
        matched_dieu = None

        # Tìm kiếm chunk tương ứng trong lao_dong_v5
        for c_idx, c_val in contexts.items():
            so_hieu = c_val.get("Số hiệu:", "")
            doc_name = str(c_val.get("document", "")).strip().lower()
            dieu = str(c_val.get("điều", "")).strip()

            if not dieu:
                continue

            candidates = []
            if doc_name in DOC_NAME_TO_ID:
                candidates.append(DOC_NAME_TO_ID[doc_name])
            if so_hieu:
                candidates.extend(normalize_so_hieu(so_hieu))

            for cand in candidates:
                if (cand, dieu) in doc_dieu_to_chunk:
                    matched_chunk = doc_dieu_to_chunk[(cand, dieu)]
                    matched_doc_id = cand
                    matched_dieu = dieu
                    break
            if matched_chunk:
                break

        # Nếu map thành công với chunk trong v5
        if matched_chunk:
            cid = matched_chunk["chunk_id"]
            covered_chunk_ids.add(cid)
            doc_counts[matched_chunk.get("document_id", "")] += 1

            matched_rec = {
                "query_id": f"vle_{qid}",
                "query": question,
                "chunk_id": cid,
                "document_id": matched_chunk.get("document_id", ""),
                "dieu": matched_dieu,
                "positive_text": matched_chunk["text"],
                "source": "vilegalexpert",
                "link": item.get("link", ""),
            }
            matched_queries.append(matched_rec)

        # Lưu vào tập toàn bộ lao động nếu là chủ đề lao động hoặc map được vào v5
        if matched_chunk or is_labor_keyword:
            labor_rec = {
                "id": f"vle_labor_{qid}",
                "question": question,
                "answer": answer,
                "has_v5_chunk": matched_chunk is not None,
                "chunk_id": matched_chunk["chunk_id"] if matched_chunk else None,
                "positive_text": matched_chunk["text"] if matched_chunk else answer,
                "link": item.get("link", ""),
                "contexts": contexts,
            }
            all_labor_pairs.append(labor_rec)

    print("5. Lưu kết quả ra các file JSONL...")
    matched_out_path.parent.mkdir(parents=True, exist_ok=True)

    with matched_out_path.open("w", encoding="utf-8") as f:
        for r in matched_queries:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"   -> Đã lưu {len(matched_queries):,} câu hỏi map trực tiếp vào v5 tại: {matched_out_path}")

    with all_labor_out_path.open("w", encoding="utf-8") as f:
        for r in all_labor_pairs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"   -> Đã lưu {len(all_labor_pairs):,} câu hỏi lao động mở rộng tại: {all_labor_out_path}")

    stats = {
        "vilegalexpert_total": len(vle_data),
        "leakage_filtered": leakage_count,
        "duplicate_queries_filtered": duplicate_query_count,
        "in_corpus_matched_queries": len(matched_queries),
        "unique_chunks_covered": len(covered_chunk_ids),
        "total_chunks_in_corpus": len(chunks),
        "chunk_coverage_percent": round(len(covered_chunk_ids) / len(chunks) * 100, 2),
        "all_labor_pairs_count": len(all_labor_pairs),
        "top_documents_covered": dict(doc_counts.most_common(15)),
    }

    with stats_out_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"   -> Đã lưu thống kê chi tiết tại: {stats_out_path}")

    print("\n--- THỐNG KÊ CHI TIẾT ---")
    print(f"- Số mẫu map thành công với chunk v5: {stats['in_corpus_matched_queries']:,}")
    print(f"- Số chunk được bao phủ: {stats['unique_chunks_covered']}/{stats['total_chunks_in_corpus']} ({stats['chunk_coverage_percent']}%)")
    print(f"- Tổng số câu hỏi lao động mở rộng: {stats['all_labor_pairs_count']:,}")
    print("- Top 5 văn bản có nhiều câu hỏi nhất:")
    for doc, c in doc_counts.most_common(5):
        print(f"    + {doc}: {c} câu")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vilegal", type=Path, default=DEFAULT_VILEGALEXPERT, help="Đường dẫn train_data.json của ViLegalExpert")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Đường dẫn chunks.jsonl của lao_dong_v5")
    parser.add_argument("--matched-output", type=Path, default=DEFAULT_MATCHED_OUTPUT, help="File xuất ra câu hỏi map v5")
    parser.add_argument("--all-output", type=Path, default=DEFAULT_ALL_LABOR_OUTPUT, help="File xuất ra toàn bộ câu hỏi lao động")
    parser.add_argument("--stats-output", type=Path, default=DEFAULT_STATS_OUTPUT, help="File xuất thống kê")
    args = parser.parse_args()

    extract_vilegalexpert(
        vilegal_path=args.vilegal,
        chunks_path=args.chunks,
        matched_out_path=args.matched_output,
        all_labor_out_path=args.all_output,
        stats_out_path=args.stats_output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

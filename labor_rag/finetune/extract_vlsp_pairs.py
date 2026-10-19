"""Trích xuất và lọc các cặp truy hồi (Query -> Positive Text / Chunk ID) từ VLSP 2025 LegalSLM.

Quy trình xử lý mở rộng (Domain Expansion):
1. Nạp toàn bộ 1.481 chunks từ data/processed/lao_dong_v5/chunks.jsonl để map chéo chunk_id (nếu có).
2. Nạp câu hỏi benchmark đóng băng để loại trừ câu hỏi trùng lặp (chống Data Leakage).
3. Quét các mẫu QA từ `longstnguyen/vlsp2025-qa-non-reasoning` và `longstnguyen/vlsp2025-qa-reasoning`.
4. Bóc tách câu hỏi và 'Tiền đề lớn' (căn cứ pháp lý).
5. Nhận diện Lĩnh vực Lao động qua:
   - Dẫn chiếu các văn bản pháp luật lao động (Bộ luật Lao động, Luật Việc làm, Luật BHXH, Luật ATVSLĐ,
     Luật Công đoàn, Nghị định 145/2020, 152/2020, 12/2022, 38/2022, Thông tư BLĐTBXH...).
   - Cặp từ khóa Chủ thể + Nghiệp vụ/Chế độ quan hệ lao động (tiền lương, thử việc, thai sản, sa thải, thất nghiệp...).
   - Bộ lọc Blacklist loại trừ ngữ cảnh hình sự / dân sự thuần túy.
6. Nếu điều luật khớp chính xác với 1.481 chunks của v5 thì lưu `positive_chunk_ids`, nếu là quy định
   lao động mở rộng khác thì lưu toàn văn `positive_text` để huấn luyện.
7. Xuất ra file JSONL phục vụ fine-tune Bi-encoder / Reranker.

Cách chạy:
    python -m labor_rag.finetune.extract_vlsp_pairs                  # Quét mặc định tập non-reasoning
    python -m labor_rag.finetune.extract_vlsp_pairs --all           # Quét cả 2 tập (non-reasoning + reasoning)
    python -m labor_rag.finetune.extract_vlsp_pairs --limit 1000     # Chạy thử 1.000 mẫu
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from labor_rag.config import BENCHMARKS_DIR, EVALUATION_DIR, LAO_DONG_DIR, ROOT_DIR, finetune_source_dir


def norm_id(s: str) -> str:
    """Chuẩn hóa số hiệu văn bản thành format document_id (vd: 45/2019/QH14 -> 45-2019-qh14)."""
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"đ", "d", s)
    s = re.sub(r"[àáạảãâầấậẩẫăằắặẳẵ]", "a", s)
    s = re.sub(r"[èéẹẻẽêềếệểễ]", "e", s)
    s = re.sub(r"[ìíịỉĩ]", "i", s)
    s = re.sub(r"[òóọỏõôồốộổỗơờớợởỡ]", "o", s)
    s = re.sub(r"[ùúụủũưừứựửữ]", "u", s)
    s = re.sub(r"[ỳýỵỷỹ]", "y", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


# Danh mục các tên luật thông dụng ánh xạ sang số hiệu
KNOWN_LAW_NAMES = [
    (r"bộ\s*luật\s*lao\s*động\s*(?:năm\s*)?2019", "45/2019/QH14"),
    (r"bộ\s*luật\s*lao\s*động\s*(?:năm\s*)?2012", "10/2012/QH13"),
    (r"bộ\s*luật\s*lao\s*động", "45/2019/QH14"),
    (r"luật\s*an\s*toàn[,\s]+vệ\s*sinh\s*lao\s*động", "84/2015/QH13"),
    (r"luật\s*việc\s*làm", "38/2013/QH13"),
    (r"luật\s*người\s*lao\s*động\s*việt\s*nam\s*đi\s*làm\s*việc\s*ở\s*nước\s*ngoài", "69/2020/QH14"),
    (r"luật\s*bảo\s*hiểm\s*xã\s*hội\s*(?:năm\s*)?2014", "58/2014/QH13"),
    (r"luật\s*bảo\s*hiểm\s*xã\s*hội", "58/2014/QH13"),
    (r"luật\s*công\s*đoàn", "12/2012/QH13"),
]

DOC_IDENTITY_REGEX = re.compile(r"(\d+(?:/\d+)?/[A-ZĐ\-\d]+)", re.IGNORECASE)


def parse_legal_citation(premise_text: str) -> tuple[str | None, str | None]:
    """Bóc tách (số Điều, mã số hiệu văn bản) từ nội dung Tiền đề lớn."""
    m_dieu = re.search(r"điều\s+(\d+)", premise_text, re.IGNORECASE)
    dieu = m_dieu.group(1) if m_dieu else None

    premise_lower = premise_text.lower()
    for pattern, official_id in KNOWN_LAW_NAMES:
        if re.search(pattern, premise_lower):
            return dieu, official_id

    m_id = DOC_IDENTITY_REGEX.search(premise_text)
    if m_id:
        return dieu, m_id.group(1).upper()

    m_nd = re.search(r"nghị\s*định\s*(?:số\s*)?(\d+/\d+)", premise_lower)
    if m_nd:
        return dieu, f"{m_nd.group(1)}/NĐ-CP"

    return dieu, None


def load_v5_catalog():
    """Nạp danh bạ Điều luật từ chunks.jsonl của lao_dong_v5."""
    chunks_path = LAO_DONG_DIR / "chunks.jsonl"
    if not chunks_path.exists():
        return {}, {}, set()

    catalog: dict[tuple[str, str], list[str]] = {}
    valid_status: dict[str, bool] = {}
    known_doc_ids: set[str] = set()

    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            did = item["document_id"]
            dieu = str(item.get("meta_dieu", "")).strip()
            cid = item["chunk_id"]
            is_valid = bool(item.get("still_valid", True))

            known_doc_ids.add(did)
            valid_status[cid] = is_valid

            key = (did, dieu)
            if key not in catalog:
                catalog[key] = []
            catalog[key].append(cid)

    return catalog, valid_status, known_doc_ids


def load_frozen_benchmark_queries() -> set[str]:
    """Tải toàn bộ câu hỏi trong bộ benchmark đóng băng để tránh rò rỉ dữ liệu."""
    benchmark_queries = set()

    default_q = EVALUATION_DIR / "benchmark_questions.jsonl"
    if default_q.exists():
        with default_q.open(encoding="utf-8") as f:
            for line in f:
                q = json.loads(line).get("question", "").strip().lower()
                if q:
                    benchmark_queries.add(q)

    bm_v5_dir = BENCHMARKS_DIR / "lao_dong_v5"
    if bm_v5_dir.exists():
        for jsonl_file in bm_v5_dir.glob("*.jsonl"):
            with jsonl_file.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        q = json.loads(line).get("question", "").strip().lower()
                        if q:
                            benchmark_queries.add(q)
                    except Exception:
                        pass
    return benchmark_queries


# ==============================================================================
# QUY TẮC NHẬN DIỆN LĨNH VỰC LAO ĐỘNG (DOMAIN EXPANSION)
# ==============================================================================

LABOR_DOC_PATTERNS = [
    r"bộ\s*luật\s*lao\s*động",
    r"luật\s*việc\s*làm",
    r"luật\s*bảo\s*hiểm\s*xã\s*hội",
    r"luật\s*an\s*toàn[,\s]+vệ\s*sinh\s*lao\s*động",
    r"luật\s*công\s*đoàn",
    r"người\s*lao\s*động\s*việt\s*nam\s*đi\s*làm\s*việc\s*ở\s*nước\s*ngoài",
    r"bộ\s*lao\s*động[\s\-]+thương\s*binh\s*và\s*xã\s*hội",
    r"bộ\s*lđtbxh",
    r"tổng\s*liên\s*đoàn\s*lao\s*động",
    r"bảo\s*hiểm\s*xã\s*hội\s*việt\s*nam",
    r"trung\s*tâm\s*dịch\s*vụ\s*việc\s*làm",
    r"145/2020/nđ-cp",
    r"152/2020/nđ-cp",
    r"12/2022/nđ-cp",
    r"38/2022/nđ-cp",
    r"39/2016/nđ-cp",
    r"44/2016/nđ-cp",
    r"28/2015/tt-bldtbxh",
    r"10/2020/tt-bldtbxh",
    r"112/2021/nđ-cp",
    r"135/2020/nđ-cp",
]

LABOR_SUBJECTS = [
    r"người\s*lao\s*động",
    r"người\s*sử\s*dụng\s*lao\s*động",
    r"công\s*nhân",
    r"nhân\s*viên",
    r"thực\s*tập\s*sinh",
    r"người\s*học\s*nghề",
    r"thử\s*việc",
    r"công\s*đoàn\s*cơ\s*sở",
    r"tổ\s*chức\s*đại\s*diện\s*người\s*lao\s*động",
    r"người\s*lao\s*động\s*nước\s*ngoài",
    r"lao\s*động\s*nữ",
    r"lao\s*động\s*chưa\s*thành\s*niên",
]

LABOR_ACTIONS = [
    r"hợp\s*đồng\s*lao\s*động",
    r"thỏa\s*ước\s*lao\s*động",
    r"nội\s*quy\s*lao\s*động",
    r"kỷ\s*luật\s*lao\s*động",
    r"sa\s*thải",
    r"đơn\s*phương\s*chấm\s*dứt\s*hợp\s*đồng",
    r"chấm\s*dứt\s*hợp\s*đồng\s*lao\s*động",
    r"tạm\s*hoãn\s*thực\s*hiện\s*hợp\s*đồng\s*lao\s*động",
    r"thôi\s*việc",
    r"mất\s*việc\s*làm",
    r"trợ\s*cấp\s*thôi\s*việc",
    r"trợ\s*cấp\s*mất\s*việc",
    r"trợ\s*cấp\s*thất\s*nghiệp",
    r"tiền\s*lương",
    r"mức\s*lương\s*tối\s*thiểu",
    r"làm\s*thêm\s*giờ",
    r"tăng\s*ca",
    r"nghỉ\s*phép\s*năm",
    r"nghỉ\s*thai\s*sản",
    r"chế\s*độ\s*thai\s*sản",
    r"chế\s*độ\s*ốm\s*đau",
    r"tai\s*nạn\s*lao\s*động",
    r"bệnh\s*nghề\s*nghiệp",
    r"đình\s*công",
    r"bảo\s*hiểm\s*thất\s*nghiệp",
    r"sổ\s*bảo\s*hiểm\s*xã\s*hội",
    r"bảo\s*hiểm\s*xã\s*hội\s*một\s*lần",
    r"lương\s*hưu",
    r"chế\s*độ\s*tử\s*tuất",
    r"giấy\s*phép\s*lao\s*động",
    r"tiền\s*lương\s*thử\s*việc",
    r"thời\s*gian\s*thử\s*việc",
    r"thời\s*giờ\s*làm\s*việc",
]

BLACKLIST_PATTERNS = [
    r"lao\s*động\s*công\s*ích",
    r"cải\s*tạo\s*không\s*giam\s*giữ",
    r"luật\s*đất\s*đai",
    r"chứng\s*nhận\s*quyền\s*sử\s*dụng\s*đất",
    r"hôn\s*nhân\s*và\s*gia\s*đình",
    r"phân\s*chia\s*di\s*sản\s*thừa\s*kế",
    r"thuế\s*thu\s*nhập\s*doanh\s*nghiệp",
    r"tố\s*tụng\s*hình\s*sự",
]


def is_labor_domain(question: str, premise: str) -> tuple[bool, str]:
    """Kiểm tra một cặp (question, premise) trong VLSP có thuộc Lĩnh vực Lao động hay không."""
    q_low = question.lower()
    p_low = premise.lower()
    combined = f"{q_low} \n {p_low}"

    # 1. Blacklist check
    for bp in BLACKLIST_PATTERNS:
        if re.search(bp, combined):
            if not ("bộ luật lao động" in combined or "hợp đồng lao động" in combined):
                return False, ""

    # 2. Match văn bản chuyên ngành
    for pat in LABOR_DOC_PATTERNS:
        if re.search(pat, combined):
            return True, f"doc_match: {pat}"

    # 3. Match Chủ thể + Hành vi
    has_subject = any(re.search(s, combined) for s in LABOR_SUBJECTS)
    has_action = any(re.search(a, combined) for a in LABOR_ACTIONS)
    if has_subject and has_action:
        return True, "subject_and_action"

    # 4. Match thuật ngữ lao động mạnh
    strong_terms = [
        r"hợp\s*đồng\s*lao\s*động",
        r"kỷ\s*luật\s*lao\s*động",
        r"trợ\s*cấp\s*thôi\s*việc",
        r"trợ\s*cấp\s*thất\s*nghiệp",
        r"tai\s*nạn\s*lao\s*động",
        r"tiền\s*lương\s*làm\s*thêm\s*giờ",
        r"tiền\s*lương\s*thử\s*việc",
        r"thời\s*gian\s*thử\s*việc",
    ]
    for term in strong_terms:
        if re.search(term, q_low) or re.search(term, p_low):
            return True, f"strong_term: {term}"

    return False, ""


def extract_pairs_from_dataset(
    dataset_name: str,
    catalog: dict[tuple[str, str], list[str]],
    valid_status: dict[str, bool],
    known_doc_ids: set[str],
    frozen_queries: set[str],
    strict_v5: bool = False,
    limit: int = 0,
    token: str | bool = True,
):
    from datasets import load_dataset

    print(f"\n--- Đang quét: {dataset_name} ---")
    ds = load_dataset(dataset_name, split="train", streaming=True, token=token)

    total_scanned = 0
    parsed_qa = 0
    labor_matched = 0
    v5_mapped = 0
    leakage_count = 0
    seen_queries = set()

    results = []

    for row in ds:
        total_scanned += 1
        if limit > 0 and total_scanned > limit:
            break

        text = row.get("text", "")
        # Tách Question
        q_match = re.search(r"### Question\s*\n(.*?)(?=<\|im_end\|>)", text, re.DOTALL)
        # Tách Tiền đề lớn
        a_match = re.search(
            r"Tiền đề lớn:\s*(.*?)(?=\nTiền đề nhỏ:|\nKết luận:|<\|im_end\|>)", text, re.DOTALL
        )

        if not q_match or not a_match:
            continue

        parsed_qa += 1
        question = q_match.group(1).strip()
        premise = a_match.group(1).strip()

        q_norm = question.strip().lower()
        if q_norm in frozen_queries:
            leakage_count += 1
            continue

        if q_norm in seen_queries:
            continue

        # 1. Kiểm tra Lĩnh vực Lao động
        is_labor, reason = is_labor_domain(question, premise)
        if not is_labor:
            continue

        # 2. Thử bóc tách mã văn bản và số Điều
        dieu, raw_doc = parse_legal_citation(premise)
        normalized_doc = norm_id(raw_doc) if raw_doc else ""

        # 3. Thử map vào chunk v5
        matched_chunks = []
        if normalized_doc and dieu:
            lookup_key = (normalized_doc, str(dieu))
            matched = catalog.get(lookup_key, [])
            # Kiểm tra hiệu lực
            if matched and all(valid_status.get(cid, True) for cid in matched):
                matched_chunks = matched
                v5_mapped += 1

        # Nếu chạy chế độ strict_v5 mà không map được vào v5 thì bỏ qua
        if strict_v5 and not matched_chunks:
            continue

        seen_queries.add(q_norm)
        labor_matched += 1

        citation_str = f"Điều {dieu} {raw_doc}" if (dieu and raw_doc) else ""

        results.append(
            {
                "id": f"vlsp_{len(results) + 1:05d}",
                "query": question,
                "positive_text": premise,
                "positive_chunk_ids": matched_chunks,
                "document_id": normalized_doc if normalized_doc else None,
                "meta_dieu": str(dieu) if dieu else None,
                "matched_citation": citation_str,
                "matched_reason": reason,
                "source": dataset_name,
            }
        )

        if labor_matched % 50 == 0:
            print(f"  [Tiến độ] Đã quét {total_scanned} mẫu -> Tìm thấy {labor_matched} cặp Lao động (Map v5: {v5_mapped})...")

    print(f"\nTổng kết {dataset_name}:")
    print(f"  - Tổng số mẫu đã quét: {total_scanned}")
    print(f"  - Phân tích cú pháp QA thành công: {parsed_qa}")
    print(f"  - Cặp câu hỏi Lao động trích xuất: {labor_matched}")
    print(f"  - Trong đó khớp trực tiếp vào chunk v5: {v5_mapped}")
    if leakage_count > 0:
        print(f"  - Đã loại bỏ {leakage_count} câu hỏi do trùng benchmark testset")

    return results


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số mẫu quét trên mỗi tập (0 = toàn bộ)")
    parser.add_argument("--all", action="store_true", default=True, help="Quét cả qa-non-reasoning và qa-reasoning (mặc định: True)")
    parser.add_argument("--strict-v5", action="store_true", help="Chỉ giữ lại các mẫu khớp 100% vào chunks v5")
    parser.add_argument(
        "--output",
        type=Path,
        default=finetune_source_dir("vlsp") / "vlsp_lao_dong_train.jsonl",
        help="Đường dẫn file kết quả xuất ra",
    )
    args = parser.parse_args()

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or None

    print("1. Đang nạp danh bạ Điều luật từ lao_dong_v5/chunks.jsonl để map chéo...")
    catalog, valid_status, known_doc_ids = load_v5_catalog()
    print(f"   Đã nạp {len(catalog)} cặp (document_id, meta_dieu) từ {len(known_doc_ids)} văn bản.")

    print("2. Đang nạp câu hỏi benchmark đóng băng để loại trừ...")
    frozen_queries = load_frozen_benchmark_queries()
    print(f"   Đã nạp {len(frozen_queries)} câu hỏi benchmark cần loại trừ.")

    datasets_to_scan = ["longstnguyen/vlsp2025-qa-non-reasoning"]
    if args.all:
        datasets_to_scan.append("longstnguyen/vlsp2025-qa-reasoning")

    all_pairs = []
    for ds_name in datasets_to_scan:
        try:
            pairs = extract_pairs_from_dataset(
                ds_name,
                catalog=catalog,
                valid_status=valid_status,
                known_doc_ids=known_doc_ids,
                frozen_queries=frozen_queries,
                strict_v5=args.strict_v5,
                limit=args.limit,
                token=token,
            )
            all_pairs.extend(pairs)
        except Exception as e:
            print(f"\n[CẢNH BÁO] Không thể tải '{ds_name}': {e}")
            print("  Bỏ qua tập này và tiếp tục xử lý các tập dữ liệu khác...")

    # Khử trùng lặp theo query
    unique_pairs = []
    seen_queries = set()
    for p in all_pairs:
        q_norm = p["query"].strip().lower()
        if q_norm not in seen_queries:
            seen_queries.add(q_norm)
            p["id"] = f"vlsp_{len(unique_pairs) + 1:05d}"
            unique_pairs.append(p)

    v5_count = sum(1 for p in unique_pairs if p.get("positive_chunk_ids"))

    print("\n" + "=" * 60)
    print(f"TỔNG SỐ CẶP FINETUNE VLSP ĐỘC NHẤT THU ĐƯỢC: {len(unique_pairs)}")
    print(f"- Số cặp đồng thời map thành công vào chunk v5: {v5_count}")
    print(f"- Số cặp là văn bản/quy định Lao động mở rộng: {len(unique_pairs) - v5_count}")

    # Ghi file kết quả
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for p in unique_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"\nĐã lưu tập dữ liệu finetune vào: {args.output.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

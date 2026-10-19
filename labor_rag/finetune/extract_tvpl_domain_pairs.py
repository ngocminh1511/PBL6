"""Trích xuất tập dữ liệu huấn luyện mở rộng về Lĩnh vực Lao động từ GreenNode/TVPL-Retrieval-VN.

Khác với cách tiếp cận ép cứng vào 1.481 chunks của lao_dong_v5, cách tiếp cận mở rộng (Domain Expansion):
1. Quét toàn bộ corpus, queries và qrels của TVPL-Retrieval-VN.
2. Nhận diện các câu hỏi và đoạn văn bản pháp luật thuộc Lĩnh vực Lao động, Việc làm,
   Tiền lương, Bảo hiểm xã hội, An toàn vệ sinh lao động, Kỷ luật lao động... dựa trên:
   - Tên và số hiệu các văn bản quy phạm pháp luật lao động (Bộ luật Lao động, Luật Việc làm,
     Luật BHXH, Luật An toàn vệ sinh lao động, Luật Công đoàn, các Nghị định/Thông tư liên quan).
   - Cơ quan ban hành chuyên ngành (Bộ LĐTBXH, Tổng Liên đoàn Lao động, BHXH Việt Nam...).
   - Cặp từ khóa chủ thể + nghiệp vụ quan hệ lao động (người lao động, người sử dụng lao động,
     hợp đồng lao động, tiền lương, sa thải, thai sản, trợ cấp thất nghiệp...).
   - Bộ lọc loại trừ (Negative filters) để không dính án hình sự ("lao động công ích", "cải tạo không giam giữ").
3. Vẫn đối chiếu với 1.481 chunks của lao_dong_v5: nếu đoạn văn bản khớp với chunk v5 thì lưu chunk_id,
   nếu không thì vẫn lưu toàn văn đoạn trích dương tính (positive_text) để huấn luyện mô hình.
4. Kiểm tra loại trừ mọi câu hỏi trùng với benchmark đánh giá đóng băng (chống Data Leakage).
5. Xuất ra data/processed/finetune/tvpl/tvpl_lao_dong_expanded.jsonl.

Cách chạy:
    python -m labor_rag.finetune.extract_tvpl_domain_pairs
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

from labor_rag.config import BENCHMARKS_DIR, LAO_DONG_DIR, ROOT_DIR, finetune_source_dir


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


def load_v5_index():
    """Nạp danh bạ 1.481 chunks của lao_dong_v5 để đánh dấu chunk_id nếu trùng."""
    chunks_path = LAO_DONG_DIR / "chunks.jsonl"
    if not chunks_path.exists():
        return {}, defaultdict(list), []

    chunks_by_id = {}
    title_to_chunks = defaultdict(list)
    clean_chunk_records = []

    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            cid = c["chunk_id"]
            chunks_by_id[cid] = c

            dieu = str(c.get("meta_dieu", "")).strip()
            ten = clean_text(c.get("ten", ""))
            if dieu and ten:
                title_to_chunks[(dieu, ten)].append(cid)

            c_text_clean = clean_text(c.get("text", ""))
            clean_chunk_records.append({
                "chunk_id": cid,
                "document_id": c.get("document_id"),
                "meta_dieu": dieu,
                "clean_text": c_text_clean,
                "still_valid": bool(c.get("still_valid", True)),
            })

    return chunks_by_id, title_to_chunks, clean_chunk_records


def load_frozen_benchmark_queries() -> set[str]:
    """Tải toàn bộ câu hỏi trong bộ benchmark đóng băng (v1, v2) để tránh data leakage."""
    benchmark_queries = set()
    from labor_rag.config import EVALUATION_DIR

    # 1. File benchmark_questions.jsonl
    default_q = EVALUATION_DIR / "benchmark_questions.jsonl"
    if default_q.exists():
        with default_q.open(encoding="utf-8") as f:
            for line in f:
                q = json.loads(line).get("question", "").strip().lower()
                if q:
                    benchmark_queries.add(q)

    # 2. Thư mục benchmarks/lao_dong_v5/*.jsonl
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
# BỘ TỪ KHÓA VÀ QUY TẮC NHẬN DIỆN LĨNH VỰC LAO ĐỘNG
# ==============================================================================

# 1. Các văn bản luật / cơ quan chuyên ngành về Lao động
LABOR_DOC_PATTERNS = [
    r"bộ luật lao động",
    r"luật việc làm",
    r"luật bảo hiểm xã hội",
    r"luật an toàn[,\s]+vệ sinh lao động",
    r"luật công đoàn",
    r"người lao động việt nam đi làm việc ở nước ngoài",
    r"bộ lao động[\s\-]+thương binh và xã hội",
    r"bộ lđtbxh",
    r"tổng liên đoàn lao động",
    r"bảo hiểm xã hội việt nam",
    r"trung tâm dịch vụ việc làm",
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
    r"24/2018/nđ-cp",
]

# 2. Chủ thể quan hệ lao động
LABOR_SUBJECTS = [
    r"người lao động",
    r"người sử dụng lao động",
    r"công nhân",
    r"nhân viên",
    r"thực tập sinh",
    r"người học nghề",
    r"thử việc",
    r"công đoàn cơ sở",
    r"tổ chức đại diện người lao động",
    r"người lao động nước ngoài",
    r"lao động nữ",
    r"lao động chưa thành niên",
    r"người giúp việc gia đình",
]

# 3. Nghiệp vụ, chế độ và quan hệ lao động
LABOR_ACTIONS = [
    r"hợp đồng lao động",
    r"thỏa ước lao động tập thể",
    r"nội quy lao động",
    r"kỷ luật lao động",
    r"sa thải",
    r"đơn phương chấm dứt hợp đồng",
    r"chấm dứt hợp đồng lao động",
    r"tạm hoãn thực hiện hợp đồng lao động",
    r"thôi việc",
    r"mất việc làm",
    r"trợ cấp thôi việc",
    r"trợ cấp mất việc làm",
    r"trợ cấp thất nghiệp",
    r"tiền lương",
    r"mức lương tối thiểu",
    r"làm thêm giờ",
    r"làm việc vào ban đêm",
    r"tăng ca",
    r"ngày nghỉ hằng năm",
    r"nghỉ phép năm",
    r"nghỉ thai sản",
    r"chế độ thai sản",
    r"chế độ ốm đau",
    r"tai nạn lao động",
    r"bệnh nghề nghiệp",
    r"đình công",
    r"bảo hiểm thất nghiệp",
    r"sổ bảo hiểm xã hội",
    r"bảo hiểm xã hội một lần",
    r"lương hưu",
    r"chế độ tử tuất",
    r"thời giờ làm việc",
    r"thời giờ nghỉ ngơi",
    r"giấy phép lao động",
    r"tiền lương thử việc",
    r"thời gian thử việc",
    r"bồi thường chi phí đào tạo",
]

# 4. Blacklist - Loại bỏ các trường hợp ngữ cảnh hình sự / dân sự thuần túy
BLACKLIST_PATTERNS = [
    r"lao động công ích",  # Án treo, hình phạt hình sự
    r"cải tạo không giam giữ",
    r"tội vi phạm quy định về tham gia giao thông",
    r"luật đất đai",
    r"chứng nhận quyền sử dụng đất",
    r"hôn nhân và gia đình",
    r"ly hôn",
    r"phân chia di sản thừa kế",
    r"thuế thu nhập doanh nghiệp",
    r"hải quan",
]


def is_labor_domain(query_text: str, corpus_text: str) -> tuple[bool, str]:
    """Kiểm tra một cặp (query, corpus) có thuộc Lĩnh vực Lao động hay không.
    
    Trả về: (is_labor, lý_do_khớp)
    """
    q_clean = query_text.lower()
    c_clean = corpus_text.lower()
    combined = f"{q_clean} \n {c_clean}"

    # 1. Kiểm tra Blacklist loại trừ
    for bp in BLACKLIST_PATTERNS:
        if re.search(bp, combined):
            # Nếu có blacklist nhưng có văn bản BLLĐ rõ rệt thì xem xét, còn không thì loại
            if not ("bộ luật lao động" in combined or "hợp đồng lao động" in combined):
                return False, ""

    # 2. Điều kiện A: Văn bản luật hoặc cơ quan ban hành chuyên ngành
    for pat in LABOR_DOC_PATTERNS:
        if re.search(pat, combined):
            return True, f"doc_match: {pat}"

    # 3. Điều kiện B: Cặp Chủ thể + Hành vi/Chế độ Lao động
    has_subject = any(re.search(s, combined) for s in LABOR_SUBJECTS)
    has_action = any(re.search(a, combined) for a in LABOR_ACTIONS)

    if has_subject and has_action:
        return True, "subject_and_action"

    # 4. Điều kiện C: Các thuật ngữ lao động đặc thù (ngay cả khi không nói rõ chủ thể)
    strong_labor_terms = [
        r"hợp đồng lao động",
        r"kỷ luật lao động",
        r"trợ cấp thôi việc",
        r"trợ cấp mất việc làm",
        r"trợ cấp thất nghiệp",
        r"thời giờ làm việc, thời giờ nghỉ ngơi",
        r"tai nạn lao động, bệnh nghề nghiệp",
        r"tiền lương làm thêm giờ",
        r"tiền lương ngừng việc",
        r"bảo hiểm thất nghiệp",
        r"thời gian thử việc",
        r"tiền lương thử việc",
        r"đơn phương chấm dứt hợp đồng lao động",
    ]
    for term in strong_labor_terms:
        if re.search(term, q_clean) or re.search(term, c_clean):
            return True, f"strong_term: {term}"

    return False, ""


def match_chunk_v5(corpus_text: str, title_to_chunks, clean_chunk_records) -> str | None:
    """Kiểm tra xem đoạn corpus có khớp vào một chunk cụ thể trong v5 không (nếu có)."""
    c_clean = clean_text(corpus_text)
    words = c_clean.split()
    if len(words) < 15:
        return None

    # Tìm Điều X
    m = re.search(r"điều\s+(\d+)\.\s*([^\n\r.]+)", corpus_text, re.IGNORECASE)
    if m:
        dieu = m.group(1).strip()
        raw_ten = clean_text(m.group(2))
        candidates = title_to_chunks.get((dieu, raw_ten), [])
        if candidates:
            probe = " ".join(words[min(5, len(words) - 15) : min(5, len(words) - 15) + 15])
            for cid in candidates:
                for rec in clean_chunk_records:
                    if rec["chunk_id"] == cid and probe in rec["clean_text"]:
                        return cid

    return None


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    load_dotenv(ROOT_DIR / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--output",
        type=Path,
        default=finetune_source_dir("tvpl") / "tvpl_lao_dong_expanded.jsonl",
        help="Đường dẫn file kết quả xuất ra",
    )
    args = parser.parse_args()

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or None
    repo = "GreenNode/TVPL-Retrieval-VN"

    print("1. Nạp danh mục 1.481 chunks của lao_dong_v5 để map chéo (nếu có)...")
    chunks_by_id, title_to_chunks, clean_chunk_records = load_v5_index()
    print(f"   Đã nạp {len(chunks_by_id)} chunks.")

    print("2. Nạp danh sách câu hỏi benchmark đóng băng để loại trừ (tránh rò rỉ dữ liệu)...")
    frozen_queries = load_frozen_benchmark_queries()
    print(f"   Đã nạp {len(frozen_queries)} câu hỏi benchmark cần loại trừ.")

    print("3. Tải toàn bộ TVPL-Retrieval-VN (corpus, queries, qrels)...")
    from datasets import load_dataset
    corpus_ds = load_dataset(repo, "corpus", split="test", token=token)
    queries_ds = load_dataset(repo, "queries", split="test", token=token)
    qrels_ds = load_dataset(repo, "qrels", split="test", token=token)
    print(f"   Corpus: {len(corpus_ds)} đoạn | Queries: {len(queries_ds)} câu | Qrels: {len(qrels_ds)} liên kết.")

    print("4. Lập chỉ mục tra cứu nhanh cho TVPL...")
    corpus_by_id = {c["id"]: c for c in corpus_ds}
    query_text_by_id = {q["id"]: q["text"].strip() for q in queries_ds}

    print("5. Quét và trích xuất các cặp câu hỏi - trích đoạn Lĩnh vực Lao động...")
    extracted_pairs = []
    seen_queries = set()
    leakage_count = 0
    reason_counter = Counter()
    v5_mapped_count = 0

    for r in qrels_ds:
        if r.get("score", 1) < 1:
            continue

        qid = r["query-id"]
        cid = r["corpus-id"]

        q_text = query_text_by_id.get(qid, "")
        c_obj = corpus_by_id.get(cid)
        if not q_text or not c_obj:
            continue

        c_text = c_obj.get("text", "")
        c_title = c_obj.get("title", "")

        q_norm = q_text.strip().lower()
        if q_norm in frozen_queries:
            leakage_count += 1
            continue

        if q_norm in seen_queries:
            continue

        # Kiểm tra xem có thuộc Lĩnh vực Lao động hay không
        is_labor, reason = is_labor_domain(q_text, f"{c_title} {c_text}")
        if not is_labor:
            continue

        seen_queries.add(q_norm)
        reason_category = reason.split(":")[0]
        reason_counter[reason_category] += 1

        # Kiểm tra xem có khớp vào chunk v5 không
        matched_chunk_id = match_chunk_v5(c_text, title_to_chunks, clean_chunk_records)
        chunk_ids = [matched_chunk_id] if matched_chunk_id else []
        if matched_chunk_id:
            v5_mapped_count += 1

        extracted_pairs.append({
            "id": f"tvpl_exp_{len(extracted_pairs) + 1:05d}",
            "query": q_text,
            "positive_text": c_text,
            "positive_title": c_title,
            "positive_chunk_ids": chunk_ids,
            "corpus_id": cid,
            "matched_reason": reason,
            "source": "GreenNode/TVPL-Retrieval-VN",
        })

    print("\n" + "=" * 60)
    print(f"KẾT QUẢ TRÍCH XUẤT MỞ RỘNG TỪ TVPL:")
    print(f"- Tổng số cặp truy hồi Lao động trích xuất được: {len(extracted_pairs)}")
    print(f"- Số cặp đồng thời map thành công vào chunk v5: {v5_mapped_count}")
    print(f"- Số cặp là văn bản/quy định Lao động mở rộng: {len(extracted_pairs) - v5_mapped_count}")
    print(f"- Số câu hỏi bị loại vì trùng benchmark testset: {leakage_count}")
    print(f"- Phân bố lý do trích xuất: {dict(reason_counter)}")

    # In thử 5 mẫu ngẫu nhiên tiêu biểu
    print("\n--- 5 MẪU CÂU HỎI TIÊU BIỂU TRÍCH XUẤT ĐƯỢC ---")
    for i, p in enumerate(extracted_pairs[:5], 1):
        print(f"[{i}] Query: {p['query']}")
        v5_tag = f"(Khớp chunk v5: {p['positive_chunk_ids'][0]})" if p['positive_chunk_ids'] else "(Văn bản Lao động mở rộng)"
        print(f"    Trích đoạn {v5_tag}: {p['positive_text'][:120]}...\n")

    # Lưu kết quả
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for p in extracted_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"Đã lưu thành công vào: {args.output.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

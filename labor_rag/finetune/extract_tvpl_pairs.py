
"""Trích xuất và lọc các cặp truy hồi (Query -> Positive Chunk ID) từ GreenNode/TVPL-Retrieval-VN.

Đặc điểm của TVPL-Retrieval-VN:
- Định dạng BEIR gồm 3 tập con: corpus (10.576 đoạn văn bản), queries (9.985 câu hỏi), qrels (11.158 liên kết).
- Các câu hỏi trong TVPL là câu hỏi pháp lý thực tế do người dân/doanh nghiệp hỏi trên Thư Ký Luật / Thư Viện Pháp Luật.

Quy trình xử lý:
1. Nạp toàn bộ 1.481 chunks từ data/processed/lao_dong_v5/chunks.jsonl làm Ground Truth chuẩn.
2. Xây dựng bộ so khớp văn bản nhiều tầng (n-gram probe + tiêu đề Điều + độ tương đồng nội dung)
   để ánh xạ chính xác từng đoạn corpus_id trong TVPL sang chunk_id trong v5.
3. Chỉ giữ các đoạn map thành công vào văn bản Lao động v5 và still_valid == True.
4. Nối với qrels để lấy query_id tương ứng, rồi lấy toàn văn câu hỏi từ queries.
5. Kiểm tra loại trừ mọi câu hỏi trùng lặp với bộ benchmark v1/v2 của nhóm (tránh Data Leakage).
6. Xuất ra file data/processed/finetune/tvpl_lao_dong_train.jsonl.

Cách chạy:
    python -m labor_rag.finetune.extract_tvpl_pairs
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

from labor_rag.config import BENCHMARKS_DIR, LAO_DONG_DIR, PROCESSED_DIR, ROOT_DIR


def clean_text(s: str) -> str:
    """Làm sạch văn bản để so khớp: viết thường, chuẩn hóa khoảng trắng và dấu câu."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r'[\r\n\t]+', ' ', s)
    s = re.sub(r'[^a-z0-9àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ\s]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def load_v5_index():
    """Nạp và lập chỉ mục nội dung cho 1.481 chunks của lao_dong_v5."""
    chunks_path = LAO_DONG_DIR / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {chunks_path}")

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
                "raw_chunk": c
            })

    return chunks_by_id, title_to_chunks, clean_chunk_records


def load_frozen_benchmark_queries() -> set[str]:
    """Tải toàn bộ câu hỏi trong bộ benchmark đóng băng (v1, v2) để tránh data leakage."""
    benchmark_queries = set()
    bm_v5_dir = BENCHMARKS_DIR / "lao_dong_v5"
    if bm_v5_dir.exists():
        for jsonl_file in bm_v5_dir.glob("*.questions.jsonl"):
            with jsonl_file.open(encoding="utf-8") as f:
                for line in f:
                    q = json.loads(line).get("question", "").strip().lower()
                    if q:
                        benchmark_queries.add(q)
    return benchmark_queries


GENERIC_TITLES = {
    "giải thích từ ngữ", "phạm vi điều chỉnh", "đối tượng áp dụng",
    "hiệu lực thi hành", "trách nhiệm thi hành", "điều khoản thi hành",
    "quy định chuyển tiếp", "tổ chức thực hiện", "áp dụng pháp luật", "nguồn kinh phí"
}

LABOR_DOC_KEYS = [
    "bộ luật lao động", "145/2020", "luật việc làm", "an toàn, vệ sinh lao động",
    "an toàn vệ sinh lao động", "thông tư 10/2020", "nghị định 152/2020", "thông tư 28/2015",
    "người lao động việt nam đi làm việc ở nước ngoài", "quân nhân, công nhân và viên chức quốc phòng"
]


def match_corpus_to_chunk(corpus_text: str, title_to_chunks, clean_chunk_records) -> str | None:
    """So khớp 1 đoạn text trong TVPL corpus sang 1 chunk_id trong lao_dong_v5 với độ chính xác cao.
    
    Áp dụng 2 chiến lược:
    1. Tiêu đề Điều cụ thể (không phải generic) + 15-từ probe nội dung.
    2. Có từ khóa văn bản luật lao động (BLLĐ, NĐ 145, Luật Việc làm...) + 15-từ probe nội dung.
    """
    clean_corp = clean_text(corpus_text)
    words = clean_corp.split()
    if len(words) < 15:
        return None

    # Chiến lược 1: Bắt theo tiêu đề Điều luật cụ thể
    m = re.search(r"điều\s+(\d+)\.\s*([^\n\r.]+)", corpus_text, re.IGNORECASE)
    if m:
        dieu = m.group(1).strip()
        raw_ten = clean_text(m.group(2))
        
        # Chỉ xét nếu không phải tiêu đề generic dùng chung cho mọi văn bản nhà nước
        if not any(g in raw_ten for g in GENERIC_TITLES):
            candidates = []
            if (dieu, raw_ten) in title_to_chunks:
                candidates = title_to_chunks[(dieu, raw_ten)]
            else:
                for (c_dieu, c_ten), cids in title_to_chunks.items():
                    if c_dieu == dieu and (c_ten == raw_ten or (c_ten in raw_ten and len(c_ten) >= 12)):
                        candidates.extend(cids)

            if candidates:
                # Kiểm chứng bằng probe 15 từ đặc trưng nội dung
                probe_start = min(8, len(words) - 15)
                probe = " ".join(words[probe_start : probe_start + 15])
                for cid in candidates:
                    for rec in clean_chunk_records:
                        if rec["chunk_id"] == cid and probe in rec["clean_text"]:
                            return cid

    # Chiến lược 2: Đoạn văn bản có nhắc rõ tên/số hiệu văn bản pháp luật lao động
    t_lower = corpus_text.lower()
    if any(k in t_lower for k in LABOR_DOC_KEYS):
        probe_start = min(5, len(words) - 15)
        probe = " ".join(words[probe_start : probe_start + 15])
        if len(probe) >= 30:
            for rec in clean_chunk_records:
                if probe in rec["clean_text"]:
                    return rec["chunk_id"]

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
        default=PROCESSED_DIR / "finetune" / "tvpl_lao_dong_train.jsonl",
        help="Đường dẫn file kết quả xuất ra",
    )
    args = parser.parse_args()

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN") or True
    repo = "GreenNode/TVPL-Retrieval-VN"

    print("1. Nạp danh bạ Điều luật từ lao_dong_v5/chunks.jsonl...")
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

    # Tạo tra cứu nhanh cho queries và qrels
    print("4. Lập chỉ mục queries và qrels...")
    query_text_by_id = {q["id"]: q["text"].strip() for q in queries_ds}
    
    # corpus_id -> list of query_ids
    queries_by_corpus = defaultdict(list)
    for r in qrels_ds:
        if r.get("score", 1) >= 1:
            queries_by_corpus[r["corpus-id"]].append(r["query-id"])

    print("5. So khớp các đoạn corpus vào Pháp điển Lao động v5...")
    corpus_to_chunk_map = {}
    matched_corpus_count = 0
    expired_count = 0

    for item in corpus_ds:
        cid = item["id"]
        matched_chunk_id = match_corpus_to_chunk(item["text"], title_to_chunks, clean_chunk_records)
        if matched_chunk_id:
            chunk_obj = chunks_by_id[matched_chunk_id]
            if not chunk_obj.get("still_valid", True):
                expired_count += 1
                continue
            corpus_to_chunk_map[cid] = matched_chunk_id
            matched_corpus_count += 1

    print(f"   - Số đoạn corpus khớp vào Lao động v5: {matched_corpus_count}")
    print(f"   - Số đoạn bị loại vì văn bản/điều luật hết hiệu lực: {expired_count}")

    print("6. Tạo các cặp truy hồi (Query -> Positive Chunk)...")
    extracted_pairs = []
    leakage_count = 0
    seen_queries = set()

    for corpus_id, chunk_id in corpus_to_chunk_map.items():
        chunk_obj = chunks_by_id[chunk_id]
        qids = queries_by_corpus.get(corpus_id, [])

        for qid in qids:
            q_text = query_text_by_id.get(qid, "")
            if not q_text:
                continue

            q_norm = q_text.strip().lower()
            # Kiểm tra chống data leakage vào bộ test benchmark
            if q_norm in frozen_queries:
                leakage_count += 1
                continue

            # Khử trùng lặp
            if q_norm in seen_queries:
                continue
            seen_queries.add(q_norm)

            extracted_pairs.append({
                "id": f"tvpl_{len(extracted_pairs) + 1:05d}",
                "query": q_text,
                "positive_chunk_ids": [chunk_id],
                "document_id": chunk_obj.get("document_id"),
                "meta_dieu": str(chunk_obj.get("meta_dieu", "")),
                "corpus_id": corpus_id,
                "source": "GreenNode/TVPL-Retrieval-VN"
            })

    print("\n" + "=" * 60)
    print(f"TỔNG SỐ CẶP TRUY HỒI LAO ĐỘNG HỢP LỆ TỪ TVPL: {len(extracted_pairs)}")
    if leakage_count > 0:
        print(f"Đã loại bỏ {leakage_count} câu hỏi do trùng với bộ benchmark testset.")

    doc_dist = Counter(p["document_id"] for p in extracted_pairs)
    print("Phân bố câu hỏi theo văn bản pháp lý:")
    for did, count in doc_dist.most_common(12):
        print(f"  - {did}: {count} câu hỏi")

    # Lưu kết quả
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for p in extracted_pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"\nĐã lưu thành công vào: {args.output.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

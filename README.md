# PBL6 – KG-RAG cho văn bản pháp luật lao động Việt Nam

Hệ thống hỏi đáp pháp luật lao động: Bộ Pháp điển điện tử → Ontology v4 (RDF) →
Neo4j (đồ thị) + Qdrant (vector) → truy hồi lai → LLM trả lời kèm trích dẫn.

## Cấu trúc thư mục

```
PBL6/
├── labor_rag/              # Package Python chính (chạy bằng python -m labor_rag.<...>)
│   ├── config.py           # Mọi đường dẫn dự án, tính từ vị trí repo
│   ├── ingest/             # parse_jsondata, parse_demuc_html (bộ đọc HTML), build_abox (ABox v4),
│   │                       # ontology_to_jsonl, load_neo4j, embed_and_index
│   ├── retrieval/          # Query rewrite, hybrid retrieval, rerank
│   ├── generation/         # LLM client, sinh câu trả lời, kiểm tra trích dẫn
│   ├── app/                # chat.py – REPL end-to-end
│   └── evaluation/         # Benchmark embedding + bộ câu hỏi + kết quả
├── ontology/
│   ├── schema/             # TBox v4 + SHACL shapes
│   ├── abox/               # ABox đã sinh (nguồn chuẩn của dữ liệu pháp lý)
│   ├── reports/            # Báo cáo validate SHACL
│   └── cq_template.txt
├── data/                   # Chỉ data/processed/ được đưa lên git
│   ├── raw/bophapdien/     # Bộ Pháp điển gốc: jsonData.js, linh_vuc/*.html, linh_vuc_index.json
│   ├── interim/            # chu_de.json, de_muc.json, mapc_index.json, testset_cache/
│   └── processed/lao_dong_v4/   # JSONL chiếu từ ABox Lao động: chunks (Qdrant) + KG (Neo4j)
├── scripts/                # Script chạy một lần: validate ABox, sắp xếp dữ liệu thô
├── tests/                  # Competency-question tests cho ABox
├── notebooks/              # Phân tích dataset, benchmark embedding
├── docs/                   # ONTOLOGY_V4.md, KNOWN_ISSUES.md; references/ (paper, slide – không lên git)
├── docker-compose.yml      # Neo4j + Qdrant
├── requirements.txt
└── .env.example
```

## Cài đặt

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # rồi điền API key
docker compose up -d
```

Mọi lệnh đều chạy từ **thư mục gốc repo**.

## Pipeline (ontology v4, chủ đề Lao động)

Dữ liệu là toàn bộ chủ đề 20 "Lao động" của Bộ pháp điển: các đề mục 20.2–20.5, tổng cộng 1.407 Điều.
Đề mục 20.1 rỗng trong nguồn. Xem chi tiết trong [docs/ONTOLOGY_V4.md](docs/ONTOLOGY_V4.md).

```
jsonData.js ─ parse_jsondata ─► data/interim/chu_de.json, de_muc.json
linh_vuc/lao_dong/*.html ─ build_abox ─► ontology/abox/abox_lao_dong.ttl   (HTML được parse trong bộ nhớ)
abox_lao_dong.ttl ─ ontology_to_jsonl ─► data/processed/lao_dong_v4/
    ├── chunks.jsonl            ─ embed_and_index ─► Qdrant (legal_ld_v4_bkai)
    └── kg_nodes/kg_edges.jsonl ─ load_neo4j      ─► Neo4j  (dataset lao_dong_v4)
```

Mọi script đều mặc định dùng `abox_lao_dong.ttl` và `data/processed/lao_dong_v4`:

```powershell
python -m labor_rag.ingest.parse_jsondata                                 # chỉ cần chạy một lần
python -m labor_rag.ingest.build_abox --chu-de 20 --output ontology/abox/abox_lao_dong.ttl
python scripts/validate_abox.py --report ontology/reports/validation_report.json
python tests/test_cq_v4.py
python -m labor_rag.ingest.ontology_to_jsonl
python -m labor_rag.ingest.load_neo4j --replace-dataset
python -m labor_rag.ingest.embed_and_index
```

## Bộ test truy hồi v2 (chủ đề Lao động)

Bộ v1 (`benchmark_questions.jsonl`, 30 câu) chỉ phủ đề mục 20.5 và được chuyển nguyên vào bộ v2 (q01–q30). Bộ v2 thêm khoảng 120 câu trên
20.2–20.5, gồm nhiều kiểu câu hỏi, câu nhắm vào Khoản cuối của Điều dài và câu cần 2 Điều.
Câu hỏi do LLM soạn nháp, ứng viên được gom từ BM25 và 3 mô hình embedding, **nhãn do người duyệt**.
Hướng dẫn gán nhãn: [labor_rag/evaluation/annotation/GUIDELINES.md](labor_rag/evaluation/annotation/GUIDELINES.md).

```powershell
python -m labor_rag.evaluation.build_testset sample     # chọn Điều nguồn  -> annotation/seeds.jsonl
python -m labor_rag.evaluation.build_testset draft      # LLM soạn câu hỏi (chạy tiếp được nếu bị ngắt)
python -m labor_rag.evaluation.build_testset pool       # gom ứng viên: BM25 + bkai + bge-m3 + mpnet
python -m labor_rag.evaluation.build_testset judge      # LLM gợi ý điểm 0-3
python -m labor_rag.evaluation.build_testset export     # -> annotation/review.xlsx (người duyệt)
python -m labor_rag.evaluation.build_testset finalize   # -> benchmark_questions_v2.jsonl
python -m labor_rag.evaluation.build_testset stats

python -m labor_rag.evaluation.embedding_benchmark --rebuild `
    --questions labor_rag/evaluation/benchmark_questions_v2.jsonl `
    --results-dir labor_rag/evaluation/results/lao_dong_v2
```

## Chạy chatbot

Chatbot mặc định dùng collection `legal_ld_v4_bkai` và dataset `lao_dong_v4`. Có thể đổi qua `.env`.

```powershell
python -m labor_rag.app.chat
```

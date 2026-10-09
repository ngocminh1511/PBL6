# PBL6 – KG-RAG cho văn bản pháp luật lao động Việt Nam

Hệ thống hỏi đáp pháp luật lao động: Bộ Pháp điển điện tử → Ontology v4 (RDF) →
Neo4j (đồ thị) + Qdrant (vector) → truy hồi lai → LLM trả lời kèm trích dẫn.

## Cấu trúc thư mục

```
PBL6/
├── labor_rag/              # Package Python chính (chạy bằng python -m labor_rag.<...>)
│   ├── config.py           # Mọi đường dẫn dự án, tính từ vị trí repo
│   ├── ingest/             # Parse dữ liệu, dựng chunk/KG, nạp Neo4j & Qdrant
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
│   ├── interim/            # chu_de.json, de_muc.json, mapc_index.json, parsed/
│   ├── legacy/             # chunks + KG của pipeline cũ (collection labor_dieu)
│   └── processed/ontology_v4/   # JSONL chiếu từ ABox v4 cho Neo4j/Qdrant
├── scripts/                # Script chạy một lần: parse ABox, validate, sắp xếp dữ liệu thô
├── tests/                  # Competency-question tests cho ABox
├── notebooks/              # Phân tích dataset, benchmark embedding
├── docs/                   # ONTOLOGY_V4.md; references/ (paper, slide – không lên git)
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

## Pipeline ontology v4 (khuyến nghị)

Xem chi tiết trong [docs/ONTOLOGY_V4.md](docs/ONTOLOGY_V4.md).

```powershell
python scripts/parse_an_toan_ve_sinh_lao_dong_abox.py
python scripts/validate_abox.py --report ontology/reports/validation_report.json
python tests/test_cq_v4.py
python -m labor_rag.ingest.ontology_to_jsonl --abox ontology/abox/abox_an_toan_ve_sinh_lao_dong.ttl
python -m labor_rag.ingest.load_neo4j --data-dir data/processed/ontology_v4 --dataset-id an_toan_ve_sinh_lao_dong_v4
python -m labor_rag.ingest.embed_and_index --chunks data/processed/ontology_v4/chunks.jsonl --collection legal_v4_bkai
```

## Pipeline cũ (legacy, collection `labor_dieu`)

```powershell
python -m labor_rag.ingest.parse_jsondata                 # -> data/interim/
python -m labor_rag.ingest.parse_demuc_html <de_muc_id>   # -> data/interim/parsed/
python -m labor_rag.ingest.build_chunks                   # -> data/legacy/chunks.jsonl
python -m labor_rag.ingest.build_kg                       # -> data/legacy/kg_*.jsonl
python -m labor_rag.ingest.load_neo4j
python -m labor_rag.ingest.embed_and_index
```

## Chạy chatbot

```powershell
python -m labor_rag.app.chat
```

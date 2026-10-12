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
│   ├── ocr/                # PDF/ảnh người dùng tải lên → text (PyMuPDF + VietOCR) → cấu trúc Điều/Khoản/Điểm
│   └── evaluation/         # Benchmark embedding + bộ câu hỏi + kết quả
├── ontology/
│   ├── schema/             # TBox v4 + SHACL shapes
│   ├── abox/               # ABox đã sinh (nguồn chuẩn của dữ liệu pháp lý)
│   ├── reports/            # Báo cáo validate SHACL
│   └── cq_template.txt
├── data/                   # Chỉ data/processed/ được đưa lên git
│   ├── raw/bophapdien/     # Bộ Pháp điển gốc: jsonData.js, linh_vuc/*.html, linh_vuc_index.json
│   ├── interim/            # chu_de.json, de_muc.json, testset_cache/, ocr/ (output OCR)
│   ├── models/vietocr/     # config + weights VietOCR, tự tải ở lần OCR đầu tiên
│   └── processed/lao_dong_v4/   # JSONL chiếu từ ABox Lao động: chunks (Qdrant) + KG (Neo4j)
├── scripts/                # Script chạy một lần: validate ABox, sắp xếp dữ liệu thô
├── tests/                  # Competency-question tests cho ABox, unit test OCR
├── notebooks/              # Phân tích dataset, benchmark embedding
├── docs/                   # ONTOLOGY_V4.md, KNOWN_ISSUES.md; references/ (paper, slide – không lên git)
├── docker-compose.yml      # Neo4j + Qdrant
├── requirements.txt
├── requirements-ocr.txt    # phụ thuộc riêng của labor_rag/ocr (xem mục OCR)
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

## Chạy embedding trên Modal, dùng Qdrant/Neo4j trên cloud (tùy chọn)

Không bắt buộc chạy GPU, Qdrant hay Neo4j trên máy:

- **Embedding trên Modal** (GPU T4): Modal chỉ tính vector rồi trả về; máy local upsert vào Qdrant mà
  `QDRANT_URL` trỏ tới (docker local hoặc Qdrant Cloud). Không có credential Qdrant/Neo4j nào gửi lên Modal.
- **Qdrant Cloud** (free 1 GB) thay container `qdrant`: đặt `QDRANT_URL` + `QDRANT_API_KEY` trong `.env`.
- **Neo4j AuraDB Free** thay container `neo4j`: đặt `NEO4J_URI=neo4j+s://...`, `NEO4J_USER`, `NEO4J_PASSWORD`.
  Dữ liệu Lao động (~7.400 node, ~18.400 cạnh) nằm trong giới hạn gói Free.

Khi đã dùng cả hai cloud thì không cần `docker compose up`. Vector của câu hỏi lúc chat vẫn tính ở máy (CPU đủ nhanh cho một câu).

```powershell
pip install modal
modal setup                                   # đăng nhập Modal (một lần)
modal deploy scripts/modal_embed.py           # deploy app (một lần, và sau mỗi lần sửa file này)
modal run scripts/modal_embed.py              # (tùy chọn) thử embed 2 câu trên GPU

python -m labor_rag.ingest.embed_and_index --backend modal
python -m labor_rag.ingest.embed_and_index --backend modal --model BAAI/bge-m3 --collection legal_ld_v4_bge
python -m labor_rag.ingest.load_neo4j --replace-dataset   # ghi vào NEO4J_URI (local hoặc Aura)
```

Benchmark embedding dùng lại collection đã có nếu đủ 1.407 `mapc` và đúng số chiều, nên có thể index
ba collection `legal_ld_v4_{bkai,bge,mpnet}` bằng Modal như trên rồi chạy `embedding_benchmark` **không** kèm `--rebuild`.

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

## OCR văn bản người dùng tải lên

`labor_rag/ocr` nhận PDF (có text layer hoặc bản scan) hoặc ảnh chụp (jpg/png/tiff/…), trả về text đã làm sạch
và cây Phần > Chương > Mục > Điều > Khoản > Điểm. Trang có text layer đọc bằng PyMuPDF; trang scan và ảnh
đọc bằng VietOCR (`vgg_transformer`). VietOCR chỉ nhận dạng từng dòng, nên module tự tách dòng: projection
ngang, tách dải nhiều dòng dính dấu, tách cột rộng (quốc hiệu / tên cơ quan), cắt dòng dài tại khoảng trắng
giữa từ để không bị VietOCR bóp ngang (ảnh đầu vào bị giới hạn 32×512 px), thêm viền trắng quanh mỗi mảnh.

Cài đặt (một lần, sau `requirements.txt`):

```powershell
pip install -r requirements-ocr.txt
pip install vietocr==0.3.13 --no-deps
pip install torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu132   # cùng bản build với torch
```

Lần OCR đầu tiên tải config + weights (~150 MB) vào `data/models/vietocr/`; các lần sau chạy offline.
Cấu hình qua `.env` (`OCR_DEVICE`, `OCR_MODEL`, `OCR_DPI`, …, xem `.env.example`).

Gọi từ app:

```python
from labor_rag.ocr import OCRUnavailableError, extract_text, process_document

result = extract_text(upload_bytes, filename="hop_dong.jpg")   # hoặc đường dẫn file
text = result.clean_text()           # toàn văn đã làm sạch
result.ocr_confidence                # độ tin cậy trung bình của VietOCR, None nếu không trang nào phải OCR
result.ocr_quality()                 # điểm heuristic 0-100, dùng để cảnh báo ảnh mờ

doc = process_document("nghi_dinh.pdf", progress=lambda msg, pct: print(msg, pct))
doc.document                         # LegalDocument: cây Phần/Chương/Mục/Điều/Khoản/Điểm + metadata
doc.records                          # FlatRecord: mỗi Điểm/Khoản/Điều một bản ghi kèm đường dẫn phân cấp
```

`progress` được gọi trước mỗi trang OCR; raise exception trong đó để hủy job. Model được tải lười ở trang
OCR đầu tiên; gọi `labor_rag.ocr.engine.get_predictor()` lúc khởi động server để tải trước.

Dòng lệnh (ghi JSONL vào `data/interim/ocr/`):

```powershell
python -m labor_rag.ocr --input duong_dan.pdf                       # flat JSONL
python -m labor_rag.ocr --input thu_muc/ --format flat hierarchical
python -m labor_rag.ocr --input anh_chup.jpg --no-export            # chỉ in tóm tắt
python tests/test_ocr_pipeline.py                                    # unit test, không cần model
```

## Chạy chatbot

Chatbot mặc định dùng collection `legal_ld_v4_bkai` và dataset `lao_dong_v4`. Có thể đổi qua `.env`.

```powershell
python -m labor_rag.app.chat
```

# PBL6 – KG-RAG cho văn bản pháp luật lao động Việt Nam

Hệ thống hỏi đáp pháp luật lao động: Bộ Pháp điển điện tử → Ontology v4 (RDF) →
Neo4j (đồ thị) + Qdrant (vector) → truy hồi lai → LLM trả lời kèm trích dẫn.

## Chạy ứng dụng sau khi hợp nhất

Hướng dẫn PowerShell để chạy hằng ngày và dùng venv hiện có: [docs/RUN.md](docs/RUN.md).

Ứng dụng dùng **Next.js → một backend FastAPI → thư viện `labor_rag`**.
Nút **Phụ lục & kiểm tra truy hồi** mở `/appendices`, không yêu cầu đăng nhập.
Trang chat dùng pipeline đầy đủ có LLM và phụ lục; công cụ retrieval chỉ chạy embedding, Qdrant và Neo4j.

Từ thư mục gốc, cài Python và dùng `.env` hiện có (chỉ sao chép `.env.example` ở lần thiết lập đầu):

```powershell
pip install -e ".[api,rag,ocr,dev]"
python run_backend.py
```

Kết nối Neo4j TLS (`neo4j+s://`, `bolt+s://`) tự nạp bộ CA `certifi` cùng CA hệ thống,
giữ xác minh chứng chỉ và hostname. `certifi` được cài qua extra `rag`; không cần đặt
`SSL_CERT_FILE` thủ công trên mỗi máy.

Mở terminal khác:

```powershell
npm --prefix src/frontend ci
npm --prefix src/frontend run dev
```

Frontend: http://localhost:3000 · Phụ lục: http://localhost:3000/appendices · API: http://127.0.0.1:8000/docs.
Frontend dev dùng `.next-dev`, build/start production dùng `.next`, nên chạy build không ghi đè cache của dev server đang mở.
`BACKEND_ORIGIN` là biến phía server của Next.js, không có hậu tố `/api`; browser luôn gọi `/api` cùng origin.
Proxy `/api` chờ tối đa 5 phút cho truy hồi cloud và các lượt gọi LLM. Lỗi hạn mức (429) hoặc yêu cầu quá lớn (413)
được chat trả thành `503` kèm nguyên nhân an toàn; kiểm tra quota/model trên `/admin`, không coi đó là câu trả lời thành công.
Mỗi phản hồi mới hiển thị token đầu vào/đầu ra/tổng do LLM báo cáo, kèm chi tiết từng bước (cả đặt tên phiên).
Số liệu lưu cùng lịch sử; phản hồi cũ hoặc provider thiếu `usage` hiển thị chưa có số liệu, không ước tính từ ký tự.
Tổng chưa đủ số liệu được ghi rõ; token yêu cầu trong lỗi 413/429 không cộng vào token đã xử lý.

Mặc định dùng Qdrant/Neo4j cloud, Modal và R2 đã cấu hình trong `.env`. Bổ sung PostgreSQL và Redis cloud:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/lexgraph_db?sslmode=require
REDIS_URL=rediss://default:PASSWORD@HOST:PORT/0
DEMO_MODE=true
EMBEDDING_BACKEND=modal
QUERY_EMBEDDING_BACKEND=modal
```

Thiếu PostgreSQL: công cụ phụ lục/retrieval vẫn hoạt động; chat có lưu lịch sử, upload và lưu cấu hình trả `503`.
Thiếu Redis: ứng dụng không cache, lịch sử vẫn lưu PostgreSQL. Không tự chuyển sang SQLite hoặc embedding local.
SQLite chỉ dùng khi đặt `DATABASE_URL=sqlite:///...` rõ ràng cho kiểm thử/local.

Cấu hình quản trị được kiểm tra rồi lưu PostgreSQL và áp dụng đồng bộ. Tác vụ đang chạy hoặc version cấu hình cũ làm thao tác lưu trả `409`.
Thứ tự cấu hình: mặc định → `.env` → biến môi trường → overrides đã lưu PostgreSQL.
PostgreSQL và khóa mã hóa lấy từ môi trường. API key, mật khẩu dịch vụ và Redis URL có thể nhập trên trang quản trị; secret được mã hóa trong PostgreSQL. Collection khác model cần index trước và đăng ký:

```dotenv
COLLECTION_MODELS={"legal_ld_v5_bge":"BAAI/bge-m3"}
```

Trang **Cấu hình hệ thống** (`/admin`) gồm LLM, embedding, Qdrant, Neo4j, R2, Redis và OCR/upload.
Các nhóm nằm trong thanh điều hướng; mỗi lần mở một nhóm để tránh form kéo dài. Mục LLM quản lý nhiều cấu hình có tên:
**Thêm cấu hình → chọn Local/Cloud → nhà cung cấp hoặc máy chủ → model và key → kiểm tra/lưu**.
Có thể thêm nhiều kết nối Gemini với các key/model khác nhau, sửa hoặc xóa từng cấu hình và chọn **Dùng** để chuyển kết nối đang chạy.
Thêm cấu hình không tự đổi LLM đang dùng, trừ khi chọn **Sử dụng cấu hình này sau khi lưu**. Cấu hình đang dùng cần được chuyển
sang kết nối khác trước khi xóa. Local hỗ trợ Ollama, LM Studio và API tương thích OpenAI; danh sách model được lấy từ máy chủ
đã cấu hình, không phải danh sách mẫu. Địa chỉ hoặc key thay đổi sẽ loại bỏ danh sách/kết quả kiểm tra cũ.
Nhập địa chỉ/thông tin xác thực, bấm **Kiểm tra**, rồi **Lưu và áp dụng nhóm này** hoặc **Lưu tất cả thay đổi**.
Dấu ✓ xác nhận kết quả kiểm tra thực tế; sửa trường liên quan sẽ bỏ xác nhận cũ. Lưu chỉ kiểm tra các nhóm bị ảnh hưởng;
đổi embedding/collection sẽ kiểm tra thêm cặp model và số chiều. Collection phải có sẵn, dùng đúng model đã khai báo.
Đăng ký model của collection hiện có trong phần **Nâng cao** của Qdrant; thao tác này không đổi vector hay lập chỉ mục lại.

Mỗi trường hiển thị nguồn đang dùng. **Dùng giá trị môi trường** xóa override khi lưu và khôi phục giá trị từ cấu hình
khởi động; biến môi trường tiến trình ưu tiên hơn `.env`, sau cùng là mặc định. Ô secret để trống giữ nguyên giá trị.
**Bỏ xác thực** lưu giá trị rỗng tường minh với các dịch vụ cho phép; không tự lấy lại key từ `.env`.

Để lưu secret mới, tạo một khóa Fernet bằng Python trong môi trường đã cài extra `api`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Đặt kết quả vào `CONFIG_ENCRYPTION_KEY` trong môi trường backend và khởi động lại. Giữ khóa này ổn định, sao lưu riêng
khỏi database; mất hoặc đổi khóa khiến cấu hình mã hóa không đọc được và các thao tác phụ thuộc bị chặn rõ ràng.
API không trả lại secret đã lưu; Redis URL được xem là secret vì có thể chứa mật khẩu. Thiếu khóa vẫn dùng và kiểm tra
được secret từ môi trường, đồng thời lưu được thay đổi không chứa secret mới.

LLM local dùng `LLM_PROVIDER=local`, `LOCAL_LLM_BASE_URL` (ví dụ `http://127.0.0.1:11434/v1`), `LOCAL_LLM_MODEL`
và API key tùy chọn. Server/model phải được chuẩn bị sẵn. Nút **Tải danh sách model** dùng thông tin đang nhập,
vẫn cho nhập tên thủ công; danh sách không xác nhận quyền dùng miễn phí. Kiểm tra LLM sinh một phản hồi ngắn và dùng hạn mức API.
Mỗi cấu hình LLM có **Mức suy luận** (`LLM_REASONING`: default/off/low/medium/high), được chuyển thành `thinking_level`/`thinking_budget` (Gemini) hoặc `reasoning_effort` (Groq, OpenAI-compatible). Token suy luận tính vào giới hạn đầu ra nên backend cộng thêm khoảng dự phòng theo mức; phân loại ý định, đặt tên phiên, viết lại truy vấn, rerank và kiểm tra kết nối luôn dùng mức thấp nhất. Model từ chối tham số sẽ được gọi lại một lần không kèm tham số.
Các địa chỉ local được truy cập từ **máy chạy backend**. R2 kiểm tra bucket chỉ đọc; đổi bucket không di chuyển file cũ.
Kiểm tra OCR cần dependency và file model đã có; đổi OCR chỉ áp dụng cho tài liệu xử lý tiếp theo.

Khi PostgreSQL chưa kết nối, trang vẫn cho xem/kiểm tra theo quyền hiện có; lưu trả `503`, cần cấu hình `DATABASE_URL`
và restart backend. `DATABASE_URL`, `CONFIG_ENCRYPTION_KEY`, JWT, CORS, đường dẫn runtime và `BACKEND_ORIGIN` là thiết lập
khởi động qua môi trường. Giao diện không khởi chạy Docker, tạo collection, nạp dữ liệu hoặc tự tải LLM local.
Cấu hình này điều khiển backend; CLI tiếp tục nhận cấu hình tường minh hoặc dùng môi trường.

Để thiết lập PostgreSQL lần đầu, mở mục **PostgreSQL** trên `/admin`: dán connection string hoặc nhập host, port,
database, tài khoản, mật khẩu và SSL. **Kiểm tra** chỉ chạy `SELECT 1`, không tạo bảng hoặc ghi dữ liệu.
**Lưu vào .env** kiểm tra lại rồi cập nhật riêng `DATABASE_URL`, giữ các cấu hình khác; thao tác này dùng được khi
chưa có PostgreSQL hoặc khóa mã hóa. Trạng thái **Đã lưu** được giữ sau khi tải lại trang; ô URI trống chỉ để bảo vệ mật khẩu.
Sau khi lưu, bấm **Áp dụng kết nối đã lưu** để thiết lập hoặc kết nối lại database khi backend đang chưa kết nối. Bước này
chuẩn bị schema bổ sung và nạp cấu hình từ database đích, chỉ chuyển tài nguyên khi toàn bộ bước chuẩn bị thành công;
tác vụ đang chạy sẽ làm thao tác trả `409`. Đổi sang một database khác khi database hiện tại đang hoạt động vẫn cần
dừng backend bằng `Ctrl+C` và chạy lại `python run_backend.py`. Database đích phải được tạo sẵn;
thay kết nối không sao chép lịch sử, tài khoản hay tài liệu từ database cũ. Nếu `DATABASE_URL` được đặt trực tiếp
trong môi trường tiến trình/container và khác giá trị trong `.env`, cần cập nhật hoặc bỏ override đó để giá trị trong `.env` có hiệu lực.
Thông tin xác thực đã lưu không được trả lại qua API; ô nhập trống giữ thông tin hiện có cho cùng máy chủ/tài khoản.

Khởi động có migration **bổ sung** theo revision trong `app_schema_versions`; dữ liệu cũ được giữ nguyên.
Revision `002_chat_token_usage` thêm cột JSON nullable vào lịch sử chat; bản ghi cũ giữ giá trị null.
Không tự nạp tài liệu mẫu, recreate collection hoặc xóa dataset. Upload dùng một worker; tác vụ gián đoạn do restart
được đánh dấu thất bại để nạp lại. Chạy **một process backend** trong phiên bản này.

Docker ứng dụng kết nối cloud: `docker compose --profile app up --build`.
Dịch vụ local tùy chọn: `docker compose --profile local up -d` rồi đặt URL local rõ ràng trong `.env`.
Compose giữ tên project `labor_rag` và các volume Neo4j/Qdrant cũ. Không chạy stack cũ trong `src` trên cùng cổng.
`.env` không được đưa vào image; Compose truyền biến môi trường lúc chạy.

```powershell
python -m pytest tests/test_postgres_configuration.py tests/test_admin_configuration.py tests/test_unified_backend.py tests/test_retrieval_inspect.py tests/test_appendices.py tests/test_r2_storage.py -q
npm --prefix src/frontend run test:config
npm --prefix src/frontend run test:chat
npm --prefix src/frontend run build
```

Quy ước module: [AGENTS.md](AGENTS.md). Thuật toán và benchmark: [docs/SYSTEM.md](docs/SYSTEM.md).

## Cấu trúc thư mục

```
PBL6/
├── labor_rag/              # Package Python chính (chạy bằng python -m labor_rag.<...>)
│   ├── config.py           # Mọi đường dẫn dự án, tính từ vị trí repo
│   ├── ingest/             # parse_jsondata, parse_demuc_html (bộ đọc HTML), build_abox (ABox v4),
│   │                       # ontology_to_jsonl, load_neo4j, embed_and_index
│   ├── retrieval/          # Query rewrite, hybrid retrieval, rerank
│   ├── generation/         # LLM client, sinh câu trả lời, kiểm tra trích dẫn
│   ├── services/           # Pipeline chat/upload và embedding dùng chung
│   ├── settings.py         # Cấu hình dùng chung API/CLI
│   ├── app/                # chat.py – REPL gọi service chung
│   ├── ocr/                # PDF/ảnh người dùng tải lên → text (PyMuPDF + VietOCR) → cấu trúc Điều/Khoản/Điểm
│   └── evaluation/         # Benchmark embedding, benchmarks/<dataset_id>/ (bộ câu hỏi đóng băng), results/
├── src/
│   ├── backend/            # FastAPI: HTTP, phiên, persistence, cấu hình
│   └── frontend/           # Next.js: chat, văn bản, phụ lục, quản trị
├── ontology/
│   ├── schema/             # TBox v4 + SHACL shapes
│   ├── abox/               # ABox đã sinh (nguồn chuẩn của dữ liệu pháp lý)
│   ├── reports/            # Báo cáo validate SHACL
│   └── cq_template.txt
├── data/                   # Chỉ data/processed/ được đưa lên git
│   ├── raw/bophapdien/     # Bộ Pháp điển gốc: jsonData.js, linh_vuc/*.html, linh_vuc_index.json
│   ├── interim/            # chu_de.json, de_muc.json, testset_cache/, ocr/ (output OCR)
│   ├── models/vietocr/     # config + weights VietOCR, tự tải ở lần OCR đầu tiên
│   └── processed/lao_dong_v5/   # JSONL chiếu từ ABox Lao động: chunks v5 (Qdrant) + KG (Neo4j), dựng trên schema ontology v4
├── scripts/                # Script chạy một lần: validate ABox, sắp xếp dữ liệu thô
├── tests/                  # Competency-question tests cho ABox, unit test OCR
├── notebooks/              # Phân tích dataset, benchmark embedding
├── docs/                   # SYSTEM.md (cách hệ thống hoạt động); references/ (paper, slide – không lên git)
├── docker-compose.yml      # Profile app/cloud và local tùy chọn
├── pyproject.toml          # Nguồn khai báo dependency Python
├── requirements.txt        # mọi thư viện; OCR cần cài thêm vietocr, torchvision (xem mục OCR)
└── .env.example
```

## Cài đặt

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # rồi điền API key
docker compose --profile local up -d
```

Mọi lệnh đều chạy từ **thư mục gốc repo**.

## Pipeline (ontology v4, chủ đề Lao động)

Dữ liệu là toàn bộ chủ đề 20 "Lao động" của Bộ pháp điển: các đề mục 20.2–20.5, tổng cộng 1.407 Điều.
Đề mục 20.1 rỗng trong nguồn. Xem chi tiết trong [docs/SYSTEM.md](docs/SYSTEM.md).

```
jsonData.js ─ parse_jsondata ─► data/interim/chu_de.json, de_muc.json
linh_vuc/lao_dong/*.html ─ build_abox ─► ontology/abox/abox_lao_dong.ttl   (HTML được parse trong bộ nhớ)
abox_lao_dong.ttl ─ ontology_to_jsonl ─► data/processed/lao_dong_v5/
    ├── chunks.jsonl            ─ embed_and_index ─► Qdrant (legal_ld_v5_bge)
    └── kg_nodes/kg_edges.jsonl ─ load_neo4j      ─► Neo4j  (dataset lao_dong_v5)
```

`chunks.jsonl` theo cấu trúc v5 ([docs/SYSTEM.md](docs/SYSTEM.md), mục 4): `chunk_id` là
`{số hiệu văn bản}:d{số Điều trong văn bản gốc}` (vd `45-2019-qh14:d35`), Điều dài hơn 1024 token bge-m3
được cắt theo khoản thành `...:p1`, `...:p2`. `mapc` vẫn giữ để nối Neo4j và chấm bộ test.

Mọi script đều mặc định dùng `abox_lao_dong.ttl` và `data/processed/lao_dong_v5`:

```powershell
python -m labor_rag.ingest.parse_jsondata                                 # chỉ cần chạy một lần
python -m labor_rag.ingest.build_abox --chu-de 20 --output ontology/abox/abox_lao_dong.ttl
python scripts/validate_abox.py --report ontology/reports/validation_report.json
python tests/test_cq_v4.py
python -m labor_rag.ingest.ontology_to_jsonl
python -m labor_rag.ingest.load_neo4j --replace-dataset
python -m labor_rag.ingest.embed_and_index
```

## Nạp PDF / văn bản hợp nhất (tùy chọn)

PDF (văn bản gốc hoặc VBHN, kể cả bản scan) được OCR rồi chuyển thành chunk v5 cùng định danh với Pháp điển,
sau đó gộp vào collection đang có: với mỗi Điều, bản có `version_date` mới hơn được giữ
(chi tiết: [docs/SYSTEM.md](docs/SYSTEM.md), mục 4.7 và 5). Cần các gói OCR (mục OCR) và
`data/processed/lao_dong_v5` đã sinh (để tra `mapc`).

```powershell
python -m labor_rag.ingest.pdf_to_chunks --input docs/Luat_lao_dong.pdf          # OCR, ghi data/interim/pdf_chunks/ + ontology/abox/pdf/
python -m labor_rag.ingest.pdf_to_chunks --from-json data/interim/pdf_chunks/45-2019-qh14_hierarchical.jsonl  # dựng lại chunk, không OCR lại
python -m labor_rag.ingest.ontology_to_jsonl                                       # ghép ABox của PDF vào đồ thị
python -m labor_rag.ingest.load_neo4j --replace-dataset
python -m labor_rag.ingest.embed_and_index --upsert                                # chunk Pháp điển: chỉ cập nhật metadata
python -m labor_rag.ingest.embed_and_index --chunks data/interim/pdf_chunks/45-2019-qh14_chunks.jsonl --upsert
```

Sửa đổi và thay thế mà PDF nêu được ghi vào ABox của PDF (`ontology/abox/pdf/<document_id>.ttl`), nên có trong Neo4j;
Qdrant chỉ nhận ngày hết hiệu lực suy ra từ đó. `--upsert` không embedding lại Điều có nội dung không đổi, chỉ cập nhật metadata.

Dựng lại collection (`embed_and_index` không kèm `--upsert`) sẽ xóa chunk PDF, nên lệnh dừng lại nếu collection đang có chunk
không phải Pháp điển. Muốn dựng lại thật (ví dụ đổi model) thì thêm `--recreate`, sau đó chạy lại các lệnh `--upsert`.

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
python -m labor_rag.ingest.embed_and_index --backend modal --model bkai-foundation-models/vietnamese-bi-encoder --collection legal_ld_v5_bkai
python -m labor_rag.ingest.load_neo4j --replace-dataset   # ghi vào NEO4J_URI (local hoặc Aura)
```

Benchmark embedding dùng lại collection đã có nếu đủ các `chunk_id`, đúng text và đúng số chiều. Vì vậy có thể index
ba collection `legal_ld_v5_{bkai,bge,mpnet}` bằng Modal như trên, rồi chạy `embedding_benchmark` (mục dưới).
Collection nào thiếu hoặc lệch text sẽ được benchmark tạo lại bằng model chạy trên máy.

## Benchmark theo phiên bản dữ liệu

Mỗi phiên bản dữ liệu (`data/processed/<dataset_id>`, ví dụ `lao_dong_v5`) có benchmark riêng, đóng băng trong
`labor_rag/evaluation/benchmarks/<dataset_id>/`. Manifest ghi sha256 của chunks, KG, TBox và ABox.
Benchmark **không chạy** nếu chunks hoặc bộ câu hỏi đã đổi so với lúc đóng băng. Thiết kế và metric:
[docs/SYSTEM.md](docs/SYSTEM.md), mục 10.

```powershell
# đóng băng một bộ câu hỏi (relevance {mapc: grade 1-3}) cho một phiên bản dữ liệu
python -m labor_rag.evaluation.benchmark_version freeze --dataset lao_dong_v5 --testset v1 `
    --questions labor_rag/evaluation/benchmark_questions.jsonl
python -m labor_rag.evaluation.benchmark_version check --dataset lao_dong_v5
python -m labor_rag.evaluation.benchmark_version list

# chạy (cần Qdrant); kết quả: labor_rag/evaluation/results/<dataset_id>/<testset>/<run_id>/
python -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1 --validate-only
python -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1 --model bge

# phiên bản dữ liệu mới: mang bộ câu hỏi sang, câu có Điều gold đổi nội dung bị loại để chấm lại
python -m labor_rag.evaluation.benchmark_version freeze --dataset lao_dong_v6 --testset v1 --from lao_dong_v5
```

Metric: HitRate@1/5/10, Recall@5/10 (micro), MultiHit@5/10, MRR@10, nDCG@10, kèm khoảng tin cậy 95% (bootstrap).
Một Điều được tính là đúng khi có grade ≥ 2 (`--min-grade`). Kết quả được gom theo `mapc` trước khi tính điểm,
nên một Điều bị cắt thành nhiều phần chỉ tính một lần. File kết quả: `summary.csv`, `metrics.csv` (CI),
`breakdown.csv` (theo đề mục / kiểu câu / tag), `per_query_results.jsonl`, `run.json`.
Notebook `notebooks/embedding_benchmark.ipynb` đọc lần chạy mới nhất.

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

python -m labor_rag.evaluation.benchmark_version freeze --dataset lao_dong_v5 --testset v2 `
    --questions labor_rag/evaluation/benchmark_questions_v2.jsonl
python -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v2
```

## OCR văn bản người dùng tải lên

`labor_rag/ocr` nhận PDF (có text layer hoặc bản scan) hoặc ảnh chụp (jpg/png/tiff/…), trả về text đã làm sạch
và cây Phần > Chương > Mục > Điều > Khoản > Điểm. Trang có text layer đọc bằng PyMuPDF; trang scan và ảnh
đọc bằng VietOCR (`vgg_transformer`). VietOCR chỉ nhận dạng từng dòng, nên module tự tách dòng: projection
ngang, tách dải nhiều dòng dính dấu, tách cột rộng (quốc hiệu / tên cơ quan), cắt dòng dài tại khoảng trắng
giữa từ để không bị VietOCR bóp ngang (ảnh đầu vào bị giới hạn 32×512 px), thêm viền trắng quanh mỗi mảnh.

Cài đặt (một lần, sau `requirements.txt`):

```powershell
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

Chatbot mặc định dùng collection `legal_ld_v5_bge` (bge-m3) và dataset `lao_dong_v5`. Có thể đổi qua `.env`.

```powershell
python -m labor_rag.app.chat
```

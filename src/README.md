# LexGraph VN - Hệ Thống Hỏi Đáp Pháp Luật Việt Nam (Decoupled Web App)

Hệ thống Web App cho toàn bộ Pipeline Hỏi đáp Pháp luật Đa lượt & Lập chỉ mục kép (Hybrid GraphRAG v2.4 - Explainable AI), áp dụng mô hình kiến trúc tách rời **Decoupled Architecture** và mẫu thiết kế **Service-Layer Pattern**.

---

## 1. Kiến Trúc Hệ Thống (Decoupled Architecture)

```
[ Frontend: Next.js + Zustand + Tailwind CSS ]
         |
         | HTTP REST API / Server-Sent Events (SSE)
         v
[ Backend: Python FastAPI (Service-Layer Pattern) ]
  ├── Routers / Controllers (Auth, Chat, Documents, Admin)
  ├── Services (Business Logic nặng):
  │   ├── QueryRewriteService (LexRAG Context Resolution & Pronoun Resolver)
  │   ├── RetrievalService (Vector Search Qdrant + Graph Cypher Neo4j)
  │   ├── RerankService (Cross-Encoder / LLM Selection & Pruning)
  │   ├── LLMService & VerificationService (Sinh câu trả lời & Trích dẫn Điều/Khoản/Điểm)
  │   ├── IngestionService (Background Worker, OCR/Pháp điển, Chunks schema v5)
  │   └── EmbeddingService (BGE-m3, Local / Modal GPU Backend)
  └── Repositories (Data Access Layer):
      ├── PostgresRepository (Users, Chat Sessions & Messages, Documents, Ingestion Tasks)
      ├── RedisRepository (Session Cache & Embedding Cache câu hỏi thường gặp)
      ├── QdrantRepository (Cosine Vector kNN)
      └── Neo4jRepository (Graph Cypher traversal, PART_OF, REFERS_TO)
```

---

## 2. Cấu Trúc Mã Nguồn Trong `src/`

```
src/
├── backend/
│   ├── app/
│   │   ├── main.py                  # Điểm khởi chạy FastAPI, middleware, seeds
│   │   ├── config.py                # Cấu hình Pydantic settings & sys.path
│   │   ├── dependencies.py          # Dependency injection (Auth JWT, DB Session)
│   │   ├── models/
│   │   │   ├── enums.py             # RetrievalMode, TaskStatus, DocumentType
│   │   │   ├── database.py          # SQLAlchemy Models (User, ChatSession, ChatMessage, DocumentRecord, IngestionTask)
│   │   │   └── schemas.py           # Pydantic Request/Response models & Traces
│   │   ├── repositories/
│   │   │   ├── postgres.py          # PostgreSQL session & CRUD
│   │   │   ├── redis.py             # Redis Cache (Embedding + Session Context)
│   │   │   ├── qdrant.py            # Qdrant client wrapper
│   │   │   └── neo4j.py             # Neo4j driver & Cypher traversal
│   │   ├── services/
│   │   │   ├── query_rewrite.py     # Xử lý ngữ cảnh đa lượt (LexRAG Idea)
│   │   │   ├── retrieval.py         # Hybrid Retrieval (Qdrant + Neo4j)
│   │   │   ├── rerank.py            # Cross-Encoder Rerank & Pruning
│   │   │   ├── llm.py               # Sinh câu trả lời trích dẫn Điều/Khoản/Điểm
│   │   │   ├── verification.py      # Citation Verification đối soát CSDL
│   │   │   ├── embedding.py         # BGE-m3 embedding (Local / Modal GPU)
│   │   │   └── ingestion.py         # Chạy ngầm ra chunks.jsonl & tiến độ embedding
│   │   ├── routers/
│   │   │   ├── auth.py              # Đăng ký / Đăng nhập JWT
│   │   │   ├── chat.py              # Phiên hỏi đáp, gửi câu hỏi, pipeline trace
│   │   │   ├── documents.py         # Quản lý văn bản, nạp tài liệu, progress SSE
│   │   │   └── admin.py             # Cấu hình mô hình, vector db, cache flush
│   │   └── utils/
│   │       ├── auth.py              # Hash password, mã hóa/giải mã JWT
│   │       └── pagination.py        # Cursor-based pagination cho lịch sử & văn bản
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx           # Layout dùng font Inter & JetBrains Mono
│   │   │   ├── page.tsx             # Redirect đến /chat
│   │   │   ├── chat/page.tsx        # [Trang 1] Hỏi đáp Pháp luật (Chuẩn mẫu UI page1)
│   │   │   ├── documents/page.tsx   # [Trang 2] Kho Văn bản & Quản lý Chỉ mục (Chuẩn mẫu UI page2)
│   │   │   └── admin/page.tsx       # [Trang 3] Quản trị cấu hình hệ thống
│   │   ├── components/
│   │   │   ├── layout/Header.tsx    # Header bar chuẩn theme #0F172A
│   │   │   ├── chat/                # SessionList, ChatMessage, PipelineTrace, CitationChip, ChatInput
│   │   │   ├── inspector/           # HierarchyTree (Cây phân cấp), GraphView (Đồ thị Neo4j), EvidencePanel
│   │   │   └── documents/           # StatsCards, DocumentTable, UploadModal, IngestionProgress
│   │   ├── stores/                  # Zustand (authStore, chatStore, documentStore)
│   │   ├── lib/                     # Axios API client, TypeScript Types
│   │   └── styles/                  # Tailwind CSS & Global styles
│   ├── package.json
│   ├── tailwind.config.ts           # Token màu sắc và font từ DESIGN.md
│   └── Dockerfile
└── docker-compose.yml               # Khởi chạy full 6 dịch vụ
```

---

## 3. Các Tính Năng Nổi Bật Đã Cài Đặt

1. **Hỏi đáp Đa lượt (Multi-turn RAG) & Giải quyết đại từ**:
   - Tự động viết lại câu hỏi phụ thuộc ("Trường hợp đó thì...", "vậy nếu...") thành câu hỏi độc lập (Standalone Query).
   - Hiển thị toàn bộ tiến trình giải thích **Explainable Pipeline Trace** với 4 bước trực quan.
2. **Interactive Citation Chips**:
   - Các trích dẫn Điều/Khoản/Điểm trong câu trả lời có thể nhấp chuột trực tiếp để tự động kích hoạt Cột Thanh tra Pháp lý bên phải, hiển thị cây phân cấp và liên kết đồ thị `REFERS_TO`.
3. **Nạp Tài Liệu Ngầm & Thanh Tiến Độ Riêng (Progress Bar)**:
   - Khi nạp tài liệu PDF hoặc Pháp điển HTML, hệ thống tự động chạy background thread để phân tích cấu trúc, trích xuất Điều/Khoản/Điểm và sinh ra `chunks.jsonl` theo chuẩn schema v5.
   - Quá trình tính toán embedding có thanh tiến độ thời gian thực (hiển thị % và số chunk đã embed: `X / Total chunks`).
4. **Trang Quản trị Admin**:
   - Cho phép lựa chọn mô hình embedding (`BAAI/bge-m3` hoặc mô hình Fine-tuned Tiếng Việt).
   - Chọn nguồn tính toán embedding: Máy cục bộ (Local) hoặc GPU Đám mây (Modal GPU).
   - Quản lý Vector DB, Neo4j và Flush Redis Cache một chạm.
5. **Cursor-based Pagination**:
   - Đảm bảo hiệu năng tải danh mục văn bản và lịch sử phiên hỏi đáp lớn mà không bị chậm.

---

## 4. Hướng Dẫn Cài Đặt & Khởi Chạy

### Cách 1: Khởi chạy nhanh bằng Docker Compose (Khuyên dùng)
Tại thư mục gốc dự án:
```bash
docker-compose -f src/docker-compose.yml up --build -d
```
- Frontend: `http://localhost:3000`
- Backend API Docs (Swagger): `http://localhost:8000/docs`
- Qdrant Dashboard: `http://localhost:6333/dashboard`
- Neo4j Browser: `http://localhost:7474` (Tài khoản: `neo4j` / `labor_rag_pw`)

---

### Cách 2: Khởi chạy từng thành phần cục bộ

#### Bước 1: Khởi chạy cơ sở dữ liệu nền tảng
Chạy Qdrant và Neo4j sẵn có trong dự án:
```bash
docker-compose up -d neo4j qdrant
```

#### Bước 2: Chạy Backend FastAPI
```bash
# Cài đặt thư viện
pip install -r src/backend/requirements.txt

# Khởi chạy backend (tự động tạo bảng SQLite/Postgres và dữ liệu mẫu)
python -m uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Bước 3: Chạy Frontend Next.js
Mở một terminal mới:
```bash
cd src/frontend
npm install
npm run dev
```
Truy cập giao diện tại: `http://localhost:3000`


# HƯỚNG DẪN KHỞI CHẠY HỆ THỐNG LEXGRAPH VN

Tài liệu hướng dẫn chi tiết 2 cách khởi chạy hệ thống Web App Hỏi đáp Pháp luật Đa lượt & Lập chỉ mục kép (Decoupled Architecture: FastAPI Backend + Next.js Frontend).

---

## Yêu cầu Hệ thống Tiên quyết
- **Python**: `>= 3.10` (Khuyên dùng Python 3.11 hoặc 3.12/3.13)
- **Node.js**: `>= 18.x` và **npm**
- **Docker & Docker Compose** (Bắt buộc nếu chọn Cách 1, hoặc dùng để chạy Neo4j/Qdrant ở Cách 2)

---

## CÁCH 1: KHỞI CHẠY TOÀN BỘ BẰNG DOCKER COMPOSE (Khuyên dùng)

Cách này sẽ tự động khởi chạy và liên kết toàn bộ 6 dịch vụ trong container:
1. **PostgreSQL 15** (Cơ sở dữ liệu người dùng, phiên hỏi đáp, văn bản số hóa)
2. **Redis 7** (Session Cache & Vector Embedding Cache)
3. **Qdrant** (Vector Database - BGE-m3 Cosine Index)
4. **Neo4j 5 Community** (Knowledge Graph - Quan hệ `PART_OF`, `REFERS_TO`)
5. **Backend FastAPI** (Cổng 8000)
6. **Frontend Next.js** (Cổng 3000)

### Các bước thực hiện:

1. Mở PowerShell hoặc Terminal tại thư mục gốc dự án (`d:\PBL6_v2\PBL6`):
   ```powershell
   docker-compose -f src/docker-compose.yml up --build -d
   ```

2. Kiểm tra trạng thái các container đang chạy:
   ```powershell
   docker ps
   ```

3. Dừng hệ thống khi không sử dụng:
   ```powershell
   docker-compose -f src/docker-compose.yml down
   ```

---

## CÁCH 2: KHỞI CHẠY THỦ CÔNG TỪNG THÀNH PHẦN (Local Development)

Phương pháp này phù hợp cho việc phát triển, chỉnh sửa mã nguồn và debug trực tiếp trên máy.

### Bước 1: Khởi chạy cơ sở dữ liệu nền tảng (Qdrant & Neo4j)
Chạy 2 dịch vụ Vector DB và Knowledge Graph có sẵn trong dự án:
```powershell
docker-compose up -d neo4j qdrant
```

---

### Bước 2: Thiết lập và Khởi chạy Backend FastAPI

1. **(Khuyên dùng) Tạo và kích hoạt môi trường ảo Python:**
   ```powershell
   # Tạo môi trường ảo
   python -m venv venv

   # Kích hoạt môi trường ảo trên Windows (PowerShell)
   .\venv\Scripts\Activate.ps1
   ```
   > *Lưu ý nếu PowerShell báo lỗi chặn script:* Chạy lệnh `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` rồi kích hoạt lại.

2. **Cài đặt các thư viện cần thiết:**
   ```powershell
   pip install --upgrade pip
   pip install -r src\backend\requirements.txt
   ```

   > **Cơ chế Fallback thông minh:** Backend đã được tích hợp sẵn cơ chế tự động chuyển sang cơ sở dữ liệu **SQLite** cục bộ (`data/interim/lexgraph.db`) và **In-Memory Cache** nếu máy bạn chưa cài đặt PostgreSQL hoặc Redis cục bộ. Do đó, Backend luôn khởi động thành công ngay lập tức!

3. **Khởi chạy Backend Server:**
   ```powershell
   python -m uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   - Server backend sẽ hoạt động tại: `http://localhost:8000`
   - Tài liệu API (Swagger UI): `http://localhost:8000/docs`

---

### Bước 3: Thiết lập và Khởi chạy Frontend Next.js

Mở một cửa sổ Terminal/PowerShell **mới**:

1. **Di chuyển vào thư mục Frontend:**
   ```powershell
   cd src/frontend
   ```

2. **Cài đặt các gói npm phụ thuộc:**
   ```powershell
   npm install
   ```

3. **Khởi chạy môi trường phát triển (Dev Server):**
   ```powershell
   npm run dev
   ```

4. **Truy cập ứng dụng:**
   Mở trình duyệt web và truy cập vào:
   👉 **`http://localhost:3000`**

## CÁCH 3: CHẠY HOÀN TOÀN KHÔNG CẦN DOCKER (ZERO-DOCKER / STANDALONE MODE)

Nếu máy tính của bạn **chưa cài Docker** hoặc **không muốn bật Docker**, hệ thống đã được lập trình sẵn các cơ chế **Tự động Fallback thông minh 100%**:
1. **Cơ sở dữ liệu (PostgreSQL)**: Tự động chuyển sang **SQLite** cục bộ lưu tại `data/interim/lexgraph.db`.
2. **Bộ nhớ Cache (Redis)**: Tự động chuyển sang **In-Memory Cache** trong tiến trình Python.
3. **Cơ sở dữ liệu Vector & Graph (Qdrant & Neo4j)**: 
   - **Tùy chọn A (Cloud Miễn phí)**: Dùng **Qdrant Cloud Free Tier** (1GB cluster miễn phí) và **Neo4j AuraDB Free Tier** (miễn phí), điền URI vào file `.env` hoặc cấu hình qua trang `http://localhost:3000/admin`.
   - **Tùy chọn B (Tự động quét kho dữ liệu số hóa có sẵn)**: Khi chưa kết nối Qdrant/Neo4j, dịch vụ `RetrievalService` tự động đọc dữ liệu từ kho `data/processed/lao_dong_v5_full/chunks.jsonl` có sẵn trong mã nguồn để phục vụ hỏi đáp và hiển thị đầy đủ Pipeline Trace mà không hề bị lỗi!

### Các bước chạy Zero-Docker:

> **Lưu ý quan trọng về thư mục:** Hãy đảm bảo terminal đang đứng ở thư mục gốc của dự án (`D:\PBL6_v2\PBL6`). Nếu đang đứng ở thư mục con `src/`, hãy gõ `cd ..` để lùi ra ngoài.

1. **Terminal 1 - Khởi chạy Backend:**
   - Cách 1 (Từ thư mục gốc `D:\PBL6_v2\PBL6`):
     ```powershell
     python -m uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8000 --reload
     ```
   - Cách 2 (Dễ nhất - chạy được ở cả thư mục gốc hoặc thư mục `src/`):
     ```powershell
     python run_backend.py
     ```

2. **Terminal 2 - Khởi chạy Frontend:**
   ```powershell
   cd src/frontend
   npm run dev
   ```

3. Mở trình duyệt tại **`http://localhost:3000`** và sử dụng ngay lập tức!

---

## 3. DANH SÁCH ĐƯỜNG DẪN TRUY CẬP (ENDPOINTS & DASHBOARDS)

| Dịch vụ / Màn hình | Địa chỉ truy cập | Ghi chú |
| :--- | :--- | :--- |
| **Giao diện Hỏi đáp (Trang 1)** | `http://localhost:3000/chat` | Tra cứu đa lượt, Explainable Pipeline Trace, Citation Chips |
| **Kho Văn bản & Nạp tài liệu (Trang 2)** | `http://localhost:3000/documents` | Nạp file PDF/HTML, xem thanh tiến độ embedding thời gian thực |
| **Cấu hình Quản trị (Trang 3)** | `http://localhost:3000/admin` | Chọn mô hình BGE-m3, Modal GPU backend, Flush Redis Cache |
| **Backend API Swagger UI** | `http://localhost:8000/docs` | Thử nghiệm trực tiếp toàn bộ 21 REST API endpoints |
| **Backend Health Check** | `http://localhost:8000/health` | Kiểm tra tình trạng kết nối API |
| **Qdrant Vector Dashboard** | `http://localhost:6333/dashboard` | Trực quan hóa vector collections và điểm tương đồng |
| **Neo4j Browser UI** | `http://localhost:7474` | User: `neo4j` / Password: `labor_rag_pw` |

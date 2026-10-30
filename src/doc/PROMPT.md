## PROMPT for AI
Hãy tạo cho tôi 1 web app cho hệ thống của tôi cho toàn pipeline hệ thống hỏi đáp luật pháp . Toàn bộ source code sẽ được lưu ở src/ .  
1. Kiến trúc hệ thống 
- Áp dụng mô hình Decoupled Architecture (Kiến trúc tách rời Frontend - Backend) kết hợp Service-Layer Pattern ở Backend
- Frontend : Next.js (React) + Zustand (State Management) + Tailwind CSS.
- Backend : Python (FastAPI)
- Tổ chức mã nguồn (Khuyên dùng mô hình Modular / Service-Repository):
Routers / Controllers (API Endpoints): Chỉ chịu trách nhiệm tiếp nhận request HTTP/WebSocket, xác thực dữ liệu đầu vào (Pydantic models) và trả về response.
Services (Business Logic): Nơi đặt toàn bộ logic nặng của pipeline:
QueryRewriteService: Xử lýữ cảnh hội thoại (LexRAG idea).
RetrievalService: Gọi đồng thời Vector Retrieval (Qdrant) và Graph Retrieval (Neo4j Cypher).
RerankService: Chạy mô hình Cross-Encoder để lọc và sắp xếp tài liệu.
LLMService & VerificationService: Gọi LLM sinh câu trả lời và kiểm chứng trích dẫn (Citation Verification).
Repositories / Data Access Layer: Các module chuyên biệt để kết nối Qdrant, Neo4j, PostgreSQL.
- Database : vector db : qdrant , graph database ( neo4j ) , relationship db : postgresdb ( Lưu trữ thông tin người dùng (Users), lịch sử hội thoại đa lượt (Chat Sessions & Messages) và cấu hình hệ thống )
- Cache Embedding: Lưu cache vector embedding của các câu hỏi thường gặp.
Session Cache (Redis): Quản lý trạng thái hội thoại đa lượt (Multi-turn Conversation Context) để phục vụ bước Query Rewrite.
- Auth : JWT
- Query : 
Query Rewrite / Standalone Query: Chuyển đổi câu hỏi phụ thuộc ngữ cảnh đa lượt thành câu hỏi độc lập.
Database Query:
Truy vấn vector khoảng cách cosine trên Qdrant (Vector Retrieval).
Truy vấn Cypher trên Neo4j để duyệt các nút quan hệ luật (Graph Retrieval).
- Search
- Pagination : Cursor . Dùng cho trang quản lý văn bản luật và lịch sử chat ở Frontend.

2 . Các lưu ý 
- Trang web sẽ gồm 2 trang : trang hỏi đáp và trang nạp tài liệu , dùng đúng mẫu thiết kế trong src\UI . Ở trang nạp tài liệu thì 1 số tính năng có thể bỏ 
- Sau khi nạp tài liệu xong thì tùy vào loại tài liệu mà xử lý pdf hay pháp điển như cách code hiện tại xử lý trong PBL6/ 
- Khi nạp tài liệu mới vào nó phải tự chạy ngầm các quy trình để ra chunks.jsonl như trong code đang dùng hiện tại và embedding phải có thanh tiến độ cho riêng file mới nạp vào đây . 
- Embedding thì hiện tại cứ dùng BGE-m3 trước khi fine tuning .
- Có 1 trang cho admin để cấu hình mô hình embedding  , chọn vector db ( hiện tại mặc định qdrant như đã cấu hình trong code ) , nguồn chạy modal embedding ( hiện tại dùng Modal ) ,...
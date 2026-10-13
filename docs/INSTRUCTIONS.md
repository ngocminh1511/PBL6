### Chạy requirements
pip install -r requirements.txt

### Thêm OCR cho PDF
Khi ở trong 1 footnotes quét trúng con số thì để con số đấy thành *n*

Footnotes trang 25,26,52,58 Luật lao động


### Chuỗi Pipeline từ HTML Pháp điển

    A["data/raw/bophapdien/*.html"] --> B["parse_demuc_html.py"]
    B --> C["build_abox.py"]
    C --> D["ontology/abox/abox_lao_dong.ttl"]
    D --> E["ontology_to_jsonl.py"]
    F["chunk_schema.py"] -. hàm dựng header & cắt điều .-> E
    E --> G["data/processed/lao_dong_v5/chunks.jsonl"]


### Khi hỏi 1 câu bằng Terminal 
Khi hỏi 1 câu terminal , quá trình truy xuất của nó như sau 

1. Model AI: BAAI/bge-m3 (Embedding Model)
Thư viện Python: sentence-transformers, torch.
Vai trò: Bạn hỏi bằng tiếng Việt bình thường, model này sẽ "hiểu ý nghĩa" và biến câu hỏi thành một dãy số (vector 1.024 chiều).
2. Vector Database: Qdrant (Tìm kiếm ngữ nghĩa)
Thư viện Python: qdrant-client.
Vai trò: Qdrant lưu trữ vector của 1.482 điều luật. Nó nhận vector câu hỏi của bạn và dùng thuật toán tìm kiếm vector (Cosine Similarity) để chọn ra các điều luật có ý nghĩa gần với câu hỏi nhất.
3. Graph Database: Neo4j (Tìm kiếm theo đồ thị quan hệ)
Thư viện Python: neo4j.
Vai trò: Khi Qdrant tìm được các điều luật ban đầu (seeds), Neo4j sẽ chạy câu truy vấn Cypher:
cypher
MATCH (a:Dieu)-[:REFERS_TO]->(b:Dieu)
để tìm tiếp các điều luật mà điều này trích dẫn hoặc có liên quan mật thiết (Graph expansion).

### chạy pipeline từ html sang chunks.jsonl
- TH1 : (Tối giản - Điều n. Tên + nội dung)
python -m labor_rag.ingest.ontology_to_jsonl --text-variant minimal --out-dir data/processed/lao_dong_variant_th1

- TH2 : (Đầy đủ ngữ cảnh)
python -m labor_rag.ingest.ontology_to_jsonl --text-variant full --out-dir data/processed/lao_dong_variant_th2


### báo cáo
- Qdrant là một Hệ quản trị cơ sở dữ liệu Vector (Vector Database) : 
+ Lưu trữ (Storage): Thay vì mỗi lần khởi động ứng dụng lại phải chạy lại mô hình để nhúng (embed) toàn bộ hàng nghìn tài liệu hành chính, bạn chỉ cần nhúng 1 lần rồi lưu vĩnh viễn các vector vào Qdrant.

+ Tìm kiếm ngữ nghĩa siêu tốc (Similarity Search): Khi người dùng đặt câu hỏi, bạn dùng bge-m3 biến câu hỏi đó thành 1 vector, rồi mang vào Qdrant để quét qua hàng triệu vector khác. Qdrant sẽ trả về các đoạn tài liệu có "khoảng cách vector" gần nhất (nghĩa là nội dung liên quan nhất) chỉ trong vài phần nghìn giây.

+ Khai thác Hybrid Search (Điểm mạnh nhất khi kết hợp với BGE-M3): Mô hình BGE-M3 tạo ra cả Dense vector (hiểu ngữ nghĩa sâu sắc) và Sparse vector (bắt từ khóa chính xác như Elasticsearch). Qdrant hỗ trợ lưu và tìm kiếm kết hợp cả 2 loại vector này cùng lúc, mang lại kết quả cực kỳ chuẩn xác.

+ Lọc theo siêu dữ liệu (Metadata Filtering): Khi lưu vector vào Qdrant, bạn có thể đính kèm thông tin (ví dụ: loai_van_ban: "nghi_dinh", ngay_ban_hanh: "2024"). Lúc truy vấn, bạn có thể yêu cầu Qdrant: "Tìm các đoạn văn bản có nghĩa giống câu hỏi này, nhưng chỉ lấy trong các nghị định năm 2024".

### chạy modal cho cả 2 modal 
- modal deploy scripts/modal_embed.py
- python scripts/auto_chain_embeddings.py --backend modal

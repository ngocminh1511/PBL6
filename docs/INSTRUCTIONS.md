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
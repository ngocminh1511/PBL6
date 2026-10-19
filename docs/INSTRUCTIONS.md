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

### Chạy benchmark cho 2 biến thể (Chỉ Vector Database)
python scripts/benchmark_retrieval_th1_vs_th2.py

### Chạy benchmark kết hợp Vector Database + Knowledge Graph (Hybrid RAG)
python scripts/benchmark_retrieval_with_graph.py

### Giải thích 1 số định nghĩa 
- Hit@1, Hit@5, Hit@10 (Tỷ lệ trúng đích): Đo lường xem tài liệu chính xác có xuất hiện trong top K kết quả trả về hay không. Chỉ cần có xuất hiện là được tính điểm, không phân biệt vị trí cụ thể bên trong top đó.

Hit@1 (83.3%): Trong 100 câu hỏi, có khoảng 83 câu mà hệ thống lấy được tài liệu đúng ngay ở vị trí đầu tiên. Đây là chỉ số khắt khe nhất.

Hit@5 và Hit@10 (93.3% - 96.7%): Nếu tìm rộng ra 5 hoặc 10 kết quả, tỷ lệ "trúng" lên tới 96.7%. Trong hệ thống RAG, nếu bạn định cắt 5 chunk đưa vào prompt cho mô hình ngôn ngữ đọc, chỉ số Hit@5 ở mức 93.3% là rất an toàn.

- Recall@5, Recall@10 (Tỷ lệ thu hồi): Đo lường mức độ "gom đủ" dữ liệu. Trong toàn bộ các đoạn tài liệu có liên quan đến câu hỏi đang nằm rải rác trong cơ sở dữ liệu, hệ thống lấy ra được bao nhiêu phần trăm khi quét top 5 hoặc top 10.

Ví dụ: Một truy vấn về một điều luật có tổng cộng 4 đoạn (chunks) liên quan nằm trong cơ sở dữ liệu. Nếu top 5 kết quả tìm kiếm chỉ chứa 2 đoạn trong số đó, thì Recall@5 của câu hỏi đó là 2/4 = 50%.

Chỉ số này ở mức 60-69% cho thấy hệ thống tìm được tài liệu đúng (Hit cao) nhưng có thể bị bỏ sót một số tài liệu phụ trợ khác cùng chủ đề.

- MRR@10 (Mean Reciprocal Rank - Điểm xếp hạng nghịch đảo trung bình): Đo lường việc kết quả đúng xuất hiện "sớm" hay "muộn" trên bảng xếp hạng.

Điểm được tính bằng nghịch đảo thứ hạng của kết quả đúng đầu tiên: 1 / thứ_hạng.

Nếu tài liệu đúng nằm ở Top 1 -> Điểm là 1.

Nếu nằm ở Top 3 -> Điểm là 1/3 (0.33).

Nếu nằm ở Top 10 -> Điểm là 1/10 (0.1).

Mức điểm 0.8833 cho thấy trung bình các tài liệu đúng luôn xuất hiện ở vị trí thứ 1 hoặc thứ 2.


# báo cáo
labor_rag\evaluation\results\retrieval_v3_hybrid_pipeline_report.md
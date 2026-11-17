# Báo Cáo Benchmark Chi Tiết: Vector Database vs Vector DB + Knowledge Graph

## 1. Thiết lập Thực nghiệm & Giải thích Kiến trúc
- **Tập dữ liệu**: [labor_rag/evaluation/benchmark_questions_v3.jsonl](file:///D:/PBL6_v2/PBL6/labor_rag/evaluation/benchmark_questions_v3.jsonl) (201 câu hỏi, trong đó có 133 câu hỏi dẫn chiếu đa điều luật).
- **Vector Database**: Qdrant Cloud (`legal_ld_v7_bge`).
- **Knowledge Graph**: Neo4j AuraDB (`Database: e97dd8f7`).
- **Các Phương án Đánh giá**:
  1. **TH1: Vector Database Only**: Tìm kiếm thuần ngữ nghĩa trên Qdrant Cloud với mô hình `BAAI/bge-m3`.
  2. **TH2-A: Pipeline chuẩn hệ thống (Top-5 Vector Seeds + Nối đuôi Graph)**: 5 vị trí đầu dành trọn vẹn cho hạt giống vector; các điều luật mở rộng từ Knowledge Graph (`REFERS_TO` & `CITES_COMPONENT`) được nối tiếp từ vị trí số 6 đến 10.
  3. **TH2-B: Pipeline tối ưu liên kết (Coupled Ranking Reranked)**: Các điều luật trích dẫn trực tiếp từ hạt giống vector được gán điểm tương quan (`score = seed * 0.92`), cho phép điều luật dẫn chiếu có thể thâm nhập ngay vào Top 3 - Top 5 nếu mức độ tương quan vượt qua các điều luật phụ.

---

## 2. Bảng Kết quả Tổng thể trên Toàn bộ 201 Câu hỏi

| Chỉ số Đánh giá | TH1: Vector DB Only | TH2-A: Pipeline chuẩn (Seeds Top 5) | Chênh lệch (TH2-A vs TH1) | TH2-B: Pipeline tối ưu (Coupled Rerank) | Chênh lệch (TH2-B vs TH1) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Hit@1** | 79.10% | 79.10% | 0.00% | 79.10% | 0.00% |
| **Hit@5** | 95.52% | 95.52% | 0.00% | 95.52% | 0.00% |
| **Hit@8** | 97.01% | 96.02% | **-0.99%** | 97.01% | 0.00% |
| **Hit@10** | 98.01% | 96.02% | **-1.99%** | 98.01% | 0.00% |
| **Recall@5** | 60.45% | 60.45% | 0.00% | **71.38%** | ****+10.93%**** |
| **Recall@8** | 66.49% | **82.91%** | ****+16.42%**** | **81.06%** | ****+14.57%**** |
| **Recall@10** | 68.45% | **86.59%** | ****+18.14%**** | **84.28%** | ****+15.83%**** |
| **MRR@10** | 0.8552 | 0.8527 | -0.0025 | 0.8552 | +0.0000 |
| **NDCG@8** | 0.7588 | 0.8132 | +0.0544 | **0.8260** | **+0.0672** |
| **NDCG@10** | 0.7639 | 0.8423 | +0.0784 | **0.8484** | **+0.0845** |

---

## 3. Bảng Kết quả trên Phân nhóm Dẫn chiếu Đa Điều Luật / Cross-Reference (133 câu)

| Chỉ số Đánh giá | TH1: Vector DB Only | TH2-A: Pipeline chuẩn (Seeds Top 5) | Chênh lệch (TH2-A vs TH1) | TH2-B: Pipeline tối ưu (Coupled Rerank) | Chênh lệch (TH2-B vs TH1) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Recall@5** | 45.87% | 45.87% | 0.00% | **62.39%** | ****+16.52%**** 🚀 |
| **Recall@8** | 53.25% | **79.82%** | ****+26.57%**** 🚀 | **75.27%** | ****+22.02%**** 🚀 |
| **Recall@10** | 55.96% | **85.37%** | ****+29.41%**** 🚀 | **79.87%** | ****+23.91%**** 🚀 |
| **NDCG@8** | 0.7170 | 0.8048 | +0.0878 | **0.8185** | **+0.1015** |
| **NDCG@10** | 0.7231 | 0.8489 | +0.1258 | **0.8508** | **+0.1277** |

---

## 4. Giải đáp Trực tiếp Câu hỏi của Bạn
1. **Tại sao ở TH2-A, chỉ số Recall@5 không hề thay đổi (0.00%)?**
   - Trong hàm `retrieve(query, top_k=5)` của `hybrid_retrieve.py`, mã nguồn thực hiện: `vector_hits = self.vector_search(query, top_k=5)` sau đó gán `merged = list(vector_hits)` và nối tiếp các kết quả đồ thị vào sau mảng `merged`.
   - Điều này đồng nghĩa với việc: **5 vị trí đầu tiên của `merged` (Top 5) hoàn toàn là 5 kết quả tìm kiếm vector gốc**. Các điều luật mở rộng từ đồ thị tri thức chỉ bắt đầu xuất hiện từ vị trí thứ 6 trở đi (Rank 6, 7, 8, 9, 10).
   - Do đó, khi đo Recall@5 (chỉ lấy 5 phần tử đầu), mảng kết quả của TH2-A hoàn toàn trùng khớp 100% với TH1, dẫn tới mức chênh lệch tuyệt đối bằng đúng `0.00%`.
2. **Tại sao ở Recall@8 và Recall@10, TH2 lại tăng vọt?**
   - Nhìn vào mốc **Top 8**, các điều luật mở rộng từ đồ thị đã được nạp vào các vị trí 6, 7, 8. Nhờ vậy, **Recall@8 của TH2-A tăng vọt từ 66.49% lên 82.91% (+16.42%)** trên toàn bộ tập dữ liệu, và tăng từ **53.25% lên 79.82% (+26.57%)** trên nhóm câu hỏi dẫn chiếu!
   - Sang mốc **Top 10**, **Recall@10 đạt tới 86.59% (+18.14%)** tổng thể và **85.37% (+29.41%)** trên nhóm dẫn chiếu!
3. **Giải pháp nếu muốn đồ thị phát huy ngay từ Top 5 (TH2-B)?**
   - Nếu áp dụng **Coupled Reranking** (gán điểm liên kết cho các điều luật được trích dẫn trực tiếp bởi top hạt giống: `score = seed * 0.92`), các điều luật dẫn chiếu quan trọng sẽ được đẩy lên chiếm ngay các vị trí Top 3, 4, 5 thay vì bị ép xuống sau vị trí 5.
   - Khi đó, **Recall@5 của nhóm dẫn chiếu lập tức tăng vọt từ 45.87% lên 62.39% (+16.52%)**, đồng thời Recall@8 đạt **75.27%** và Recall@10 đạt **79.87%**!
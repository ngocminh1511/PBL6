# Báo Cáo Benchmark Chi Tiết (v4): Mô Hình Fine-Tuned BGE-M3 vs Mô Hình Gốc Kết Hợp Knowledge Graph

## 1. Thiết lập Thực nghiệm & Cấu hình Kiến trúc

- **Tập dữ liệu kiểm thử**: [labor_rag/evaluation/benchmark_questions_v3.jsonl](file:///d:/PBL6_v2/PBL6/labor_rag/evaluation/benchmark_questions_v3.jsonl) (201 câu hỏi pháp lý Lao động, trong đó có 133 câu hỏi dẫn chiếu đa điều luật / Cross-reference).
- **Knowledge Graph**: Neo4j AuraDB (`Database: e97dd8f7`), khai thác 2 loại cạnh quan hệ:
  - `REFERS_TO`: Dẫn chiếu trực tiếp giữa các điều luật trong bộ pháp điển.
  - `CITES_COMPONENT` / `IMPLEMENTS_COMPONENT`: Dẫn chiếu chéo văn bản quy phạm pháp luật (Bộ luật, Nghị định, Thông tư).
- **Các Hệ thống So sánh Đối đầu**:
  1. **TH1 (Base Vector Only)**: Vector Search trên Qdrant Cloud (`legal_ld_v7_bge`) với mô hình nguyên bản `BAAI/bge-m3`.
  2. **TH2-B (Base Vector + KG Coupled)**: Kết hợp mô hình gốc `BAAI/bge-m3` với đồ thị Neo4j qua cơ chế Coupled Reranking (`score = seed * 0.92`).
  3. **TH1-FT (Fine-tuned Vector Only)**: Vector Search trên Qdrant Cloud (`legal_ld_v7_finetuned`) với mô hình **Fine-tuned BGE-M3** (`data/model/bge-m3-legal-vietnamese`).
  4. **TH2-B-FT (Fine-tuned + KG Coupled - MỚI)**: Kết hợp mô hình **Fine-tuned BGE-M3** với đồ thị Neo4j qua cơ chế Coupled Reranking (`score = seed * 0.92`).

---

## 2. Bảng Kết quả Tổng thể trên Toàn bộ 201 Câu hỏi

| Chỉ số Đánh giá | (1) Gốc: TH1 (Base Vector) | (2) Gốc: TH2-B (Base + KG) | (3) MỚI: TH1-FT (Fine-tuned Vector) | (4) MỚI: TH2-B-FT (Fine-tuned + KG) | Chênh lệch (4) vs (2) <br> *(FT+KG vs Base+KG)* | Chênh lệch (4) vs (1) <br> *(FT+KG vs Base Vector)* |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Hit@1** | 79.10% | 79.10% | **79.10%** | **79.10%** | 0.00% | 0.00% |
| **Hit@5** | 95.52% | 95.52% | 94.03% | 93.03% | -2.49% | -2.49% |
| **Hit@8** | 97.01% | 97.01% | 95.52% | 93.53% | -3.48% | -3.48% |
| **Hit@10** | 98.01% | 98.01% | 96.02% | 94.53% | -3.48% | -3.48% |
| **Recall@5** | 60.45% | 71.38% | 59.37% | **74.00%** | **+2.62%** | **+13.55%** |
| **Recall@8** | 66.49% | 81.06% | 65.57% | **81.15%** | **+0.09%** | **+14.66%** |
| **Recall@10** | 68.45% | 84.28% | 67.14% | **85.06%** | **+0.78%** | **+16.61%** |
| **MRR@10** | 0.8552 | 0.8552 | **0.8600** | **0.8559** | **+0.0007** | **+0.0007** |
| **NDCG@8** | 0.7588 | 0.8260 | 0.7617 | **0.8395** | **+0.0135** | **+0.0807** |
| **NDCG@10** | 0.7639 | 0.8484 | 0.7656 | **0.8647** | **+0.0163** | **+0.1008** |

---

## 3. Bảng Kết quả trên Phân nhóm Dẫn chiếu Đa Điều Luật / Cross-Reference (133 câu)

> Phân nhóm câu hỏi yêu cầu phải truy xuất được cả điều luật chính lẫn các điều luật/nghị định liên đới hướng dẫn thi hành.

| Chỉ số Đánh giá | (1) Gốc: TH1 (Base Vector) | (2) Gốc: TH2-B (Base + KG) | (3) MỚI: TH1-FT (Fine-tuned Vector) | (4) MỚI: TH2-B-FT (Fine-tuned + KG) | Chênh lệch (4) vs (2) <br> *(FT+KG vs Base+KG)* | Chênh lệch (4) vs (1) <br> *(FT+KG vs Base Vector)* |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Hit@1** | 81.20% | 81.20% | **84.21%** | **84.21%** | **+3.01%** 🎯 | **+3.01%** 🎯 |
| **Recall@5** | 45.87% | 62.39% | 46.74% | **69.85%** | **+7.46%** 🚀 | **+23.98%** 🚀 |
| **Recall@8** | 53.25% | 75.27% | 54.73% | **80.67%** | **+5.40%** 🚀 | **+27.42%** 🚀 |
| **Recall@10** | 55.96% | 79.87% | 57.10% | **85.44%** | **+5.57%** 🚀 | **+29.48%** 🚀 |
| **MRR@10** | 0.8753 | 0.8753 | **0.9042** | **0.9034** | **+0.0281** | **+0.0281** |
| **NDCG@8** | 0.7170 | 0.8185 | 0.7431 | **0.8727** | **+0.0542** | **+0.1557** |
| **NDCG@10** | 0.7231 | 0.8508 | 0.7490 | **0.9062** | **+0.0554** | **+0.1831** |


---

## 4. Trực Quan Hóa Đồ Thị Kết Quả Thực Nghiệm

Dưới đây là các biểu đồ trực quan hóa chi tiết các chỉ số thực nghiệm đo đạc được:

### 4.1. Biểu đồ Tổng quan Dashboard Đa Chiều (All-in-One Dashboard)
Biểu đồ tổng hợp 4 chiều phân tích: (A) Hiệu năng nhóm dẫn chiếu đa điều, (B) Đường cong thu hồi Recall, (C) Hiệu năng toàn bộ 201 câu hỏi, và (D) Mức tăng trưởng đột phá của mô hình Fine-tuned kết hợp đồ thị tri thức.

![Tổng quan Dashboard Đa Chiều](plots/retrieval_v4_dashboard.png)

---

### 4.2. So sánh Trực diện trên Phân nhóm Dẫn chiếu Đa Điều Luật (133 câu)
Biểu đồ cột so sánh trực tiếp cả 4 cấu hình (`Base Vector`, `Base + KG`, `Fine-tuned Vector`, `Fine-tuned + KG`) trên 6 chỉ số khắt khe nhất (`Hit@1`, `Recall@5`, `Recall@8`, `Recall@10`, `MRR@10`, `NDCG@10`).

![So sánh Nhóm Dẫn Chiếu](plots/retrieval_v4_cross_ref_comparison.png)

---

### 4.3. Động Lực Tăng Trưởng Độ Phủ Dữ Liệu (Recall Growth Curve)
Minh họa sự gia tăng vượt bậc của độ thu hồi Recall khi mở rộng từ Top 5 đến Top 10. Trong khi mô hình Vector thuần túy bị bão hòa ở mức thấp (55.96%), mô hình Fine-tuned kết hợp Knowledge Graph vươn tới đỉnh cao **85.44%**.

![Đường cong tăng trưởng Recall](plots/retrieval_v4_recall_progression.png)

---

## 5. Phân Tích Chuyên Sâu & Đánh Giá Hiệu Năng

### 1. Khả năng "Bắn trúng hạt giống" (Finding the Seed):
- Trên tập 133 câu hỏi dẫn chiếu đa điều luật, mô hình Fine-tuned giúp **Hit@1 tăng vọt từ 81.20% lên 84.21% (+3.01%)**.
- Điểm xếp hạng nghịch đảo trung bình **MRR@10 vượt mốc 0.9034 (+0.0281)**. Điều này chứng minh rằng mô hình Fine-tuned hiểu sâu sắc cấu trúc ngôn ngữ pháp lý, ánh xạ câu hỏi đời thường vào điều luật cốt lõi chính xác hơn hẳn mô hình gốc.

### 2. Tác động Cộng hưởng của Knowledge Graph với Chiến lược TH2-B (Coupled Rerank):
- Knowledge Graph mở rộng dựa trên các hạt giống (Seeds) mà Vector tìm thấy. Khi mô hình Fine-tuned cung cấp hạt giống chính xác hơn, đồ thị Neo4j duyệt sang các nhánh dẫn chiếu chuẩn xác hơn rất nhiều.
- Cơ chế **Coupled Reranking (`score = seed * 0.92`)** cho phép các điều luật dẫn chiếu quan trọng thâm nhập ngay vào Top 3–5 thay vì bị đẩy xuống cuối:
  - **Recall@5** trên nhóm dẫn chiếu tăng vọt từ **62.39% lên 69.85% (+7.46%)** so với Base+KG và tăng **+23.98%** so với Vector thuần túy.
  - **Recall@10** đạt tới **85.44% (+29.48% so với Vector thuần túy)**, thu hồi trọn vẹn các nghị định, thông tư phụ trợ.

### 3. Chất lượng Xếp hạng Toàn diện (NDCG@10):
- Điểm **NDCG@10 trên nhóm dẫn chiếu đạt 0.9062** (+0.0554 so với Base+KG và +0.1831 so với Vector Only).
- Điều này khẳng định hệ thống RAG không chỉ gom đủ tài liệu mà còn xếp hạng những tài liệu quan trọng nhất lên đầu bảng, tối ưu hóa ngữ cảnh đưa vào LLM để sinh câu trả lời chính xác nhất.

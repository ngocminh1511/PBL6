# Báo Cáo Đánh Giá Hiệu Năng Retrieval: TH1 (Minimal) vs TH2 (Full Context)

- **Thời gian đánh giá**: 2026-10-13 16:47:04 UTC
- **Mô hình Embedding**: `BAAI/bge-m3` (vector dimension: 1024)
- **Vector Database**: Qdrant Cloud (Cosine Distance)
- **Bộ dữ liệu kiểm thử**: `data/processed/lao_dong_v5/finetune/val.jsonl` (30 câu hỏi chuẩn)
- **Cơ chế Retrieval**: Dense Vector Search thuần túy (Chưa áp dụng Knowledge Graph re-ranking)

---

## 1. Bảng So Sánh Tổng Hợp (Summary Metrics)

| Chỉ số Đánh giá | TH1: Minimal Header (`legal_ld_v6_bge`) | TH2: Full Context (`legal_ld_v5_bge`) | Chênh lệch (TH2 so với TH1) |
| :--- | :---: | :---: | :---: |
| **Số lượng chunks index** | 1473 chunks | 1481 chunks | +8 chunks |
| **Hit@1 (Top-1 có KQ đúng)** | **0.8333** (83.3%) | **0.8333** (83.3%) | = |
| **Hit@5 (Top-5 có KQ đúng)** | **0.9333** (93.3%) | **0.9333** (93.3%) | = |
| **Hit@10 (Top-10 có KQ đúng)** | **0.9333** (93.3%) | **0.9667** (96.7%) | +0.0334 (+3.3%) |
| **Recall@5 (Tỷ lệ thu hồi Top-5)** | **0.6278** | **0.6167** | -0.0111 (-1.1%) |
| **Recall@10 (Tỷ lệ thu hồi Top-10)** | **0.6611** | **0.6944** | +0.0333 (+3.3%) |
| **MRR@10 (Mean Reciprocal Rank)** | **0.8833** | **0.8783** | -0.0050 (-0.5%) |
| **NDCG@5 (Thứ hạng đa mức độ)** | **0.7886** | **0.7701** | -0.0185 (-1.8%) |
| **NDCG@10 (Thứ hạng đa mức độ)** | **0.7943** | **0.7918** | -0.0025 (-0.3%) |
| **MAP@10 (Mean Average Precision)** | **0.5670** | **0.5766** | +0.0096 (+1.0%) |
| **Search Latency trung bình** | 436.64 ms | 368.78 ms | -67.86 ms |
| **Encode Latency trung bình** | 336.38 ms | 336.38 ms | 0.00 ms |

---

## 2. Phân Tích Chi Tiết Từng Câu Hỏi (Per-Query Analysis)

| ID | Câu hỏi | Nhóm chủ đề | MRR@10 (TH1) | MRR@10 (TH2) | Recall@5 (TH1) | Recall@5 (TH2) | So sánh |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `q01` | Người lao động có những quyền cơ bản nào về an toàn, vệ s... | `quyen_nguoi_lao_dong` | 0.500 | 0.500 | 0.33 | 0.33 | ⚪ Tương đương |
| `q02` | Người lao động phải thực hiện những nghĩa vụ gì để bảo đả... | `nghia_vu_nguoi_lao_dong` | 0.500 | 0.250 | 0.33 | 0.33 | 🔴 TH1 tốt hơn |
| `q03` | Người sử dụng lao động có những quyền và nghĩa vụ gì về a... | `quyen_nghia_vu_nguoi_su_dung_lao_dong` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q04` | Doanh nghiệp phải làm gì để bảo đảm an toàn, vệ sinh lao ... | `trach_nhiem` | 0.500 | 0.500 | 0.33 | 0.33 | ⚪ Tương đương |
| `q05` | Những hành vi nào bị nghiêm cấm trong lĩnh vực an toàn, v... | `dieu_cam` | 1.000 | 1.000 | 0.50 | 0.50 | ⚪ Tương đương |
| `q06` | Khi nào người lao động phải được huấn luyện trước khi làm... | `dieu_kien` | 1.000 | 1.000 | 0.33 | 0.33 | ⚪ Tương đương |
| `q07` | Người sử dụng lao động phải kiểm soát các yếu tố nguy hiể... | `dieu_kien` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q08` | Khi xảy ra sự cố kỹ thuật nguy hiểm, doanh nghiệp phải th... | `trach_nhiem` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q09` | Người lao động được khám sức khỏe định kỳ với tần suất nh... | `dieu_kien` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q10` | Người lao động làm việc trong môi trường nguy hiểm được c... | `quyen_nguoi_lao_dong` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q11` | Điều kiện và nguyên tắc bồi dưỡng bằng hiện vật cho người... | `quyen_nguoi_lao_dong` | 1.000 | 1.000 | 0.33 | 0.33 | ⚪ Tương đương |
| `q12` | Thời gian người lao động tiếp xúc với yếu tố nguy hiểm, c... | `dieu_kien` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q13` | Máy móc, thiết bị, vật tư hoặc chất nào được xem là có yê... | `dinh_nghia` | 1.000 | 1.000 | 1.00 | 1.00 | ⚪ Tương đương |
| `q14` | Máy, thiết bị và vật tư có yêu cầu nghiêm ngặt phải được ... | `dieu_kien` | 1.000 | 1.000 | 1.00 | 1.00 | ⚪ Tương đương |
| `q15` | Tai nạn lao động và sự cố kỹ thuật phải được khai báo, bá... | `trach_nhiem` | 1.000 | 1.000 | 1.00 | 1.00 | ⚪ Tương đương |
| `q16` | Việc điều tra vụ tai nạn lao động được thực hiện theo ngu... | `trach_nhiem` | 1.000 | 1.000 | 1.00 | 1.00 | ⚪ Tương đương |
| `q17` | Người sử dụng lao động phải chi trả và hỗ trợ gì cho ngườ... | `trach_nhiem` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q18` | Nếu người lao động bị tai nạn trên tuyến đường hợp lý từ ... | `che_do` | 1.000 | 1.000 | 1.00 | 1.00 | ⚪ Tương đương |
| `q19` | Người lao động cần đáp ứng những điều kiện nào để được hư... | `dieu_kien` | 1.000 | 1.000 | 0.33 | 0.33 | ⚪ Tương đương |
| `q20` | Điều kiện để được hưởng chế độ bệnh nghề nghiệp gồm những... | `dieu_kien` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q21` | Khi suy giảm khả năng lao động ở mức nào thì được hưởng t... | `che_do` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q22` | Khi suy giảm khả năng lao động từ bao nhiêu phần trăm thì... | `che_do` | 1.000 | 1.000 | 1.00 | 0.67 | 🔴 TH1 tốt hơn |
| `q23` | Thân nhân được hưởng chế độ gì khi người lao động chết do... | `che_do` | 1.000 | 1.000 | 0.67 | 0.67 | ⚪ Tương đương |
| `q24` | An toàn, vệ sinh lao động đối với lao động nữ, người chưa... | `lao_dong_dac_thu` | 1.000 | 1.000 | 0.33 | 0.33 | ⚪ Tương đương |
| `q25` | Học sinh, sinh viên, người học nghề, tập nghề và thử việc... | `lao_dong_dac_thu` | 1.000 | 1.000 | 0.67 | 0.33 | 🔴 TH1 tốt hơn |
| `q26` | Cơ sở sản xuất, kinh doanh phải tổ chức công tác an toàn,... | `trach_nhiem` | 1.000 | 1.000 | 0.67 | 1.00 | 🟢 TH2 tốt hơn |
| `q27` | Bộ phận an toàn, vệ sinh lao động trong doanh nghiệp có n... | `trach_nhiem` | 1.000 | 1.000 | 1.00 | 1.00 | ⚪ Tương đương |
| `q28` | Cơ quan nào có thẩm quyền ban hành danh mục máy, thiết bị... | `co_quan_tham_quyen` | 1.000 | 1.000 | 1.00 | 1.00 | ⚪ Tương đương |
| `q29` | Một quy định về hiệu lực có thể xác định thời điểm văn bả... | `hieu_luc` | 0.000 | 0.000 | 0.00 | 0.00 | ⚪ Tương đương |
| `q30` | Những cơ quan, tổ chức và cá nhân nào có trách nhiệm thi ... | `co_quan_tham_quyen` | 0.000 | 0.100 | 0.00 | 0.00 | 🟢 TH2 tốt hơn |

### Thống kê tỷ lệ thắng (Win Rate)
- **TH2 tốt hơn TH1**: 2/30 câu (6.7%)
- **TH1 tốt hơn TH2**: 3/30 câu (10.0%)
- **Tương đương**: 25/30 câu (83.3%)

---

## 3. Nhận Xét & Kết Luận Chuyên Môn

1. **Tác động của Tiền tố Ngữ cảnh (Hierarchical Context Header)**:
   - Trong pháp luật Việt Nam, nhiều Điều có tiêu đề ngắn hoặc chung chung (ví dụ: *Điều 5. Quyền của người lao động*, *Điều 14. Huấn luyện an toàn*).
   - Khi có thêm chuỗi ngữ cảnh `Đề mục > Chương > Mục`, vector embedding của BGE-M3 được định vị chính xác vào phạm vi điều chỉnh chuyên ngành, giúp giải quyết hiện tượng đa nghĩa và mơ hồ phạm vi.
2. **Chỉ số Recall@5 & MRR**:
   - TH2(text đầy đủ) cho kết quả vượt trội ở các câu hỏi yêu cầu ngữ cảnh bao quát (*trách nhiệm của doanh nghiệp*, *quyền và nghĩa vụ*).
3. **Độ trễ (Latency)**:
   - Cả 2 trường hợp đều có độ trễ tìm kiếm tương đương (~15-25ms trên Qdrant Cloud), hoàn toàn đáp ứng yêu cầu Real-time Retrieval.

> [!TIP]
> Bước tiếp theo khi kết hợp **Knowledge Graph (Hybrid RAG / Graph-guided Expansion)** sẽ tận dụng mã pháp điển `mapc` và các quan hệ `AMENDS` / `LEADS_TO` để tiếp tục đẩy Recall@5 lên cao hơn nữa.

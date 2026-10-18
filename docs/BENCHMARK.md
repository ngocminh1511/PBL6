# Thiết kế benchmark đánh giá KG-RAG pháp luật lao động

Cập nhật: 2026-10-12. Đã cài đặt: version benchmark theo dữ liệu (mục 3) và metric truy hồi (mục 4.1),
benchmark `lao_dong_v5` với bộ v1. Các mục 4.2–4.6 (ablation, sinh câu trả lời, hội thoại) để giai đoạn sau.

Mục tiêu: một benchmark đánh giá **từng tầng** của pipeline (ontology → truy hồi → rerank → sinh câu trả lời → trích dẫn),
theo cách các paper chuẩn đã làm, và **gắn với một phiên bản dữ liệu cụ thể**: mỗi phiên bản ontology/projection
(`lao_dong_v4`, `lao_dong_v5`, …) có một phiên bản benchmark riêng, đóng băng, kết quả không trộn lẫn.

---

## 1. Tài liệu tham khảo đã đọc

| Nguồn | Nội dung chính | Lấy gì cho mình |
|---|---|---|
| **NitiBench** (EMNLP 2025, `docs/references/Nitibench`) | Luật Thái, đơn vị truy hồi = section (≈ Điều). CCL: 3.729 câu do chuyên gia viết từ 1 section; Tax: 50 ca thật, 2,6 section/câu. | Định nghĩa metric truy hồi (HR, Multi-HR, Recall micro, MRR, Multi-MRR, k = 1/5/10); metric end-to-end Coverage 0/50/100, Contradiction, Citation P/R/F1; kiểm định LLM judge với người (F1 > 0,8 trên 150–200 mẫu); 3 mức ngữ cảnh: không truy hồi / truy hồi / gold. |
| **LexRAG** (SIGIR 2025, `docs/references/LexRAG`) | 1.013 hội thoại 5 lượt, 17k điều luật TQ, 11 chuyên gia gán nhãn, BM25 top-30 hỗ trợ tìm điều. | Tách hai tác vụ: truy hồi hội thoại và sinh câu trả lời; so sánh 4 cách xử lý hội thoại (câu cuối / toàn bộ ngữ cảnh / mọi câu hỏi / rewrite); LLM judge 5 tiêu chí, có cảnh báo thiên vị độ dài; keyword accuracy. |
| **Pham & Phan, DST 2026** (`docs/references/DST-V5I1P101.pdf`) | KG-RAG pháp luật VN (gồm Luật Lao động), trích dẫn Điều/Khoản/Điểm. | Baseline BM25 / LLM thuần / Dense RAG; Answer Accuracy, Citation Precision/Recall. **Điểm yếu** để mình làm tốt hơn: không nêu số câu hỏi, không ablation, không CI, không có metric truy hồi theo k. |
| Slide nhóm `PBL7_Thai_vs_Vietnam_Legal_RAG.pptx` | Kế hoạch ablation E0–E4 và danh sách metric. | Giữ nguyên làm khung ablation (mục 4.3). |
| Khảo sát thêm | ALQAC (macro-F2), Zalo AI 2021 (nDCG@10), VLQA, VLegal-Bench, COLIEE, STARD, ALCE, RAGChecker, TREC RAG 2024, CRAG, BEIR/MTEB, KILT, Datasheets for Datasets. | F2 để so với ALQAC/COLIEE; nugget và citation support (TREC RAG, ALCE); abstain (CRAG); quy ước version (KILT, MTEB). |

Số liệu tham khảo (để biết mức hợp lý, không so trực tiếp vì khác corpus):
NitiBench-CCL BGE-M3 HR@5 = 0,88; Tax Multi-HR@5 chỉ 0,20–0,29. LexRAG R@10 tốt nhất 33% (hội thoại).
DST 2026: Dense RAG → KG-RAG: Accuracy 78,9 → 85,7%, Citation Recall 68,3 → 81,6%.

---

## 2. Hiện trạng benchmark trong repo

Đã có và **đúng hướng**:
- Bộ test v2 dựng theo quy trình chuẩn IR: chọn Điều nguồn theo tầng (đề mục / loại văn bản / kiểu câu hỏi),
  **pooling** ứng viên từ BM25 + 3 embedding (như TREC, tránh thiên vị một mô hình), nhãn **graded 0–3**,
  có câu `deep_khoan` và `multi_dieu`. Hướng dẫn gán nhãn rõ ràng (`annotation/GUIDELINES.md`).
- Gold gắn theo `mapc`, gom kết quả theo Điều trước khi tính điểm.
- 9 competency question cho ABox, SHACL 0 vi phạm.

Còn thiếu / sai:

| # | Vấn đề | Mức |
|---|---|---|
| 1 | **Chưa có nhãn người duyệt.** `review.xlsx`: 30/150 câu có `action`, 88/2.154 ô `grade` được điền. Chưa có `benchmark_questions_v2.jsonl`. | Chặn |
| 2 | **Chưa có kết quả nào** (`evaluation/results/` trống). | Chặn |
| 3 | ~~**Metric đặt tên sai:** `recall_at_k` thực chất là HitRate@k.~~ Đã sửa: HitRate, Recall (micro), MultiHit riêng. | Đã sửa |
| 4 | ~~Không có version benchmark.~~ Đã có `benchmark_version.py` (mục 3). | Đã sửa |
| 4b | ~~Collection được dùng lại khi chỉ trùng `chunk_id`, kể cả khi text đã đổi.~~ Nay so cả text. | Đã sửa |
| 4c | ~~Grade 1 ("chỉ cho ngữ cảnh") được tính là trúng trong Recall/MRR.~~ Nay tính đúng từ grade ≥ 2 (`--min-grade`); nDCG vẫn dùng cả 3 mức. | Đã sửa |
| 5 | Chỉ đo **embedding**. Chưa đo graph expansion, rerank, rewrite, sinh câu trả lời, trích dẫn. | Thiếu |
| 6 | Câu hỏi do LLM soạn từ 1 Điều nguồn: NitiBench chỉ ra kiểu này dễ mơ hồ, văn phong "sạch" hơn người dùng thật. | Hạn chế |
| 7 | Không có gold answer / ý chính (nugget) để chấm câu trả lời; không có câu hội thoại nhiều lượt; không có câu ngoài phạm vi (cần từ chối). | Thiếu |
| 8 | Không có độ đồng thuận người chấm (kappa), không có CI / kiểm định thống kê. | Thiếu |

Kiểm tra v4 ↔ v5 (2026-10-12): cùng 1.407 `mapc`, không Điều nào thêm/bớt. Nội dung giống nhau, chỉ khác phần đầu chunk
(v5 thêm số hiệu văn bản, "Điều N." thay mã pháp điển) và v5 cắt 38 Điều dài thành 112 phần.
→ Gold của v2 dùng được cho cả hai phiên bản, nhưng **kết quả** phải tính riêng vì text đem đi embed khác nhau.

---

## 3. Version benchmark theo phiên bản ontology

Quy tắc (theo cách KILT gắn mọi tác vụ vào một snapshot Wikipedia, MTEB ghim `revision`):

1. **Phiên bản benchmark = (bộ câu hỏi, phiên bản dữ liệu).** Đặt tên `<testset>@<dataset_id>`, ví dụ `v2@lao_dong_v5`.
2. Mỗi phiên bản có thư mục riêng, đóng băng, không sửa tay sau khi phát hành (`labor_rag/evaluation/benchmark_version.py`):

```
labor_rag/evaluation/benchmarks/
  lao_dong_v5/
    manifest.json             # hash dữ liệu + danh sách bộ câu hỏi đã đóng băng
    v1.jsonl                  # câu hỏi, gold theo mapc
    v1.gold.jsonl             # mỗi Điều gold lúc đóng băng: content_hash, ten, document_id, meta_dieu, số phần
  lao_dong_v6/                # (ví dụ) phiên bản sau, mang bộ câu hỏi sang bằng --from
    v1.jsonl
    v1.gold.jsonl
    v1.migration.json         # trạng thái từng gold khi chuyển version, câu bị loại, Điều mới
labor_rag/evaluation/results/<dataset_id>/<testset>/<run_id>/
    summary.csv  metrics.csv (CI)  breakdown.csv  per_query_results.jsonl  run.json
```

3. `manifest.json` ghi: `dataset_id`, prefix collection Qdrant, sha256 của `chunks.jsonl`, `kg_nodes/edges.jsonl`,
   TBox (`vn_legal_ontology_schema_v4.ttl`), ABox; mỗi bộ câu hỏi có sha256, số câu, số Điều gold, nguồn, ngày đóng băng.
   Hash tính sau khi đổi CRLF → LF nên giống nhau trên mọi máy. Lúc chạy, benchmark **dừng** nếu `chunks.jsonl`
   hoặc file câu hỏi khác manifest; KG / TBox / ABox đổi chỉ cảnh báo (truy hồi vector không đọc chúng;
   `abox_lao_dong.ttl` bị ghi đè mỗi lần dựng lại nên chỉ dùng để phát hiện, không chặn).
4. **Gold khóa theo ID ổn định**: `mapc` (mã pháp điển) và kèm `document_id:dN[:kM]` (số hiệu văn bản + Điều + Khoản).
   Không dùng `chunk_id` vì v5 cắt Điều thành `:p1`, `:p2`.
5. **Chuyển gold sang version mới** (`freeze --dataset <mới> --testset <tên> --from <cũ>`): với mỗi Điều gold, so `content_hash`
   (hash phần thân Điều, không gồm phần đầu chunk) giữa hai version:
   - `unchanged` → giữ nhãn;
   - `changed` (nội dung sửa đổi) hoặc `missing` (bị bãi bỏ / đổi mã) → câu hỏi đó **bị loại** khỏi version mới,
     ghi trong `excluded` và `<testset>.migration.json` để người chấm lại rồi đóng băng lại bằng `--questions`;
   - `new_articles`: Điều mới xuất hiện ở version mới, chưa từng nằm trong pool → nên chạy lại `pool` cho các câu liên quan.
   Chunk v4 không có `content_hash` nên chuyển từ v4 sẽ coi mọi Điều là đổi. Không cần: bộ câu hỏi được đóng băng thẳng vào v5.
6. Datasheet ngắn (theo *Datasheets for Datasets*) trong `manifest.json` hoặc `README` của thư mục: nguồn câu hỏi,
   ai gán nhãn, kappa, mục đích sử dụng, giới hạn.

Ba Điều trùng mã (`20.4.TT.5.2`, `20.5.TT.74.1`, `20.5.TT.74.2`) có `mapc` dạng URI `..._dup2`: không dùng làm gold
cho tới khi `ontology_to_jsonl` cho chúng ID ổn định.

---

## 4. Các tầng đánh giá

Ký hiệu: N câu hỏi, T_i tập gold (grade ≥ 2 là "relevant" cho metric nhị phân; nDCG dùng nguyên thang 0–3),
R_i^k top-k Điều sau khi gom các phần của cùng Điều.

### 4.0 Tầng ontology / KG (mỗi version)

Đã có, chỉ cần đưa vào báo cáo của version: tỉ lệ competency question pass (`tests/test_cq_v4.py`), số vi phạm SHACL,
độ phủ so với nguồn (1.407/1.407 Điều, % Điều có `codificationOf`, % cạnh REFERS_TO trỏ tới Điều có nội dung).

### 4.1 Truy hồi (retriever đơn lẻ: embedding, BM25)

| Metric | Định nghĩa | Nguồn |
|---|---|---|
| HitRate@k | (1/N) Σ 1[R_i^k ∩ T_i ≠ ∅] | NitiBench (đây là "Recall@k" hiện tại) |
| Recall@k | Σ\|R_i^k ∩ T_i\| / Σ\|T_i\| (micro) | NitiBench |
| Multi-HitRate@k | (1/N) Σ 1[T_i ⊆ R_i^k] | NitiBench, quan trọng cho câu `multi_dieu` |
| MRR@10 | 1/rank gold đầu tiên | chuẩn |
| nDCG@10 | gain 2^g − 1, g ∈ {0..3} | BEIR/MTEB (metric chính khi so embedding) |

k = 1, 5, 10. Mỗi metric kèm CI 95% bootstrap (10.000 lần, theo câu hỏi) trong `metrics.csv`;
`breakdown.csv` tách theo `de_muc`, `style`, tag (`deep_khoan`, `multi_dieu`). Đã cài đặt trong `embedding_benchmark.py`.
(Recall@50, trần cho reranker, thêm khi làm mục 4.2.)

**4.2 – 4.6 dưới đây chưa làm**: nhóm chưa dùng ablation; giữ lại làm thiết kế cho giai đoạn sau.

### 4.2 Truy hồi cả pipeline (sau graph + rerank)

Tập Điều cuối cùng đưa vào prompt là tập có kích thước thay đổi, nên đo thêm như ALQAC/COLIEE:
**Precision, Recall, F2 theo từng câu rồi lấy trung bình (macro-F2)**. Kèm số Điều và số token đưa vào prompt.
Đo **trước và sau rerank** (NitiBench: graph expansion tăng recall nhưng Điều thêm vào nằm cuối danh sách, chỉ có ích khi rerank đưa lên).

### 4.3 Ablation (khung E0–E4 trong slide nhóm)

Giữ cố định LLM, top-k, ngân sách token. Mỗi cấu hình chạy trên cùng bộ câu hỏi của cùng version.

| Mã | Cấu hình | So sánh để trả lời |
|---|---|---|
| E0 | BM25 | baseline từ vựng |
| E1 | Dense (bkai / bge-m3 / mpnet) | chọn embedding |
| E1h | Dense trên chunk v4 vs v5 | chunk theo cấu trúc có giúp không (đây là lý do cần benchmark theo version) |
| E2 | E1 + REFERS_TO depth 1, 2 | graph expansion; báo cáo cả số Điều thêm vào |
| E3 | E2 + LLM rerank | rerank |
| E4 | E3 + citation verification | xác minh trích dẫn |
| (tùy chọn) | BM25 + dense (RRF), bge-m3 sparse | hybrid từ vựng |

### 4.4 Sinh câu trả lời và trích dẫn

Cần thêm vào mỗi câu hỏi: `gold_answer` ngắn và 2–5 **ý chính (nugget)**, mỗi ý gắn với Điều/Khoản (theo TREC RAG 2024).

| Metric | Định nghĩa | Nguồn |
|---|---|---|
| Coverage | 100 = đủ mọi ý chính, 50 = thiếu một phần, 0 = không đúng ý nào (LLM judge) | NitiBench |
| Contradiction | 1 nếu câu trả lời mâu thuẫn gold answer | NitiBench |
| Citation P/R/F1 | Điều được trích so với gold (mức Điều; mức Khoản nếu gold có Khoản) | NitiBench, DST 2026 |
| Citation support | % câu (statement) được các Điều nó trích **thực sự** hỗ trợ (LLM/NLI) | ALCE, TREC RAG |
| Unverified rate | % trích dẫn bị `citation_verify` đánh dấu (đã có code) | của mình |
| Abstain | Với câu ngoài phạm vi: +1 từ chối đúng, −1 bịa | CRAG |

Ba mức ngữ cảnh như NitiBench/LexRAG: **không truy hồi** (sàn), **pipeline**, **gold Điều** (trần). Khoảng cách giữa
pipeline và gold cho biết lỗi do truy hồi hay do LLM.

**LLM judge phải được kiểm định**: 2 người chấm ~100–150 câu trả lời, so với judge; yêu cầu Cohen κ ≥ 0,6
(hoặc weighted F1 ≥ 0,8 như NitiBench), báo cáo ma trận nhầm lẫn. Prompt judge ghi vào repo (NitiBench không công bố prompt, đây là điểm bị chê).
Judge khác model với generator; nhiệt độ 0.

### 4.5 Hội thoại (query rewrite)

Bộ con nhỏ (~20 hội thoại × 3 lượt, lượt sau dùng đại từ / tỉnh lược như LexRAG). So 3 cách: câu cuối, nối mọi câu hỏi,
`rewrite_query`; metric như 4.1 trên lượt 2–3.

### 4.6 Hiệu năng

Latency từng bước (encode, Qdrant, Neo4j, rerank, generate), số token prompt, số lần gọi LLM. DST 2026 bị chê 38 s/câu.

### 4.7 Thống kê

- 95% CI bằng bootstrap theo câu hỏi (10.000 lần lấy mẫu).
- So hai cấu hình: kiểm định hoán vị cặp (paired randomization), hiệu chỉnh Holm khi so nhiều cấu hình.
- Với 150 câu, chênh lệch nhỏ hơn ~5 điểm HitRate thường không có ý nghĩa: ghi rõ trong báo cáo.

---

## 5. Bộ câu hỏi

| Bộ | Kích thước | Dùng cho | Trạng thái |
|---|---|---|---|
| v1 (q01–q30) | 30 | so với kết quả cũ | có |
| v2 (ld001–ld120 + v1) | 150 | 4.1–4.3 | **chờ người duyệt** |
| v2-gen: thêm `gold_answer` + nugget cho v2 | 150 | 4.4 | chưa có (LLM nháp từ Điều gold, người sửa) |
| real-user: câu hỏi thật từ trang tư vấn lao động, viết lại để bỏ thông tin cá nhân | 30–50 | kiểm tra độ lệch văn phong (pitfall NitiBench) | chưa có |
| conversational | 20 × 3 lượt | 4.5 | chưa có |
| out-of-scope | 10–15 | abstain | chưa có |
| ngoài (tùy chọn): Zalo AI 2021 lọc các Điều thuộc BLLĐ 2019, map sang `mapc`; VLQA mảng "Lao động – tiền lương" khi được công bố | — | kiểm tra trên dữ liệu người khác gán | cần xác minh bản quyền / độ phủ |

Quy tắc:
- **Chia dev / test** (ví dụ 50 / 100, phân tầng theo đề mục + kiểu câu). Chỉ tinh chỉnh (top-k, prompt, trọng số) trên dev.
- **Dữ liệu fine-tune không được lấy từ test**, kể cả Điều nguồn của câu test (tránh rò rỉ).
- Độ đồng thuận: 2 người chấm chung ~20–30 câu (đã gợi ý trong GUIDELINES), báo cáo weighted κ trên thang 0–3.
- Ghi `grades_from_suggestion`; bản chính thức phải bằng 0.

---

## 6. So với các paper

| | DST 2026 | NitiBench | LexRAG | Benchmark đề xuất |
|---|---|---|---|---|
| Số câu công bố | không | 3.729 + 50 | 5.065 | 150 (+ bộ con) |
| Nhãn graded | không | không | không | 0–3 |
| Pooling nhiều hệ | không | không (1 section) | BM25 top-30 | BM25 + 3 embedding |
| Metric truy hồi theo k | không | có | có | có + F2 |
| Citation P/R | có (mức Điều) | có | không | có, mức Điều + Khoản, + support |
| Judge kiểm định với người | không | có | không | có |
| Ablation | không | có | có | E0–E4 |
| CI / kiểm định | không | không | không | có |
| Gắn version dữ liệu | không | không | không | có |

---

## 7. Việc cần làm (theo thứ tự)

1. ✅ Version benchmark: `benchmark_version.py` (`freeze`, `freeze --from`, `check`, `list`), kiểm hash khi chạy.
2. ✅ `embedding_benchmark.py`: HitRate / Recall micro / MultiHit / MRR / nDCG + CI bootstrap, `--min-grade`, `--benchmark`,
   kết quả theo `results/<dataset_id>/<testset>/<run_id>/`; dùng lại collection chỉ khi text khớp. Notebook đã cập nhật.
3. ✅ Đóng băng bộ v1 (30 câu, 20.5) vào `benchmarks/lao_dong_v5/`.
4. **Bộ câu hỏi mới phủ cả chủ đề** (nhóm đang tìm): đóng băng bằng `freeze --dataset lao_dong_v5 --testset <tên> --questions <file>`.
   Định dạng: mỗi dòng `{"id", "question", "relevance": {mapc: 1|2|3}}`, nên có `de_muc`, `style`, `tags`; mỗi câu cần ít nhất một Điều grade ≥ 2.
5. Chạy benchmark trên v5 (bkai / bge-m3 / mpnet) → baseline đầu tiên.
6. Sau khi có baseline mới fine-tune embedding, so trên cùng `<testset>@lao_dong_v5`.
7. Giai đoạn sau: ablation (4.2–4.3), sinh câu trả lời (4.4), hội thoại (4.5).

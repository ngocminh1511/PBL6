# Dữ liệu fine-tune BGE-M3 (Lao động)

Cập nhật: 2026-10-19. Tài liệu này mô tả cách tạo bộ train/val để fine-tune BGE-M3 cho truy hồi Pháp điển Lao động:
dữ liệu đến từ đâu, được xử lý thế nào, và chạy lại ra sao.

Mục tiêu của fine-tune là **dạy mô hình nối câu hỏi đời thường với đoạn luật trả lời nó** ("nghỉ phép" → "nghỉ hằng năm",
"đuổi việc" → "sa thải / đơn phương chấm dứt"), và phân biệt các Điều na ná nhau. Mô hình không học thuộc nội dung luật.
Vì vậy câu hỏi có thể lấy từ nhiều nguồn, nhưng **đoạn đúng luôn phải là chunk của corpus đang được index** (`lao_dong_v5`).

---

## 1. Luồng xử lý

```
data/finetune/<nguồn>/            (thô, tải về)
        │  extract_* / map_* / fetch_hf_sources
        ▼
data/processed/finetune/<nguồn>/  (đã trích / map)
        │  sources.py  → một dạng record chung
        │  align.py    → gióng về chunk v5: tier + temporal   → <nguồn>/aligned.jsonl
        ▼
build_dataset.py   chọn → khử trùng → loại gần trùng benchmark → chia theo Điều → giới hạn câu sinh
        ▼
data/processed/finetune/merged/   queries_train.jsonl, queries_val.jsonl, rejected.jsonl, build_report.json
        │  mine_negatives.py (GPU)  → hard_negatives.jsonl
        │  assemble_dataset.py      → train.jsonl, val.jsonl
        ▼
train.py  (notebook 03)
```

Ba notebook trong `notebooks/finetune/` chạy theo đúng thứ tự này:

| Notebook | Việc |
|---|---|
| `01_data_analysis.ipynb` | Phân tích từng nguồn: tier, temporal, nhiễu, trùng, rò rỉ, độ phủ |
| `02_data_processing.ipynb` | Tải / trích → build → kiểm chứng → (GPU) đào hard negative, ghép `train.jsonl` |
| `03_finetuning.ipynb` | Train 2 giai đoạn, chọn checkpoint trên val, đánh giá cuối trên benchmark v3 |

Code nằm trong `labor_rag/finetune/`, test ở `tests/test_finetune_build.py`. Notebook chỉ điều phối.

---

## 2. Nguồn dữ liệu

Mỗi nguồn một thư mục, cả thô (`data/finetune/<nguồn>/`) lẫn đã xử lý (`data/processed/finetune/<nguồn>/`).
Cả hai thư mục đều **gitignored**: dữ liệu không được commit, chỉ commit code, docs và notebook.

| Nguồn | Lấy về bằng | Loại câu hỏi | Giấy phép / ghi chú |
|---|---|---|---|
| `tvpl` | `extract_tvpl_pairs.py`, `extract_tvpl_domain_pairs.py` (GreenNode/TVPL-Retrieval-VN) | thật (thuvienphapluat) | dùng nghiên cứu |
| `vlsp` | `extract_vlsp_pairs.py` (longstnguyen/vlsp2025-qa-*, **gated**: cần `HF_TOKEN` và bấm đồng ý trên trang dataset) | tình huống | **CC BY-NC-SA 4.0**, phải trích dẫn bài VLSP 2025 (INLG 2025) |
| `vilegal` | đặt tay `data/finetune/vilegal/train_data.json`, rồi `map_vilegal_labor.py` (docs/VILEGALEXPERT_LABOR_MAPPING.md) | thật (thuvienphapluat) | |
| `zalo` | đặt tay `data/finetune/zalo/train_data_model.json`, rồi `map_zaloai_labor.py` (docs/ZALOAI_LTR_MAPPING.md) | thật | chữ đã tách từ (`trợ_cấp`), được bỏ `_` |
| `bkai` | `fetch_hf_sources.py` (YuITC/Vietnamese-Legal-Documents) | thật | MIT |
| `phamson02` | `fetch_hf_sources.py` (phamson02/large-vi-legal-queries) | **sinh bởi LLM** | CC BY 4.0, trích dẫn bài của tác giả |
| `alqac` | `fetch_hf_sources.py` (another-symato/VMTEB-ALQAC-retrieval) | chuyên gia soạn | |

Đường dẫn khai báo trong `labor_rag/config.py`: `FINETUNE_RAW_DIR`, `FINETUNE_WORK_DIR`, `FINETUNE_MERGED_DIR`,
`finetune_raw_dir(nguồn)`, `finetune_source_dir(nguồn)`.

Nguồn đa lĩnh vực (BKAI, phamson02, ALQAC, TVPL mở rộng, VLSP) được lọc trước bằng từ khoá lao động trên câu hỏi
(`sources.LABOR_QUERY_RE`). Bộ lọc thật sự là bước gióng v5 ở mục 3.

---

## 3. Gióng về corpus v5 (`align.py`)

Đoạn luật của mỗi bản ghi được so với chunk v5 (bỏ dòng breadcrumb) bằng **cụm 8 từ liên tiếp**:

```
score(chunk) = max( số 8-gram chung / số 8-gram của đoạn nguồn ,  số 8-gram chung / số 8-gram của chunk )
```

Vế đầu bắt trường hợp nguồn trích một khoản, vế sau bắt câu trả lời trích nguyên Điều xen bình luận.
Đoạn đúng là chunk có score cao nhất, cộng các chunk khác đạt ≥ 60% điểm đó (các phần `:pN` của Điều dài), tối đa 3.

- Nguồn đã có chunk_id (ViLegal, Zalo) vẫn được **kiểm chứng lại** bằng nội dung. Nếu điểm < 0.1 thì gióng lại trên toàn corpus
  (`match = exact_rejected`). Bước này sửa 43 câu ViLegal lấy nhầm `:p1` và 40 câu ViLegal gán sai Điều.
- Nguồn không có văn bản luật gốc (VLSP: "Tiền đề lớn" là câu diễn giải) chỉ dựa vào chunk_id theo trích dẫn,
  không kiểm chứng được (`exact_unverified`, tier B, mặc định không dùng).
- **Đoạn đúng luôn là text chunk v5** (có breadcrumb "Lao động > Bộ luật … > Chương …"), đúng định dạng đã index,
  không bao giờ là câu trả lời hay đoạn trích của nguồn.

**Tier:** A khi score ≥ 0.5 · B khi 0.1–0.5 · C khi < 0.1 hoặc không khớp.

---

## 4. Lệch thời gian giữa dữ liệu và Pháp điển

Câu hỏi dùng lại được qua các phiên bản luật, đoạn luật thì không. Mỗi bản ghi được gán trạng thái:

| Trạng thái | Khi nào | Xử lý |
|---|---|---|
| `keep` | Cùng phiên bản: văn bản được dẫn là văn bản của chunk khớp, hoặc nguồn không dẫn | Dùng |
| `remap` | **Dữ liệu cũ hơn** Pháp điển: nguồn dẫn văn bản khác/cũ (BLLĐ 2012, bản trước sửa đổi…) nhưng nội dung trùng chunk v5 | Dùng, đoạn đúng là chunk v5 hiện hành |
| `pending` | **Dữ liệu mới hơn** Pháp điển: không khớp v5, văn bản dẫn ban hành từ `PENDING_FROM_YEAR = 2024` trở đi và không có trong v5 | Để riêng, chờ cập nhật corpus |
| `outside` | Không khớp v5: lĩnh vực khác, hoặc luật cũ mà nội dung đã thay đổi; hoặc chunk khớp đã hết hiệu lực (`still_valid = false`) | Không dùng |

Gióng **theo nội dung, không theo số Điều**, nên các Điều bị đánh số lại giữa hai bộ luật (Điều 111 BLLĐ 2012 → Điều 113 BLLĐ 2019)
vẫn được ghép đúng. Nếu quy định đã đổi (ví dụ "hợp đồng mùa vụ" bị bỏ), nội dung không còn khớp và bản ghi rơi vào `outside`.

**Khi corpus lên phiên bản mới** (v6 trở đi): không cần thu thập lại dữ liệu. Chạy lại `build_dataset --chunks <chunks mới>`:
câu hỏi giữ nguyên, đoạn đúng và hard negative được tính lại, các câu `pending` tự tìm được chỗ. Sau đó đo lại benchmark
để quyết định có cần train lại hay không.

Thực tế với dữ liệu hiện có: các bộ dữ liệu đều được tạo khoảng 2022–2023, nên gần như không có câu `pending` (3 câu).
Rủi ro thời gian nằm ở phía corpus (xem `docs/KNOWN_ISSUES.md`, mục fine-tune).

---

## 5. Build train/val (`build_dataset.py`)

1. **Chọn:** tier A, cộng tier B có score ≥ 0.3; temporal ∈ {`keep`, `remap`}.
2. **Khử trùng** theo câu hỏi đã chuẩn hoá. Khi trùng, giữ theo thứ tự ưu tiên nguồn
   **ALQAC > ViLegal > TVPL > BKAI > Zalo > VLSP > phamson02**: chuyên gia và câu thật trước, câu sinh sau cùng.
3. **Chống rò rỉ:** loại mọi câu có Jaccard (trên tập từ) ≥ 0.5 với **bất kỳ** câu benchmark nào
   (`labor_rag/evaluation/benchmark_questions*.jsonl` và `benchmarks/*/*.jsonl`).
4. **Chia train/val theo Điều:** chọn khoảng 10% số Điều có câu hỏi thật tier A, phân tầng theo đề mục. Một câu vào val khi
   **mọi** Điều của nó thuộc tập val; câu nằm vắt qua ranh giới bị loại. Val chỉ gồm câu thật tier A, tối đa 5 câu mỗi Điều.
   Nhờ vậy val đo được khả năng tổng quát sang Điều mô hình chưa thấy, và train/val không dùng chung Điều nào.
5. **Giới hạn câu sinh** (phamson02) ≤ 40% train, ưu tiên các câu rơi vào Điều mà câu hỏi thật chưa phủ.

**Val không lấy từ benchmark.** Benchmark (v3, 200 câu) chỉ dùng để báo cáo cuối, không dùng để chọn checkpoint.

Tham số đều có cờ dòng lệnh: `--no-tier-b`, `--tier-b-min`, `--synthetic-cap`, `--no-synthetic`, `--val-ratio`,
`--val-per-article`, `--leak-threshold`, `--seed`, `--chunks`, `--sources`.

### Kết quả lần build 2026-10-19 (corpus `lao_dong_v5`, 1.481 chunk)

| | |
|---|---|
| Train | **7.118 câu**: ViLegal 2.713, BKAI 1.359, TVPL 133, ALQAC 53, Zalo 13, phamson02 2.847 (40%) |
| Tier / temporal | A 6.549, B 569 / keep 6.870, remap 248 |
| Độ phủ | 956 chunk, 915 Điều (20.2: 406 · 20.4: 238 · 20.5: 167 · 20.3: 144); 274/345 chunk đáp án benchmark v3 |
| Val | 174 câu, 62 Điều (ViLegal 140, BKAI 26, ALQAC 6, TVPL 1, Zalo 1) |
| Bị loại | ngoài v5 10.542 · tier B thấp 2.937 · trùng 1.969 · giới hạn câu sinh 862 · gần trùng benchmark 302 · ranh giới/val 754 |
| Kiểm chứng | Điều chung train/val = 0 · câu gần trùng benchmark còn lại = 0 |

Lý do loại từng câu nằm trong `merged/rejected.jsonl`.

---

## 6. Hard negative và ghép dữ liệu train

`mine_negatives.py` lấy top 30 chunk gần nhất theo BGE-M3 gốc rồi giữ 5, sau khi bỏ:
- chunk cùng Điều với bất kỳ đoạn đúng nào;
- chunk thuộc Điều có quan hệ `REFERS_TO` (theo cả hai chiều, từ `kg_edges.jsonl`) với Điều đúng, vì dễ là false negative.

Bước này cần GPU, nên mặc định tắt trong notebook 02.

`assemble_dataset.py` (mặc định) ghép `queries_train` + hard negative thành `merged/train.jsonl`
(anchor / positive / negatives / type / metadata), và chép `queries_val` thành `merged/val.jsonl` theo định dạng
`chunk_relevance` mà `train.py::build_ir_evaluator` đọc. KG pairs (cặp Điều–Điều) mặc định tắt (`--with-kg-pairs` để bật)
vì cặp `same_chapter` nhiều nhiễu. `--legacy` giữ luồng cũ (synthetic queries + KG, val lấy từ benchmark).

`train.py` dùng `NoDuplicatesDataLoader` cho MNRL, để hai câu hỏi có cùng đoạn đúng không rơi vào cùng một batch
(nếu rơi vào, đoạn đúng của câu này thành mẫu âm của câu kia).

---

## 7. Chạy lại

```powershell
python -m labor_rag.finetune.fetch_hf_sources              # bkai, phamson02, alqac (bỏ qua file đã có)
python -m labor_rag.finetune.extract_tvpl_pairs            # tùy chọn: tải lại TVPL
python -m labor_rag.finetune.extract_tvpl_domain_pairs
python -m labor_rag.finetune.extract_vlsp_pairs            # cần HF_TOKEN + quyền truy cập dataset
python -m labor_rag.finetune.map_vilegal_labor             # cần data/finetune/vilegal/train_data.json
python -m labor_rag.finetune.map_zaloai_labor              # cần data/finetune/zalo/train_data_model.json
python -m labor_rag.finetune.build_dataset
python -m labor_rag.finetune.mine_negatives                # GPU
python -m labor_rag.finetune.assemble_dataset
pytest tests/test_finetune_build.py
```

Hoặc chạy lần lượt `notebooks/finetune/01 → 02 → 03`.

Sau khi fine-tune phải embedding lại toàn bộ corpus bằng model mới vào **collection mới**, giữ collection cũ làm baseline:
`python -m labor_rag.ingest.embed_and_index --model data/models/bge-m3-legal --collection legal_ld_v5_bge_ft --recreate`.

---

## 8. Giới hạn đã biết

- Ngưỡng tier và việc chọn chunk khớp nhất là tự động. Bảng 20 cặp mẫu trong notebook 02 nên được đọc mỗi lần build.
- Bộ lọc từ khoá lao động có thể bỏ sót câu không chứa từ khoá nào (chỉ áp với nguồn đa lĩnh vực).
- Val lệch về 20.2 (105/174 câu), vì Bộ luật Lao động có nhiều câu hỏi nhất.
- Lý do bỏ VLSP: đoạn đúng không phải văn bản luật, và 278/320 câu dẫn văn bản ngoài v5. Muốn dùng phải lấy văn bản gốc
  của Điều được dẫn rồi gióng lại.

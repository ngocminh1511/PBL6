# Thiếu sót đã biết

Cập nhật: 2026-10-12. Chunk chuyển sang cấu trúc v5 (`data/processed/lao_dong_v5`, xem docs/structural_jsonl.md);
`lao_dong_v4` giữ lại để so sánh.
Các con số dưới đây lấy từ lần dựng ABox cho toàn bộ 45 chủ đề có dữ liệu
(`python -m labor_rag.ingest.build_abox --chu-de 1 ... 45`): 65.997 Điều, 1,44 triệu triple, SHACL 0 vi phạm.

---

## 1. Chưa có kết quả benchmark embedding trên dữ liệu Lao động

**Trạng thái:** benchmark `lao_dong_v5` đã đóng băng với bộ v1 (30 câu, 20.5). Chưa chạy.
Bộ câu hỏi phủ cả chủ đề đang được làm lại.

Ngày 2026-10-10 đã xóa bộ dữ liệu thử nghiệm chỉ gồm 20.5 (`data/processed/ontology_v4/`) cùng kết quả benchmark
cũ của nó (ngày 2026-09-30, 348 chunk, parser cũ). Benchmark hiện chạy trên
`data/processed/lao_dong_v5/` (1.407 Điều, 38 Điều dài bị cắt thành nhiều phần, 1.481 chunk), qua
`labor_rag/evaluation/benchmarks/lao_dong_v5/` (README, mục "Benchmark theo phiên bản dữ liệu").

Trên Qdrant Cloud (kiểm tra ngày 2026-10-12) chỉ có `legal_ld_v5_bge`: 1.481 point, text khớp `chunks.jsonl`.
Chưa có `legal_ld_v5_bkai` và `legal_ld_v5_mpnet`. Lần chạy đầu sẽ tạo hai collection này bằng model trên máy,
hoặc tạo trước bằng Modal (`embed_and_index --backend modal --model ... --collection ...`).

```powershell
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1
```

Collection chỉ được dùng lại khi đủ `chunk_id` **và** đúng text, nên không còn rủi ro dùng vector cũ sau khi text đổi.
bkai và mpnet chỉ đọc 256 token đầu (bge-m3 đọc 8192), trong khi chunk v5 dài tới 1024 token,
nên phần cuối Điều dài không nằm trong vector của hai mô hình này (`max_seq_length` có trong `summary.csv`).

---

## 2. Ghi chú nguồn (`pGhiChu`) không tách được: 15 / ~66.000

**Hậu quả:** các Điều này vẫn có trong ABox (mã, tiêu đề, nội dung), nhưng
**không có liên kết tới văn bản nguồn** (`codificationOf`, `promulgatedBy`, ngày hiệu lực).

**Nguyên nhân:** ghi chú trong dữ liệu gốc lệch khỏi mẫu chuẩn
`(Điều N <Loại VB> số <số hiệu>, có hiệu lực thi hành kể từ ngày dd/mm/yyyy)`.

| Đề mục | Mã Điều | Lỗi trong dữ liệu gốc | Trích ghi chú |
|---|---|---|---|
| 2.2 Bảo hiểm y tế | 2.2.NĐ.2.27 | Thiếu chữ "Điều" | `(27 Nghị định số 70/2015/NĐ-CP, có hiệu lực …)` |
| 14.3 Giao thông đường thủy nội địa | 14.3.TT.29.2 | Ghi chú là nội dung điều khoản thi hành, không phải trích dẫn nguồn | `(Thông tư này có hiệu lực thi hành kể từ ngày 28 tháng 6 năm 2017. Bãi bỏ …)` |
| 17.1 Kế toán | 17.1.TT.25.29a | Thiếu chữ "kể", ngày viết bằng chữ | `… có hiệu lực thi hành từ ngày 01 tháng 01 năm 2019)` |
| 17.1 Kế toán | 17.1.TT.25.30a | Như trên | |
| 17.1 Kế toán | 17.1.TT.25.38a | Như trên | |
| 17.1 Kế toán | 17.1.TT.25.34 | Lỗi gõ "k ể" | `… có hiệu lực thi hành k ể từ ngày 01/01/2016 …` |
| 17.1 Kế toán | 17.1.TT.25.44 | Lỗi gõ "k ể" | |
| 17.1 Kế toán | 17.1.TT.25.54 | Lỗi gõ "n gày", "hông tư" | `… kể từ n gày 01/01/2016 … Điều 1 hông tư số 112/2018 …` |
| 24.3 Đê điều | 24.3.TL.1.5 | Trích theo "Mục" thay vì "Điều" | `(Mục 5 Thông tư liên tịch số 18/1999/TTLT/…)` |
| 24.9 Phát triển ngành nghề nông thôn | 24.9.TL.1.1 | Thiếu chữ "số" | `(Điều 1 Thông tư liên tịch 13/2014/TTLT-BNNPTNT-BKHĐT-BTC …)` |
| 33.7 Thuế sử dụng đất nông nghiệp | 33.7.TT.1.1 | Không có cụm "có hiệu lực" | `((Điều 1 Thông tư số 89-TC/TCT ngày 09/11/1993 của Bộ Tài chính …` |
| 33.7 Thuế sử dụng đất nông nghiệp | 33.7.TT.1.14 | Thiếu "thi hành" | `… có hiệu lực kể từ ngày 01/01/1994 …` |
| 33.7 Thuế sử dụng đất nông nghiệp | 33.7.TT.1.18 | Thiếu "Điều N" | `((Thông tư số 03/TC-TCT, có hiệu lực …))` |
| 33.7 Thuế sử dụng đất nông nghiệp | 33.7.TT.1.19 | Thiếu "Điều N" | `((Thông tư số 59/TC-TCT …` |
| 45.9 Phòng, chống tác hại của thuốc lá | 45.9.TT.1.4 | Trích theo "Mục" thay vì "Điều" | `((Mục IV Thông tư số 124/2007/TT-BTC …))` |

**Hướng sửa (nếu cần):** có thể nới regex `SOURCE_RE` trong
`labor_rag/ingest/build_abox.py` để chấp nhận ngày viết bằng chữ, thiếu "thi hành"/"kể",
và "Mục" thay "Điều". Các lỗi gõ ("k ể", "n gày", "hông tư") và ghi chú thiếu "Điều"
nên xử lý bằng bảng sửa tay theo mã Điều, không nên nới regex tới mức đó.

**Lưu ý:** không có chủ đề Lao động (20) nào nằm trong danh sách này.

---

## 3. Mã cơ quan ban hành chưa có tên đầy đủ: 8 mã

**Hậu quả:** văn bản vẫn có quan hệ `promulgatedBy`, nhưng node cơ quan chỉ có
lớp chung `vla:Authority` và nhãn là chính mã viết tắt (ví dụ `rdfs:label "KL"`).

| Mã | Số lần | Ví dụ số hiệu | Đề mục | Dự đoán (cần xác minh) |
|---|---|---|---|---|
| `BTT` | 12 | 235/2009/TTLT/BTC-BGTVT-BTT | 33.4 Quản lý thuế | Chưa rõ: có thể là cách viết tắt khác của Bộ Thông tin và Truyền thông |
| `KL` | 5 | 102/2000/TT-BNN-KL | 24.2 Lâm nghiệp | Cục Kiểm lâm (đơn vị thuộc Bộ NN) |
| `PCLB` | 5 | 15/2001/TT-BNN-PCLB | 24.3 Đê điều | Cục Phòng chống lụt bão (thuộc Bộ NN) |
| `TP` | 5 | 01/1999/NQLT-TP-VHTT-NNPTNT-DTMN-ND | 44.8 Phổ biến, giáo dục pháp luật | Bộ Tư pháp |
| `VHTT` | 5 | (như trên) | 44.8 | Bộ Văn hóa - Thông tin |
| `DTMN` | 5 | (như trên) | 44.8 | Ủy ban Dân tộc và Miền núi |
| `KH` | 4 | 61/2000/TT-BNNPTNT/KH | 24.9 Phát triển ngành nghề nông thôn | Hậu tố đơn vị soạn thảo, xem lỗi parser bên dưới |
| `UBNVQH` | 1 | 01/2018/UBNVQH14 | 34.11 Quản lý thị trường | Có thể gõ nhầm từ `UBTVQH14` |

Trong số hiệu `01/1999/NQLT-TP-VHTT-NNPTNT-DTMN-ND`, mã `ND` đang bị bỏ qua vì
trùng với ký hiệu loại văn bản "NĐ" viết không dấu; đây có thể là Hội Nông dân Việt Nam.

**Lỗi parser liên quan:** `issuer_codes()` chỉ đọc phần sau dấu `/` cuối cùng,
nên với `61/2000/TT-BNNPTNT/KH` nó lấy `KH` và **bỏ sót `BNNPTNT`**. Cần sửa để
đọc mọi phần sau năm ban hành.

**Hướng sửa:** khi đã xác minh, thêm mã vào `AUTHORITIES` hoặc
`AUTHORITY_ALIASES` trong `labor_rag/ingest/build_abox.py`. Không có mã nào thuộc chủ đề Lao động (20).

---

## 4. Đặc điểm dữ liệu gốc (đã xử lý, ghi lại để tham khảo)

Các điểm này không còn gây lỗi, nhưng cần biết khi đọc số liệu:

- **104/306 đề mục rỗng** (chưa được pháp điển hóa), ví dụ 20.1 Giáo dục nghề nghiệp. Chủ đề Đất đai và Thi đua - khen thưởng rỗng hoàn toàn. Chủ đề 46 "Chủ đề test" là dữ liệu thử của nguồn.
- **Mã Điều trùng trong dữ liệu gốc**: 171 Điều thừa ở 28 đề mục, ví dụ `20.5.TT.74.1`, `20.4.TT.5.2`. ABox giữ cả hai Điều; Điều xuất hiện sau có URI hậu tố `_dup2` nhưng cùng `codificationNumber`.
- **429 Điều không có đoạn nội dung riêng**: toàn bộ quy định nằm trong dòng tiêu đề. `contentText` của các Điều này lấy bằng chính tiêu đề.
- **8 Điều không có ghi chú nguồn**, ví dụ `41a` (Công nghiệp), `35.8.LQ.68a`.

---

## 5. Kiểm tra parse chủ đề Lao động (2026-10-10)

Đã đối chiếu parser với HTML gốc trên 20.2–20.5. Kết quả: số Điều, thứ tự MAPC, vị trí Chương/Mục,
ghi chú nguồn và liên kết chỉ dẫn đều khớp 100%. Không có token nội dung nào bị sót, ngoài tiêu đề trang.
`chunks.jsonl` chứa đủ các đoạn của mọi Điều. Những điểm còn lại:

- **Chunk của Điều trùng mã có id dạng URI.** Bản thứ hai của `20.4.TT.5.2`, `20.5.TT.74.1` và `20.5.TT.74.2`
  có `chunk_id`/`mapc` là `https://example.org/vn-legal/instance#Article_..._dup2`, không phải mã Điều.
  Lý do: `ontology_to_jsonl` lấy id của node, và id này chuyển sang URI khi mã bị trùng. Nội dung chunk vẫn đúng.
- **48 Điều không có tiêu đề trong nguồn** (47 ở 20.5, ví dụ `20.5.QĐ.1.2`, và 1 ở 20.4). Trường `ten` của chunk
  được thay bằng "Điều <mã>.".
- **Số Điều trong `mapc` lệch số Điều gốc ở 12 / 1.407 Điều.** Pháp điển hợp nhất các Điều sửa đổi vào văn bản
  bị sửa và nối các Điều còn lại (hiệu lực, trách nhiệm thi hành) vào cuối văn bản đó, nên các Điều này mang số mới:
  `20.4.NĐ.3.43`, `.44` (Điều 3, 4 NĐ 61/2020), `20.2.NĐ.4.31` (Điều 3 NĐ 70/2023), `20.4.NĐ.5.46`, `.47`
  (Điều 2, 3 NĐ 74/2019), `20.5.TT.21.8`, `.9` (Điều 2, 3 TT 02/2023). `meta_dieu` lấy từ ghi chú nguồn nên vẫn đúng;
  trích dẫn và đối chiếu PDF dùng `meta_dieu`, không dùng số cuối của `mapc`.
- **Số khoản không liên tục** ở `20.2.NĐ.4.13`, `20.4.NĐ.3.18`, `20.4.NĐ.3.22`, `20.4.NĐ.3.30`.
  Các khoản này thiếu ngay trong HTML gốc, không phải do lỗi parse.

---

## Chunk v5: các điểm còn thiếu

**Trạng thái:** đã biết, chưa xử lý.

- `meta_chuong` / `meta_muc` của chunk Pháp điển luôn `null`: ABox chỉ có chương, mục của đề mục Pháp điển
  (`pd_chuong` / `pd_muc`), không có chương của văn bản gốc.
- `effective_to_date` của chunk Pháp điển luôn `null` với dữ liệu hiện có: Pháp điển không ghi quan hệ thay thế.
  Chỉ có khi nạp một PDF thay thế văn bản (ABox của PDF ghi `vlt:validTo`, structural_jsonl.md mục 6, 10).
- Parser văn bản sửa đổi (`labor_rag/ingest/amending.py`) mới thử trên văn bản mẫu, chưa chạy trên PDF thật.
  Nếu OCR tách sai phần nội dung mới trong ngoặc kép thành khoản riêng, phần sửa đổi sẽ bị cắt sai.
- PDF: `pdf_to_chunks` + `embed_and_index --upsert` đã có, nhưng chưa chạy thử trên OCR thật của
  `docs/Luat_lao_dong.pdf`. Cần xem: số Điều nhận được (~220), Điều sai số do OCR, chú thích tách đúng chưa.
- Dấu chú thích nằm trong câu ("Bộ luật Lao động1", "động¹") chưa bị xóa: OCR đọc số mũ không ổn định.
- Chú thích chỉ được tách khi nằm trọn trong một trang; chú thích tràn sang trang sau còn lẫn vào nội dung.
  Chưa parse chú thích thành `amended_by`.
- OCR gộp mọi phụ lục thành một chunk `:pl1`, chưa tách theo từng phụ lục.
- Điều 14 NĐ 97/2022 (`20.2.NĐ.6.14`) gần như toàn phụ lục dạng bảng, bị cắt theo câu thành 16 phần; khi ghép
  lại cả Điều (`join_parts`) còn lặp vài dòng gối đầu.
- Dẫn chiếu trong câu chữ (`references.py`): 32 dẫn chiếu tới luật không có trong dữ liệu và không kèm số hiệu
  ("Luật Bảo hiểm xã hội") không thành cạnh. "Điều 14" không nêu văn bản, trong một văn bản cũng có Điều 14, được
  gán cho chính văn bản đó dù có thể là văn bản khác (3/503 liên kết Pháp điển bị lệch vì vậy). "Của Luật này" trong
  nội dung mà một Điều sửa đổi chèn vào luật khác (Điều 219 BLLĐ) bị hiểu là luật đang xét.

---

## Fine-tune: các điểm cần lưu ý (2026-10-19)

Chi tiết dữ liệu fine-tune: docs/FINETUNE_DATA.md.

**1. `data/processed/lao_dong_v5/` từng bị xóa khỏi repo.** Commit `c0ece55` ("update result after run benchmark test 200
question", vào `develop` qua PR #1) xóa toàn bộ thư mục, gồm `chunks.jsonl`, `kg_nodes.jsonl`, `kg_edges.jsonl`.
Qdrant và Neo4j không bị ảnh hưởng, nhưng pipeline fine-tune và benchmark cần file cục bộ. Đã khôi phục nguyên trạng
ở `5d28985` (trên `dev/minh`). Khi merge `develop` cần kiểm tra để thư mục không bị xóa lại.

**2. Corpus v5 có thể đã cũ ở mảng Việc làm / BHXH / Công đoàn — cần đối chiếu.** `38-2013-qh13` (Luật Việc làm 2013)
và các nghị định hướng dẫn (28/2015, 61/2015, 31/2015) vẫn có `still_valid = true`. Nếu Pháp điển đã cập nhật luật thay thế
(Luật Việc làm 2025, Luật BHXH 2024, Luật Công đoàn 2024) thì chatbot đang trả lời theo văn bản cũ. Khoảng 290 câu
ViLegal và hầu hết câu Zalo gắn vào nhóm văn bản này. Khi corpus được cập nhật, chạy lại `build_dataset` (docs/FINETUNE_DATA.md, mục 4).

**3. Ánh xạ exact của ViLegal có lỗi; đã sửa ở bước gióng.** `map_vilegal_labor` luôn trả `chunk_id` = phần `:p1`
(43/107 Điều nhiều phần khớp ở phần khác) và gán sai Điều ở 40 câu (ví dụ "đi nghĩa vụ quân sự về có được làm tiếp"
→ Điều 32 thay vì Điều 31). `align.py` kiểm chứng lại bằng nội dung, nên `merged/` đã dùng chunk đúng.
Các file `vilegal_labor_mapped.json` thì vẫn giữ ánh xạ gốc.

**4. Có node `mapc` dạng IRI `..._dup2`.** 3 chunk (`24-2017-tt-bldtbxh:d2`, hai chunk của `TT_74`) có `mapc` là IRI
`https://example.org/vn-legal/instance#Article_..._dup2` thay vì mã `20.x...`, nên thống kê theo đề mục ở chỗ này bị lẫn.

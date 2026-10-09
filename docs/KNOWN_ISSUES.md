# Thiếu sót đã biết

Cập nhật: 2026-10-09, sau commit `d1e9257` (bộ đọc HTML chung + `build_abox`).
Các con số dưới đây lấy từ lần dựng ABox cho toàn bộ 45 chủ đề có dữ liệu
(`python -m labor_rag.ingest.build_abox --chu-de 1 ... 45`): 65.997 Điều, 1,44 triệu triple, SHACL 0 vi phạm.

---

## 1. Kết quả benchmark embedding đã cũ

**Trạng thái:** cần chạy lại.

`data/processed/ontology_v4/` đã được sinh lại bằng parser mới, nhưng
`labor_rag/evaluation/results/` (`summary.csv`, `per_query_results.jsonl`,
`model_metadata.json`) vẫn là kết quả của lần chạy ngày 2026-09-30 trên dữ liệu cũ.

Dữ liệu đã thay đổi:

| | Trước | Sau |
|---|---|---|
| Số chunk đề mục 20.5 | 348 | 350 (tách đúng 2 Điều trùng mã `20.5.TT.74.1`, `20.5.TT.74.2`) |
| Breadcrumb | `DeMuc > Chương I` | `An toàn, vệ sinh lao động > Chương I. QUY ĐỊNH CHUNG` |
| Nội dung Điều | `20.5.TT.48.1`, `20.5.TT.93.5` thiếu một phần (bảng, đoạn dán từ Word) | đủ nội dung |

`model_metadata.json` cũng còn ghi đường dẫn cũ (`labor_rag\data\ontology_v4\...`).

**Cách xử lý** (cần bật Docker):

```powershell
docker compose up -d
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --rebuild
```

Phải dùng `--rebuild`: bộ benchmark chỉ so tập MAPC để quyết định dùng lại
collection, nên nếu tập MAPC trùng mà text đã đổi, nó sẽ dùng lại vector cũ.
Sau đó chạy lại `notebooks/embedding_benchmark.ipynb` để cập nhật biểu đồ.

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

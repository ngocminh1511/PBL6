# Cấu trúc chunk JSONL (v5)

Mỗi dòng của `chunks.jsonl` là một chunk, dùng chung cho dữ liệu Bộ Pháp điển và PDF OCR.
Mô hình embedding: `BAAI/bge-m3`.

Nguyên tắc: **định danh theo văn bản gốc (số hiệu + số Điều), không theo nguồn dữ liệu.**
Cùng một Điều của cùng một văn bản luôn có cùng `chunk_id`, dù lấy từ Pháp điển hay PDF.

## 1. Bản ghi mẫu

```json
{
  "chunk_id": "45-2019-qh14:d1",
  "document_id": "45-2019-qh14",
  "mapc": "20.2.LQ.1",
  "source": "phap_dien",
  "ten": "Phạm vi điều chỉnh",
  "text": "Lao động > Bộ luật Lao động số 45/2019/QH14 > Chương I. NHỮNG QUY ĐỊNH CHUNG\nĐiều 1. Phạm vi điều chỉnh\nBộ luật Lao động quy định tiêu chuẩn lao động; ...",
  "meta_de_muc": "Bộ luật Lao động số 45/2019/QH14",
  "meta_chuong": "I",
  "meta_muc": null,
  "meta_dieu": "1",
  "meta_khoan": null,
  "effective_from_date": "2021-01-01",
  "still_valid": true
}
```

Phần thứ 2 của một Điều dài, lấy từ PDF:

```json
{
  "chunk_id": "12-2026-nd-cp:d35:p2",
  "document_id": "12-2026-nd-cp",
  "mapc": null,
  "source": "pdf",
  "ten": "Trợ cấp thôi việc",
  "text": "Nghị định số 12/2026/NĐ-CP > Chương III. CHẾ ĐỘ\nĐiều 35. Trợ cấp thôi việc\nNgười sử dụng lao động có trách nhiệm chi trả trợ cấp thôi việc như sau:\n4. ...\n5. ...",
  "meta_de_muc": "Nghị định số 12/2026/NĐ-CP",
  "meta_chuong": "III",
  "meta_muc": null,
  "meta_dieu": "35",
  "meta_khoan": "4-5",
  "effective_from_date": "2026-12-01",
  "still_valid": true
}
```

## 2. Danh sách trường

| Trường | Kiểu | Dùng cho | Cách lấy |
|---|---|---|---|
| `chunk_id` | string | Khóa chính | Mục 3.2 |
| `document_id` | string | Xóa/cập nhật/lọc theo văn bản | Mục 3.1 |
| `mapc` | string / null | Neo4j, bộ test | Mục 3.3 |
| `source` | `phap_dien` / `pdf` | Quy tắc nạp | Mục 7 |
| `ten` | string | LLM, UI | Tên Điều |
| `text` | string | Embedding, LLM | Mục 4 |
| `meta_de_muc` | string | Trích dẫn, lọc | Tên văn bản: loại + tên + số hiệu. Pháp điển: tiêu đề node văn bản trong KG. PDF: `FlatRecord.document_title` |
| `meta_chuong` | string / null | Lọc | Chỉ số hiệu (`"I"`). Pháp điển: `pChuong`. OCR: `chapter_number` |
| `meta_muc` | string / null | Lọc | Chỉ số hiệu (`"1"`). Pháp điển: `pMuc`. OCR: `section_number` |
| `meta_dieu` | string / null | Trích dẫn, gom phần, tra `mapc` | Số Điều trong **văn bản gốc**. `null` với phần mở đầu / phụ lục |
| `meta_khoan` | string / null | Trích dẫn | Khoảng khoản `"đầu-cuối"` của chunk khi Điều bị cắt (`"1-8"`, `"9-14"`); chỉ một khoản thì `"3"`; `null` nếu chunk là cả Điều |
| `effective_from_date` | `YYYY-MM-DD` / null | Lọc hiệu lực | Mục 6 |
| `still_valid` | bool | Lọc hiệu lực | Mục 6 |

Trích dẫn ghép lúc dựng prompt:
`Điều {meta_dieu}[ khoản {meta_khoan}] {meta_de_muc}` -> `Điều 35 khoản 4-5 Nghị định số 12/2026/NĐ-CP`.

## 3. Định danh

### 3.1. `document_id`

Chuẩn hóa từ số hiệu văn bản:

```python
def make_document_id(so_hieu: str) -> str:
    # "45/2019/QH14" -> "45-2019-qh14"; "145/2020/NĐ-CP" -> "145-2020-nd-cp"
    s = so_hieu.strip().lower().replace("đ", "d")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")
```

- Pháp điển: `document_number` của văn bản trong KG.
- PDF: regex `Số:\s*([\w/.-]+)` ở trang đầu. Nếu không đọc được thì dùng `doc-<sha1 file>[:12]`.

### 3.2. `chunk_id`

```
{document_id}:{đơn vị}[:p{k}]
```

| Đơn vị | Ví dụ |
|---|---|
| Điều | `45-2019-qh14:d1` |
| Điều có chữ (4a, 35đ; `đ` -> `dd`) | `45-2019-qh14:d35dd` |
| Phần mở đầu | `145-2020-nd-cp:preamble` |
| Phụ lục | `10-2020-tt-bldtbxh:pl2` |
| Phần thứ k của Điều bị cắt | `45-2019-qh14:d35:p2` |

- Số Điều lấy từ ghi chú nguồn (`codificationOf` trong KG), **không** lấy phần cuối của mã pháp điển.
- Qdrant point id: `uuid5(NAMESPACE_URL, chunk_id)`.

### 3.3. `mapc`

| Trường hợp | Giá trị |
|---|---|
| Pháp điển | Mã pháp điển (`20.2.LQ.1`) |
| PDF của văn bản đã có trong Pháp điển | Tra `(document_id, meta_dieu) -> mapc` từ KG |
| PDF của văn bản mới | `null`. Không mở rộng đồ thị, các bước khác chạy bình thường |

Mọi phần `:p{k}` của một Điều dùng chung một `mapc`.

## 4. Dựng trường `text`

```
{ngữ cảnh}
Điều {meta_dieu}. {ten}
{nội dung}
```

| Nguồn | Ngữ cảnh |
|---|---|
| Pháp điển | `{đề mục} > {meta_de_muc} > Chương {số}. {tên chương}[ > Mục {số}. {tên mục}]` |
| PDF | `{meta_de_muc} > Chương {số}. {tên chương}[ > Mục {số}. {tên mục}]` |

Quy tắc:
- **Phải có tên văn bản** trong ngữ cảnh. Nhiều văn bản có Điều trùng tên ("Phạm vi điều chỉnh", "Đối tượng áp dụng"), nên thiếu tên văn bản thì vector không phân biệt được.
- **Không** đưa mã pháp điển (`Điều 20.2.LQ.1`) vào `text`.
- Chuẩn hóa `unicodedata.normalize("NFC", text)`. OCR có thể trả về dấu tổ hợp, làm tokenizer tách khác với Pháp điển.
- bge-m3 không cần prefix `query:` / `passage:` và không cần tách từ (pyvi).

## 5. Cắt Điều dài

`MAX_TOKENS = 1024`, đếm bằng tokenizer bge-m3 và tính cả phần đầu.
Với dữ liệu hiện tại có khoảng 38/1407 Điều bị cắt; trung vị là 225 token.

### 5.1. Thuật toán

Điều được tách thành: **phần đầu** (ngữ cảnh + `Điều n. Tên`), **câu dẫn** (đoạn trước khoản 1,
vd "Người lao động có các quyền sau đây:"), và **danh sách khoản**.

1. `len(text) <= MAX_TOKENS` thì giữ nguyên cả Điều, không thêm `:p{k}`.
2. Ngược lại, ngân sách mỗi phần là `budget = MAX_TOKENS - len(phần đầu) - len(câu dẫn)`.
3. **Cắt theo khoản:** gom các khoản liên tiếp vào một phần cho tới khi vượt `budget`. Không cắt giữa một khoản.
4. **Khoản quá dài** (một khoản > `budget`): cắt tiếp theo **điểm** (a, b, c...).
   Mỗi phần con lặp lại câu dẫn của khoản (vd "3. Các trường hợp sau đây:").
5. **Điểm quá dài** hoặc đoạn không có khoản/điểm (phụ lục, bảng): cắt theo **câu**,
   gối đầu 1-2 câu (khoảng 64 token) giữa hai phần liền nhau.
6. **Cân bằng:** số phần `k = ceil(tổng / budget)`, rồi gom sao cho mỗi phần gần `tổng / k`,
   tránh phần cuối chỉ còn vài chục token.

Chỉ gối đầu ở bước 5. Ranh giới khoản/điểm là ranh giới tự nhiên nên không cần gối đầu.

### 5.2. Mỗi phần chứa gì

| | Phần 1 | Phần k > 1 |
|---|---|---|
| Phần đầu (ngữ cảnh + `Điều n. Tên`) | Có | **Lặp lại** |
| Câu dẫn của Điều | Có | **Lặp lại** |
| Câu dẫn của khoản (khi cắt theo điểm) | Có | **Lặp lại** |
| `chunk_id` | `...:d35:p1` | `...:d35:p{k}` |
| `meta_khoan` | `"1-3"` | `"4-5"` |
| Các trường khác | Giống nhau ở mọi phần | |

```python
def split_article(header, lead, clauses, count, max_tokens=1024):
    budget = max_tokens - count(header) - count(lead)
    units = []                                   # (nhãn khoản, đoạn văn)
    for no, body in clauses:
        if count(body) <= budget:
            units.append((no, body))
        else:                                    # khoản quá dài -> cắt theo điểm / câu
            units += [(no, piece) for piece in split_clause(body, budget, count)]
    parts = balanced_pack(units, budget, count)  # bước 6
    return [
        {"text": "\n".join([header, lead, *(u for _, u in part)]).strip(),
         "meta_khoan": khoan_range([n for n, _ in part])}
        for part in parts
    ]
```

### 5.3. Khi retrieval

- **Gom theo Điều:** khóa Điều là `chunk_id.split(":p")[0]`. Nhiều phần của cùng Điều cùng lọt top-k
  thì tính là **một** kết quả, lấy điểm cao nhất. Bộ test chấm theo `mapc` cũng gom như vậy.
- **Đưa cho LLM:** dùng phần trúng kết quả. Nếu cần cả Điều thì lấy đủ các phần bằng filter
  `document_id = X AND meta_dieu = Y`, sắp theo `k` rồi nối lại, bỏ phần đầu và câu dẫn bị lặp.

## 6. Hiệu lực

| Trường | Ý nghĩa | Pháp điển | PDF |
|---|---|---|---|
| `effective_from_date` | Ngày bắt đầu có hiệu lực | `effective_date` của văn bản trong KG | Regex `có hiệu lực (?:thi hành )?(?:kể )?từ ngày (\d{1,2}/\d{1,2}/\d{4})`; không thấy thì `null` |
| `still_valid` | Đã bị bãi bỏ/thay thế chưa | Luôn `true` | `true` lúc nạp; đổi thành `false` khi nạp văn bản bãi bỏ/thay thế nó |

Filter lúc truy vấn:
`still_valid = true AND (effective_from_date <= hôm nay OR effective_from_date IS NULL)`.

Khi `still_valid` thay đổi thì cập nhật payload (Qdrant `set_payload` theo `document_id`), không cần embedding lại.

## 7. Quy tắc nạp

- Trùng `chunk_id` giữa Pháp điển và PDF thì **giữ bản Pháp điển**, vì bản này đã cập nhật các lần sửa đổi.
- PDF nạp lại: xóa mọi chunk có cùng `document_id` rồi nạp lại.
- Văn bản sửa đổi, bổ sung có số hiệu riêng, nên là văn bản riêng.

## 8. Ánh xạ từ OCR (`labor_rag/ocr/schemas.py::FlatRecord`)

| Chunk v5 | FlatRecord |
|---|---|
| `document_id` | `make_document_id(số hiệu)`. Hiện đang là tên file, cần đổi |
| `meta_de_muc` | `document_title` |
| `meta_chuong` / `meta_muc` / `meta_dieu` | `chapter_number` / `section_number` / `article_number` |
| `ten` | `article_title` |

Các bản ghi mức khoản/điểm (`level = clause/point`) phải gộp về mức Điều trước, rồi cắt theo mục 5.

## 9. Prompt cho LLM

```text
[Điều {meta_dieu}[ khoản {meta_khoan}] {meta_de_muc}] {ten}
Nội dung: {text}
```

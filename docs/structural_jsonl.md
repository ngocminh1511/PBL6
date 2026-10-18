# Cấu trúc chunk JSONL (v5)

Mỗi dòng của `chunks.jsonl` là một chunk, dùng chung cho dữ liệu Bộ Pháp điển và PDF OCR.
Mô hình embedding: `BAAI/bge-m3`.

Nguyên tắc: **định danh theo văn bản gốc (số hiệu + số Điều), không theo nguồn dữ liệu.**
Cùng một Điều của cùng một văn bản luôn có cùng `chunk_id`, dù lấy từ Pháp điển hay PDF.

## 1. Bản ghi mẫu

Lấy từ Pháp điển (Điều 10 của NĐ 145/2020, xếp vào Chương III, Mục 4 của đề mục "Lao động"):

```json
{
  "chunk_id": "145-2020-nd-cp:d10",
  "document_id": "145-2020-nd-cp",
  "mapc": "20.2.NĐ.3.10",
  "source": "phap_dien",
  "ten": "...",
  "text": "Lao động > Nghị định số 145/2020/NĐ-CP > Chương III. HỢP ĐỒNG LAO ĐỘNG > Mục 4. HỢP ĐỒNG LAO ĐỘNG VÔ HIỆU\nĐiều 10. ...\n...",
  "meta_de_muc": "Nghị định số 145/2020/NĐ-CP",
  "meta_chuong": null,
  "meta_muc": null,
  "pd_chuong": "III",
  "pd_muc": "4",
  "meta_dieu": "10",
  "meta_khoan": null,
  "effective_from_date": "2021-02-01",
  "effective_to_date": null,
  "version_date": "2021-02-01",
  "still_valid": true,
  "content_hash": "3f1c0a9e7b2d4c51"
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
  "pd_chuong": null,
  "pd_muc": null,
  "meta_dieu": "35",
  "meta_khoan": "4-5",
  "effective_from_date": "2026-12-01",
  "effective_to_date": null,
  "version_date": "2026-12-01",
  "still_valid": true,
  "content_hash": "9a0b7c3d2e1f4a5b"
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
| `meta_de_muc` | string | Trích dẫn, lọc | Tên văn bản (loại + số hiệu, kèm tên nếu có). Pháp điển: `vld:title` của văn bản trong KG. PDF: `FlatRecord.document_title` |
| `meta_chuong` | string / null | Lọc | Chương của **văn bản gốc**, chỉ số hiệu (`"I"`). OCR: `chapter_number`. Pháp điển: `null` (KG không có chương của văn bản gốc) |
| `meta_muc` | string / null | Lọc | Mục của **văn bản gốc** (`"1"`). OCR: `section_number`. Pháp điển: `null` |
| `pd_chuong` | string / null | Ngữ cảnh, UI | Chương của **đề mục Pháp điển** chứa Điều (`"III"`), lấy từ heading trong KG. PDF: `null` |
| `pd_muc` | string / null | Ngữ cảnh, UI | Mục của đề mục Pháp điển (`"4"`). PDF: `null` |
| `meta_dieu` | string / null | Trích dẫn, gom phần, tra `mapc` | Số Điều trong **văn bản gốc**. `null` với phần mở đầu / phụ lục |
| `meta_khoan` | string / null | Trích dẫn | Khoảng khoản `"đầu-cuối"` của chunk khi Điều bị cắt (`"1-8"`, `"9-14"`); chỉ một khoản thì `"3"`; `null` nếu chunk là cả Điều |
| `effective_from_date` | `YYYY-MM-DD` / null | Lọc hiệu lực | Mục 6 |
| `effective_to_date` | `YYYY-MM-DD` / null | Lịch sử | Mục 6 |
| `version_date` | `YYYY-MM-DD` / null | Chọn bản khi trùng | Ngày hiệu lực mới nhất mà nội dung đã phản ánh. Mục 7 |
| `still_valid` | bool | Lọc hiệu lực | Mục 6 |
| `content_hash` | string | Phát hiện Điều thay đổi | sha1 (16 ký tự hex) của **nội dung** Điều (không gồm phần đầu), sau khi chuẩn hóa NFC và gộp khoảng trắng. Mọi phần của một Điều có cùng giá trị |

Quan hệ sửa đổi và thay thế **không nằm trong chunk**: chúng ở đồ thị (ABox -> Neo4j), mục 10. Payload chỉ giữ
những gì cần để lọc lúc tìm vector (`effective_from_date`, `effective_to_date`, `still_valid`), sinh ra từ đồ thị.

**Chương của văn bản gốc và chương Pháp điển là hai thứ khác nhau.** Pháp điển xếp Điều của
nghị định, thông tư vào khung chương của đề mục (lấy theo Bộ luật), nên Điều 10 NĐ 145/2020 nằm ở
"Chương III. HỢP ĐỒNG LAO ĐỘNG" của đề mục, còn trong chính Nghị định thì ở chương khác.
Không dùng chương để so khớp hay cập nhật; định danh luôn là `(document_id, meta_dieu)`.

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
- PDF: regex `số\s*:?\s*(\d+/\d{4}/[\w-]+)` (không phân biệt hoa thường, bắt cả "Luật số: ...") ở trang đầu,
  kiểm tra khuôn `số/năm/ký hiệu`. Nếu không đọc được thì dùng `doc-<sha1 của text trích được>[:12]`.
- OCR hay đọc `Đ` thành `Ð` (chữ Iceland); `make_document_id` đổi về `Đ` trước khi chuẩn hóa.

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

- Số Điều lấy từ ghi chú nguồn: `codificationOf` -> `vld:Article` có `vld:itemNumber` (do `build_abox` ghi),
  **không** lấy phần cuối của mã pháp điển.
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
| Pháp điển | `{đề mục} > {meta_de_muc} > {các heading Pháp điển: Phần / Chương / Mục ...}` (chương, mục của đề mục, tức `pd_chuong`, `pd_muc`) |
| PDF | `{meta_de_muc} > Chương {số}. {tên chương}[ > Mục {số}. {tên mục}]` |

Quy tắc:
- **Phải có tên văn bản** trong ngữ cảnh. Nhiều văn bản có Điều trùng tên ("Phạm vi điều chỉnh", "Đối tượng áp dụng"), nên thiếu tên văn bản thì vector không phân biệt được.
- **Không** đưa mã pháp điển (`Điều 20.2.LQ.1`) vào `text`.
- Chuẩn hóa `unicodedata.normalize("NFC", text)`. OCR có thể trả về dấu tổ hợp, làm tokenizer tách khác với Pháp điển.
- bge-m3 không cần prefix `query:` / `passage:` và không cần tách từ (pyvi).

## 5. Cắt Điều dài

`MAX_TOKENS = 1024`, đếm bằng tokenizer bge-m3 và tính cả phần đầu.
Với dữ liệu Lao động hiện tại (`lao_dong_v5`): 38/1407 Điều bị cắt, ra 1481 chunk; chunk dài nhất 1017 token,
trung vị 242 token.

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
| `effective_from_date` | Ngày bắt đầu có hiệu lực | `effective_date` của văn bản trong KG | `effective_date` trong KG nếu văn bản đã có trong Pháp điển; không thì `metadata.ngay_hieu_luc` (`ocr/structure.py`): câu dẫn VBHN, hoặc câu "… này có hiệu lực (thi hành) (kể) từ ngày …" dạng `dd/mm/yyyy` hay `ngày dd tháng mm năm yyyy`; không thấy thì `null` |
| `effective_to_date` | Ngày hết hiệu lực | `vlt:validTo` của văn bản (khoảng hiệu lực `vlt:LegalValidityInterval`); `null` khi chưa bị thay thế | Như Pháp điển, đọc từ `kg_nodes` (`VanBan.valid_to`) |
| `still_valid` | Cờ loại thủ công | `true` | `true` |

`vlt:validTo` do ABox của văn bản thay thế ghi (mục 10). `embed_and_index` mỗi lần chạy chép `VanBan.valid_to` trong
`kg_nodes.jsonl` sang `effective_to_date` của mọi chunk văn bản đó (Qdrant `set_payload` theo `document_id`, không
embedding lại).

Filter lúc truy vấn (`hybrid_retrieve.in_force`):
`still_valid = true AND (effective_from_date <= hôm nay OR IS NULL) AND (effective_to_date > hôm nay OR IS NULL)`.
Điều kiện cuối giữ văn bản cũ đến đúng ngày văn bản mới có hiệu lực, kể cả khi nạp văn bản mới trước ngày đó.

## 7. Quy tắc nạp

Code: `labor_rag/ingest/merge.py::plan_upsert`, chạy bởi `embed_and_index --upsert`.

- Quyết định **theo từng Điều** (`chunk_id` bỏ `:p{k}`), không theo từng phần, để một Điều không bao giờ
  lẫn phần của hai nguồn.
- Điều có ở cả hai bên với cùng các phần và cùng `text`: không embedding lại. Nếu chỉ metadata đổi (`version_date`,
  `effective_to_date`, …) và bên mới là nạp lại cùng nguồn hoặc thắng, ghi đè payload (`overwrite_payload`).
- Điều có ở cả hai bên, nội dung khác: bên có **`version_date` lớn hơn thắng**. Bằng nhau thì Pháp điển thắng PDF;
  cùng nguồn (nạp lại) thì bản mới thay bản cũ.
- Bên mới thắng: **xóa mọi phần cũ** của Điều rồi mới ghi, vì hai bên có thể cắt Điều thành số phần khác nhau.
- Điều chỉ có ở bản đang index: giữ nguyên, in cảnh báo (thường do OCR bỏ sót Điều).
- Dựng lại collection (`embed_and_index` không có `--upsert`) sẽ xóa luôn chunk PDF, nên lệnh dừng lại khi collection có
  chunk không phải Pháp điển. Thêm `--recreate` để vẫn dựng lại, rồi chạy lại `--upsert`. `--upsert` không embedding lại
  Điều có `text` không đổi, nên khi đổi model phải dùng `--recreate`.
- Văn bản sửa đổi, bổ sung có số hiệu riêng, nên là văn bản riêng.

`version_date` (`YYYY-MM-DD`): ngày hiệu lực mới nhất mà nội dung đã phản ánh.

| Nguồn | Cách tính |
|---|---|
| Pháp điển | max(`effective_date` của văn bản, `vlt:amendsAt` của các `AmendmentEvent` của **chính Điều đó** có `vlpd:consolidatedInCodification = true`). Ghi chú nguồn trong HTML nêu Điều nào sửa Điều này ("được sửa đổi … bởi Điều X …"), nên Điều không bị sửa giữ ngày hiệu lực gốc; sửa đổi nạp sau từ PDF không tính vì chưa có trong nội dung |
| PDF văn bản gốc | Ngày hiệu lực ("… này có hiệu lực (thi hành) từ ngày …") |
| PDF VBHN | max(ngày hiệu lực văn bản gốc, ngày hiệu lực từng văn bản sửa đổi trong câu dẫn "…, được sửa đổi, bổ sung bởi: 1. … 2. …") |

Ví dụ: Pháp điển trong repo có Bộ luật Lao động với `version_date = 2021-01-01`; VBHN `docs/Luat_lao_dong.pdf`
(sửa đổi bởi 3 luật năm 2025) có `2026-07-01`, nên các Điều của VBHN thay bản Pháp điển.

## 8. Từ OCR sang chunk (`labor_rag/ingest/pdf_to_chunks.py`)

Đầu vào là cây `LegalDocument` của OCR (không dùng `FlatRecord`/`chunk_long_records`).

| Chunk v5 | Lấy từ |
|---|---|
| `document_id` | `make_document_id(metadata.so_hieu)`; không có thì `doc-<sha1>` |
| `meta_de_muc` | Tên văn bản trong KG nếu văn bản đã có trong Pháp điển (để trùng với chunk Pháp điển); không thì `"{loai_van_ban} số {so_hieu}"` |
| `meta_chuong` / `meta_muc` | `heading_number(chapter_number / section_number)`: `"Chương I"` -> `"I"` |
| `meta_dieu` | `article_number` bỏ `"Điều "`: `"Điều 35a"` -> `"35a"` |
| `ten` | `article_title` |
| `mapc` | KG: `(document_id, article_number)` của node Dieu -> `mapc`; Điều không có trong Pháp điển thì `null` |
| `effective_from_date` | KG nếu có, không thì `metadata.ngay_hieu_luc` |
| `effective_to_date` | KG (`VanBan.valid_to`) nếu văn bản đã bị thay thế |
| `version_date` | `metadata.version_date` (mục 7) |

Cùng lúc, `pdf_to_chunks` ghi ABox của văn bản ra `ontology/abox/pdf/<document_id>.ttl` (`pdf_abox.py`): văn bản,
các Điều (`vld:Article`, `vld:heading`), và những gì văn bản thay đổi ở văn bản khác (mục 10). URI giống ABox Pháp điển,
nên `ontology_to_jsonl` ghép vào cùng một đồ thị.

- Thân Điều dựng lại thành từng dòng: câu dẫn, `"1. …"`, `"a) …"` (cây OCR bỏ các ký hiệu này), rồi cắt theo mục 5.
- Phụ lục: OCR gộp mọi phụ lục thành một khối -> chunk `{document_id}:pl1` (cắt nếu dài). Phần mở đầu không thành chunk.
- Hai Điều cùng số (thường do OCR đọc sai số) -> giữ Điều đầu, in cảnh báo.
- **VBHN**: nhận ra qua số `xx/VBHN-…` hoặc câu "được sửa đổi, bổ sung bởi:". Số hiệu dùng làm `document_id` là
  số của văn bản gốc (VBHN mang số hiệu gốc trong câu dẫn), không phải số VBHN.
- **Chú thích cuối trang** (`cleaner.split_footnotes`): khối dòng cuối trang bắt đầu bằng số chú thích, các số tăng
  liên tiếp và có từ khóa sửa đổi/căn cứ ban hành, được cắt khỏi nội dung và ghi ra `{document_id}_footnotes.jsonl`
  (`{page, number, text}`). Chưa đọc thông tin sửa đổi từ chú thích.

## 9. Prompt cho LLM

```text
[Điều {meta_dieu}[ khoản {meta_khoan}] {meta_de_muc}] {ten}
Nội dung: {text}
```

## 10. Cập nhật văn bản

So sánh bản cũ và bản mới **luôn theo `(document_id, meta_dieu)`**, không theo chương hay `mapc`.

| Trường hợp | Ví dụ | Cách làm |
|---|---|---|
| Nạp lại cùng văn bản | PDF NĐ 145/2020 OCR lại | Cùng `document_id` nên `chunk_id` khớp 1-1. `chunk_id` chỉ có ở bản mới: Điều mới. Chỉ có ở bản cũ: Điều bị mất (thường do OCR, cần cảnh báo). Có ở cả hai: so `content_hash`, chỉ embedding lại Điều đổi hash |
| Văn bản sửa đổi, bổ sung | "Sửa đổi khoản 2 Điều 35 Nghị định 145/2020/NĐ-CP" | Văn bản riêng, `document_id` riêng. Xem "Văn bản sửa đổi" bên dưới |
| Văn bản thay thế | NĐ mới "thay thế Nghị định 145/2020/NĐ-CP" | Không so theo Điều được (đánh số lại). Xem "Văn bản thay thế" bên dưới. Nếu cần ghép Điều cũ - Điều mới để hiển thị thì dùng tên Điều + cosine |

- **Không xóa bản cũ**: văn bản bị thay thế chỉ có thêm `effective_to_date`, vẫn trả lời được "trước đây quy định thế
  nào" và so được phiên bản. Filter mặc định ở mục 6 đã loại bản cũ khỏi truy vấn thường.

**Đồ thị là nơi giữ quan hệ.** Sửa đổi và thay thế nằm trong ABox (Pháp điển: `build_abox`; mỗi PDF:
`ontology/abox/pdf/<document_id>.ttl`), được `ontology_to_jsonl` ghép lại và `load_neo4j` nạp vào Neo4j:

```text
(:SourceComponent {document_id, article_number})              Điều bị sửa
   -[:HAS_AMENDMENT]-> (:AmendmentEvent {actions, scope, date, consolidated})
   -[:AMENDING_COMPONENT]-> (:SourceComponent {document_id, article_number, clause_number})   Điều / khoản sửa
(:VanBan {document_id, valid_to}) -[:REPLACES]-> (:VanBan)      văn bản thay thế
```

- `actions`: `sua_doi`, `bo_sung`, `bai_bo`, `thay_cum_tu`. `scope`: phần bị sửa (`"khoản 2"`), không có khi nguồn chỉ
  nêu Điều (luôn vậy với Pháp điển). `date`: ngày văn bản sửa đổi có hiệu lực.
- `consolidated = true`: Pháp điển đã hợp nhất sửa đổi này vào nội dung Điều (lấy từ ghi chú nguồn "được sửa đổi … bởi
  Điều X …"). Chỉ các sửa đổi này được tính vào `version_date` (mục 7).
- Retrieval (`hybrid_retrieve.attach_amendments`): với mỗi Điều trả về, hỏi Neo4j các `AmendmentEvent` có `date` >
  `version_date` của chunk (sửa đổi chưa có trong nội dung), lấy chunk của Điều / khoản sửa đổi (lọc `document_id`,
  `meta_dieu`, `meta_khoan`) và gắn vào `Evidence.amendments`. Prompt đặt chúng ngay dưới Điều gốc
  ("Được sửa đổi bởi … (sửa đổi, bổ sung khoản 2)") và yêu cầu áp dụng quy định sửa đổi thay cho nội dung gốc.

**Văn bản sửa đổi** (PDF, `labor_rag/ingest/amending.py`, `pdf_abox.py`):

1. `pdf_to_chunks`: Điều có tên bắt đầu bằng "Sửa đổi / Bổ sung / Bãi bỏ / Thay (thế) cụm từ" được cắt **theo từng
   khoản** (khoản dài thì cắt tiếp). Mỗi phần có dòng ngữ cảnh "Sửa đổi, bổ sung khoản 2 Điều 3 Nghị định số
   152/2020/NĐ-CP (Điều 3. <tên>)" ngay sau phần đầu; `meta_khoan` = số khoản của Điều sửa đổi.
2. ABox của PDF: mỗi khoản là một `vld:Clause`; phần lệnh của khoản (trước "như sau", bỏ cụm trong ngoặc kép) cho Điều
   đích, `scope`, `actions` -> một `AmendmentEvent` cho mỗi Điều đích. Văn bản đích là văn bản nêu trong khoản, nếu
   không có thì lấy văn bản nêu trong tên Điều. "Bổ sung Điều 35a vào sau Điều 35": đích là Điều 35, `scope = "Điều 35a"`.
- Chỉ nạp văn bản sửa đổi khi chưa có VBHN. Không tự áp nội dung sửa đổi vào Điều cũ: khi có VBHN / Pháp điển mới,
  `version_date` của Điều mới ≥ `date` nên chunk sửa đổi tự không còn bị kéo theo.

**Văn bản thay thế**: trong Điều có tên chứa "hiệu lực / thi hành / chuyển tiếp", câu có "thay thế / hết hiệu lực" nêu
văn bản nào thì ABox của PDF ghi `vlr:replaces` và `vlt:validTo` = ngày hiệu lực của văn bản mới trên khoảng hiệu lực của
văn bản cũ. Từ đó ra `VanBan.valid_to` và `effective_to_date` (mục 6). Dữ liệu Pháp điển không có quan hệ này (Pháp
điển chỉ giữ văn bản còn hiệu lực), nên nó chỉ đến từ văn bản nạp sau.

**Thứ tự nạp một PDF**:

```powershell
python -m labor_rag.ingest.pdf_to_chunks --input <file>.pdf        # chunk + ontology/abox/pdf/<doc>.ttl
python -m labor_rag.ingest.ontology_to_jsonl                       # ghép ABox, chiếu lại kg_nodes/edges + chunks
python -m labor_rag.ingest.load_neo4j --replace-dataset
python -m labor_rag.ingest.embed_and_index --chunks data/processed/lao_dong_v5/chunks.jsonl --upsert   # chỉ cập nhật metadata
python -m labor_rag.ingest.embed_and_index --chunks data/interim/pdf_chunks/<doc>_chunks.jsonl --upsert
```

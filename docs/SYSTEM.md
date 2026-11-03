# Hệ thống KG-RAG pháp luật lao động: cách hoạt động

Tài liệu duy nhất mô tả hệ thống: dữ liệu đi từ đâu, được chuẩn hóa thế nào, nạp vào đâu, và một câu hỏi được trả lời ra
sao. Cách cài đặt và chạy nhanh xem `README.md`.

Cập nhật: 2026-11-03.

---

## 1. Tổng quan

```text
Pháp điển HTML ─ parse_demuc_html ─ build_abox ─► ontology/abox/abox_lao_dong.ttl ─┐
PDF (OCR)      ─ pdf_to_chunks ──────────────────► ontology/abox/pdf/<doc>.ttl ─────┤
                                                                                    ▼
                                                     ontology_to_jsonl ─► data/processed/lao_dong_v5/
                                                                            ├─ chunks.jsonl ─ embed_and_index ─► Qdrant
                                                                            └─ kg_nodes / kg_edges.jsonl ─ load_neo4j ─► Neo4j
Phụ lục (vbpl.vn) ─ collect ─ extract ─ graph / index ─► data/processed/appendices_v1/ ─► Neo4j + Qdrant (bổ sung)

Câu hỏi ─ query_rewrite ─ hybrid_retrieve (Qdrant + Neo4j) ─ rerank ─ answer (LLM) ─ citation_verify ─► câu trả lời
```

Nguyên tắc chung:

- **ABox (Turtle) là bản gốc** của dữ liệu pháp lý. JSONL trong `data/processed/lao_dong_v5/` chỉ là bản chiếu có phiên
  bản để nạp Neo4j và Qdrant.
- **Đồ thị giữ quan hệ** (cấu trúc, sửa đổi, thay thế, dẫn chiếu). **Qdrant chỉ giữ nội dung và các trường cần lọc**.
- **Định danh theo văn bản gốc** (`document_id` + số Điều), không theo nguồn dữ liệu hay mã Pháp điển.
- Hai hệ số phiên bản độc lập: **schema ontology v4** (`ontology/schema/vn_legal_ontology_schema_v4.ttl`) và
  **dataset `lao_dong_v5`** (bản chiếu đang dùng). Phụ lục dùng schema riêng `vn_legal_appendix_schema_v1.ttl`.

| Thành phần | Công nghệ |
|---|---|
| Embedding | `BAAI/bge-m3` (1.024 chiều, đọc tới 8.192 token), chạy local hoặc trên Modal |
| Vector DB | Qdrant (Cloud, strict mode), collection `legal_ld_v5_bge` |
| Graph DB | Neo4j (Aura), dataset `lao_dong_v5` |
| LLM | qua `labor_rag/generation/llm_client.py` (cấu hình trong `.env`) |
| Lưu file phụ lục | Local, đồng bộ chủ động lên Cloudflare R2 |
| Giao diện | FastAPI `labor_rag/app/api.py` + trang tĩnh `labor_rag/app/static/`; REPL `labor_rag/app/chat.py` |

---

## 2. Dữ liệu nguồn

| Nguồn | Vị trí | Ghi chú |
|---|---|---|
| Bộ Pháp điển (offline) | `data/raw/bophapdien/` (`jsonData.js`, `linh_vuc/*.html`) | Chủ đề 20 "Lao động": 1.407 Điều thuộc 4 đề mục 20.2–20.5 (20.1 Giáo dục nghề nghiệp rỗng) |
| PDF văn bản hợp nhất | `docs/Luat_lao_dong.pdf` | VBHN Bộ luật Lao động 2019, bản scan 86 trang, phải OCR |
| Phụ lục | `data/raw/appendix/<document_id>/` | Tải từ vbpl.vn (mục 7) |

**Mã Pháp điển** `20.2.TT.1.8`: đề mục `20.2`, loại văn bản `TT` (`LQ` Luật, `NĐ`, `TT`, `QĐ`, `TL`…), `1` là STT văn bản
loại đó trong đề mục (**không phải số hiệu**, Pháp điển tự gán và có thể đánh lại), `8` là số Điều. Số hiệu thật lấy từ
ghi chú nguồn `pGhiChu` dưới tiêu đề, ví dụ `(Điều 8 Thông tư số 09/2020/TT-BLĐTBXH, có hiệu lực …)`.

Pháp điển đặt Điều của NĐ/TT ngay sau Điều luật mà nó hướng dẫn. Ngoại lệ: Điều "Phạm vi điều chỉnh" / "Đối tượng áp
dụng" của các NĐ/TT được gom thành một cụm sau `LQ.2` nhưng không hướng dẫn `LQ.2`. Vì vậy hệ thống **không** suy ra
quan hệ hướng dẫn từ vị trí; quan hệ chỉ lấy từ ghi chú "nội dung liên quan" và câu chữ (mục 6).

---

## 3. Ontology và ABox

```powershell
python -m labor_rag.ingest.build_abox --chu-de 20 --output ontology/abox/abox_lao_dong.ttl
python scripts/validate_abox.py --report ontology/reports/validation_report.json   # SHACL
python tests/test_cq_v4.py                                                          # competency questions
python -m labor_rag.ingest.ontology_to_jsonl                                        # ghép ABox -> lao_dong_v5
```

`build_abox` đọc HTML trong bộ nhớ (`parse_demuc_html.parse_demuc_nodes`), không ghi JSON trung gian. ABox Lao động hiện
có 58.215 triple, SHACL 0 vi phạm; bản chiếu có 11.744 node, 33.357 cạnh. `ontology_to_jsonl` ghép ABox Pháp điển với
mọi `ontology/abox/pdf/*.ttl` (cùng URI) thành một đồ thị.

Mô hình đồ thị (tên nhãn trong Neo4j):

```text
(:VanBan {document_id, valid_from, valid_to, short_title}) -[:REPLACES]-> (:VanBan)     thay thế (chỉ từ PDF)
(:Dieu {id: mapc}) -[:REFERS_TO]-> (:Dieu)                                              "nội dung liên quan" của Pháp điển
(Chương/Mục) -[:CONTAINS]-> (:Dieu)                                                     cấu trúc đề mục
(:SourceComponent {document_id, article_number})                                        Điều của văn bản nguồn
   -[:CONTAINS]-> (:SourceComponent {clause_number, text})                              khoản (có text)
   -[:CONTAINS]-> (:SourceComponent {point_number})                                     điểm (khi được dẫn chiếu)
(:SourceComponent) -[:HAS_AMENDMENT]-> (:AmendmentEvent {actions, scope, date, consolidated})
   -[:AMENDING_COMPONENT]-> (:SourceComponent)                                          Điều / khoản sửa đổi
(:SourceComponent) -[:CITES_COMPONENT | IMPLEMENTS_COMPONENT]-> (:SourceComponent)      dẫn chiếu trong câu chữ
```

- URI: `Doc_Decree_145_2020_ND_CP`, `SourceArticle_<văn bản>_D35`, `SourceClause_..._D35_K2`, `SourcePoint_..._K2_Pa`,
  `Amendment_<Điều bị sửa>_by_<Điều/khoản sửa>`, `Validity_<văn bản>`.
- Text cấp Điều **không** lưu trong Neo4j (lấy từ payload Qdrant). Text cấp khoản lưu trong Neo4j để khi có dẫn chiếu
  tới đúng một khoản thì chỉ đưa khoản đó vào prompt.

---

## 4. Chunk v5 (`chunks.jsonl`)

Code: `labor_rag/ingest/chunk_schema.py`, `ontology_to_jsonl.py`, `pdf_to_chunks.py`. Mỗi dòng là một chunk, dùng chung
cho Pháp điển và PDF. Dữ liệu hiện tại: 1.407 Điều → 1.481 chunk (38 Điều dài bị cắt), dài nhất 1.017 token, trung vị
242 token.

### 4.1. Bản ghi mẫu

```json
{
  "chunk_id": "145-2020-nd-cp:d10",
  "document_id": "145-2020-nd-cp",
  "mapc": "20.2.NĐ.3.10",
  "source": "phap_dien",
  "ten": "...",
  "text": "Lao động > Nghị định số 145/2020/NĐ-CP > Chương III. HỢP ĐỒNG LAO ĐỘNG > Mục 4. ...\nĐiều 10. ...\n...",
  "meta_de_muc": "Nghị định số 145/2020/NĐ-CP",
  "meta_chuong": null, "meta_muc": null,
  "pd_chuong": "III", "pd_muc": "4",
  "meta_dieu": "10", "meta_khoan": null,
  "effective_from_date": "2021-02-01", "effective_to_date": null,
  "version_date": "2021-02-01", "still_valid": true,
  "content_hash": "3f1c0a9e7b2d4c51"
}
```

### 4.2. Các trường

| Trường | Ý nghĩa |
|---|---|
| `chunk_id` | Khóa chính, `{document_id}:{đơn vị}[:p{k}]` (mục 4.3) |
| `document_id` | Chuẩn hóa từ số hiệu: `145/2020/NĐ-CP` → `145-2020-nd-cp` |
| `mapc` | Mã Pháp điển, để nối Neo4j và chấm benchmark. PDF của văn bản đã có trong Pháp điển: tra `(document_id, meta_dieu)` trong KG; văn bản mới: `null` |
| `source` | `phap_dien` / `pdf` |
| `ten`, `text` | Tên Điều; đầu vào embedding (mục 4.4) |
| `meta_de_muc` | Tên văn bản (loại + số hiệu) |
| `meta_chuong`, `meta_muc` | Chương/mục của **văn bản gốc**. Chỉ PDF có; Pháp điển luôn `null` |
| `pd_chuong`, `pd_muc` | Chương/mục của **đề mục Pháp điển** chứa Điều. PDF: `null` |
| `meta_dieu` | Số Điều trong văn bản gốc (lấy từ ghi chú nguồn, không lấy số cuối của `mapc`) |
| `meta_khoan` | Khoảng khoản khi Điều bị cắt (`"1-8"`), một khoản `"3"`, cả Điều `null` |
| `effective_from_date`, `effective_to_date`, `still_valid` | Lọc hiệu lực (mục 4.6) |
| `version_date` | Ngày hiệu lực mới nhất mà nội dung đã phản ánh (mục 4.7) |
| `content_hash` | sha1 16 ký tự của nội dung Điều (không gồm phần đầu), sau NFC và gộp khoảng trắng; mọi phần của một Điều giống nhau |

Chương Pháp điển và chương văn bản gốc khác nhau: Pháp điển xếp Điều của NĐ/TT vào khung chương của Bộ luật. Không dùng
chương để so khớp; định danh luôn là `(document_id, meta_dieu)`. Ở 12/1.407 Điều, số cuối của `mapc` lệch số Điều gốc
(Pháp điển nối Điều hiệu lực của văn bản sửa đổi vào cuối văn bản bị sửa), nên trích dẫn luôn dùng `meta_dieu`.

### 4.3. Định danh

| Đơn vị | `chunk_id` |
|---|---|
| Điều | `45-2019-qh14:d1` |
| Điều có chữ (4a, 35đ; `đ` → `dd`) | `45-2019-qh14:d35dd` |
| Phần mở đầu | `145-2020-nd-cp:preamble` |
| Phụ lục | `10-2020-tt-bldtbxh:pl2` |
| Phần thứ k của Điều bị cắt | `45-2019-qh14:d35:p2` |

- `make_document_id` bỏ dấu, `đ` → `d`, đổi `Ð` (OCR hay đọc nhầm) về `Đ`. PDF không đọc được số hiệu thì dùng
  `doc-<sha1 text>[:12]`.
- Qdrant point id = `uuid5(NAMESPACE_URL, chunk_id)`. Khóa Điều = bỏ hậu tố `:p<số>` (giữ nguyên `:pl`).

### 4.4. Trường `text`: hai biến thể

| Biến thể | Cờ | Nội dung | Collection |
|---|---|---|---|
| TH2 (mặc định) | `--text-variant full` | `{đề mục} > {văn bản} > {Chương/Mục}` + `Điều n. Tên` + nội dung | `legal_ld_v5_bge` |
| TH1 | `--text-variant minimal` | `Điều n. Tên` + nội dung | `legal_ld_v6_bge` |

TH2 phân biệt được các Điều trùng tên giữa các văn bản và khớp câu hỏi có tên văn bản; TH1 giữ vector tập trung vào nội
dung Điều. Không đưa mã Pháp điển vào `text`; chuẩn hóa NFC; bge-m3 không cần prefix hay tách từ.

### 4.5. Cắt Điều dài

`MAX_TOKENS = 1024` (tokenizer bge-m3, tính cả phần đầu). Điều dài hơn được cắt theo **khoản** (không cắt giữa khoản);
khoản quá dài cắt theo **điểm**, lặp lại câu dẫn của khoản; điểm quá dài hoặc đoạn không có khoản (bảng, phụ lục) cắt
theo **câu**, gối đầu ~64 token. Số phần `k = ceil(tổng / budget)` và gom cho các phần dài gần bằng nhau. Mỗi phần lặp
lại phần đầu và câu dẫn của Điều.

Khi truy vấn: nhiều phần của cùng Điều trong top-k tính là **một** kết quả (điểm cao nhất). Cần cả Điều thì lấy mọi phần
theo `document_id` + `meta_dieu`, nối lại và bỏ phần lặp (`join_parts`).

### 4.6. Hiệu lực

| Trường | Pháp điển | PDF |
|---|---|---|
| `effective_from_date` | `effective_date` của văn bản trong KG | KG nếu có; không thì câu "… có hiệu lực (thi hành) từ ngày …" |
| `effective_to_date` | `vlt:validTo` (chỉ có khi một PDF thay thế văn bản) | như Pháp điển |
| `still_valid` | `true` (cờ loại thủ công) | `true` |

Bộ lọc lúc truy vấn (`hybrid_retrieve.in_force`):
`still_valid AND (effective_from_date <= hôm nay OR NULL) AND (effective_to_date > hôm nay OR NULL)`.
Văn bản cũ vẫn được dùng đến đúng ngày văn bản thay thế có hiệu lực. Mỗi lần chạy, `embed_and_index` chép
`VanBan.valid_to` sang `effective_to_date` bằng `set_payload` (không embedding lại).

### 4.7. Quy tắc nạp và `version_date`

Code: `labor_rag/ingest/merge.py::plan_upsert`, chạy bằng `embed_and_index --upsert`. Quyết định **theo từng Điều**:

- Cùng phần, cùng `text`: không embedding lại; chỉ ghi đè payload nếu metadata đổi.
- Nội dung khác: `version_date` lớn hơn thắng; bằng nhau thì Pháp điển thắng PDF; cùng nguồn thì bản mới thay bản cũ.
  Bên thắng xóa **mọi phần cũ** của Điều rồi mới ghi.
- Điều chỉ có ở bản đang index: giữ, in cảnh báo (thường do OCR sót).
- Dựng lại collection (không `--upsert`) dừng lại nếu có chunk PDF; phải thêm `--recreate`. Đổi model embedding cũng
  phải dùng `--recreate`.

| Nguồn | `version_date` |
|---|---|
| Pháp điển | max(ngày hiệu lực văn bản, ngày của các sửa đổi **của chính Điều đó** đã được Pháp điển hợp nhất) |
| PDF văn bản gốc | Ngày hiệu lực |
| PDF VBHN | max(ngày hiệu lực văn bản gốc, ngày hiệu lực từng văn bản sửa đổi trong câu dẫn) |

Ví dụ: Pháp điển có BLLĐ với `version_date = 2021-01-01`; VBHN `docs/Luat_lao_dong.pdf` (sửa bởi 3 luật năm 2025) có
`2026-07-01`, nên khi nạp thì các Điều của VBHN thay bản Pháp điển.

### 4.8. Trích dẫn trong prompt

```text
[Điều {meta_dieu}[ khoản {meta_khoan}] {meta_de_muc}] {ten}
Nội dung: {text}
```

---

## 5. Nạp PDF (OCR)

Code: `labor_rag/ocr/` (VietOCR; cài thêm `vietocr`, `torchvision` theo đầu `requirements.txt`), `labor_rag/ingest/pdf_to_chunks.py`, `pdf_abox.py`,
`amending.py`. Đầu vào là cây `LegalDocument` của OCR.

```powershell
python -m labor_rag.ingest.pdf_to_chunks --input <file>.pdf     # chunk + ontology/abox/pdf/<doc>.ttl
python -m labor_rag.ingest.ontology_to_jsonl                    # ghép ABox, chiếu lại
python -m labor_rag.ingest.load_neo4j --replace-dataset
python -m labor_rag.ingest.embed_and_index --chunks data/processed/lao_dong_v5/chunks.jsonl --upsert   # chỉ metadata
python -m labor_rag.ingest.embed_and_index --chunks data/interim/pdf_chunks/<doc>_chunks.jsonl --upsert
```

- Thân Điều được dựng lại thành dòng (`"1. …"`, `"a) …"`) rồi cắt như mục 4.5. Phụ lục trong PDF gộp thành `:pl1`.
- **VBHN**: nhận qua số `xx/VBHN-…` hoặc câu "được sửa đổi, bổ sung bởi:"; `document_id` là số hiệu văn bản gốc.
- **Chú thích cuối trang** được cắt khỏi nội dung, ghi ra `{document_id}_footnotes.jsonl`; chưa đọc thành sửa đổi.
- **Văn bản sửa đổi**: Điều có tên "Sửa đổi / Bổ sung / Bãi bỏ / Thay cụm từ" cắt theo từng khoản, mỗi phần có dòng ngữ
  cảnh "Sửa đổi, bổ sung khoản 2 Điều 3 Nghị định số …"; ABox ghi một `AmendmentEvent` cho mỗi Điều đích. Chỉ nạp văn bản
  sửa đổi khi chưa có VBHN.
- **Văn bản thay thế**: câu "thay thế / hết hiệu lực" trong Điều hiệu lực/chuyển tiếp → `vlr:replaces` và `vlt:validTo`
  trên văn bản cũ → `effective_to_date`.

Trạng thái: `docs/Luat_lao_dong.pdf` đã OCR thành `45-2019-qh14` (216/220 Điều, 594 khoản, `version_date = 2026-07-01`),
ABox ở `ontology/abox/pdf/45-2019-qh14.ttl`. **Chưa ghép** vào `lao_dong_v5` / Neo4j / Qdrant. Thiếu Điều 76–79 do bản
scan thiếu trang in 33–34 (lỗi nguồn); khi hợp nhất lấy 4 Điều này từ Pháp điển.

---

## 6. Sửa đổi, thay thế và dẫn chiếu

Mọi quan hệ nằm trong ABox → Neo4j; chunk không có trường quan hệ.

- **Sửa đổi** (`AmendmentEvent`): `actions` ∈ `sua_doi`, `bo_sung`, `bai_bo`, `thay_cum_tu`; `scope` là phần bị sửa
  (`"khoản 2"`); `date` là ngày văn bản sửa đổi có hiệu lực; `consolidated = true` khi Pháp điển đã hợp nhất vào nội dung
  (chỉ những sửa đổi này được tính vào `version_date`). Pháp điển có 71 sửa đổi mức Điều.
- **Thay thế** chỉ đến từ PDF của văn bản mới (Pháp điển chỉ giữ văn bản còn hiệu lực). Văn bản cũ không bị xóa, chỉ có
  thêm `effective_to_date`.
- **Dẫn chiếu trong câu chữ** (`labor_rag/ingest/references.py`): "điểm a, b khoản 2 Điều 35 của Bộ luật Lao động",
  "khoản 3 Điều này", "Điều 5 Nghị định số 145/2020/NĐ-CP" thành cạnh từ khoản tới Điều/khoản/điểm đích:
  `CITES_COMPONENT`, hoặc `IMPLEMENTS_COMPONENT` khi câu dẫn có "quy định chi tiết / hướng dẫn". Văn bản đích ưu tiên
  văn bản được nêu ngay sau dẫn chiếu, rồi văn bản ở câu dẫn danh sách, rồi chính văn bản đang xét. Tên luật tra theo
  `vld:shortTitle`. Trên 1.407 Điều: 1.620 dẫn chiếu, 2.108 đích (1.456 mức khoản), 2.109 `CITES_COMPONENT` +
  68 `IMPLEMENTS_COMPONENT`; lấy lại 99,4% liên kết Pháp điển có số Điều trong câu chữ.
- **Cập nhật văn bản** luôn so theo `(document_id, meta_dieu)`: nạp lại cùng văn bản thì so `content_hash` và chỉ
  embedding lại Điều đổi; văn bản sửa đổi/thay thế là văn bản riêng với `document_id` riêng.

---

## 7. Phụ lục (`appendices_v1`)

Phụ lục là nội dung ban hành kèm NĐ/TT (biểu mẫu, danh mục, bảng). Gói Pháp điển offline chỉ có link `AppFile/...doc`
đã chết (404): 156 link thuộc ~30 văn bản, gắn với 121 Điều. Phụ lục danh mục là nội dung chính, ví dụ
`LQ.147 khoản 3` giao Bộ trưởng quy định danh mục → `TT 09/2020 Điều 9` → Phụ lục III (công việc) và IV (nơi làm việc);
thiếu phụ lục thì không trả lời được.

### 7.1. Thu thập

```powershell
python -m labor_rag.appendices.collect [--document 09-2020-tt-bldtbxh]
```

- Danh sách 38 văn bản ở `docs/reports/appendix_inventory/documents.csv`, cộng 4 nguồn sửa đổi (NĐ 61/2020, NĐ 140/2018,
  TT 24/2017, NĐ 74/2019). `source_overrides.csv` sửa ItemID, `supplemental_sources.csv` và `alternative_sources.csv`
  bổ sung nguồn.
- Collector đọc trang vbpl.vn của văn bản, kiểm tra **số hiệu trong metadata**, rồi tải mọi file công khai. Mỗi văn bản
  có một thư mục `data/raw/appendix/<document_id>/` chứa **toàn bộ file nguồn**, không chỉ phụ lục:
  - `…_vbpl_content.html`: nội dung trang web (`role = document_html`). Tùy văn bản, có thể chỉ có thân văn bản
    (ví dụ TT 01/2020 chỉ có câu "theo Mẫu số 1 … ban hành kèm theo Thông tư này") hoặc chứa luôn các bảng phụ lục.
  - `.doc` / `.docx`: toàn văn bản Word, thường đủ cả phụ lục và biểu mẫu.
  - `…VanBanGoc….pdf`: bản gốc có chữ ký, dấu; thường là scan.
- Tiền tố hex trong tên file là mã file; `artifact_id = sha256:<hash>`. File được kiểm tra signature và SHA-256; lỗi 404,
  file rỗng, sai số hiệu được ghi trong manifest. Notebook `notebooks/appendix_collection.ipynb` chạy cùng các bước, các cờ
  mạng mặc định tắt.

### 7.2. Trích xuất (`labor_rag/appendices/extract.py`)

```powershell
python -m labor_rag.appendices.extract [--ocr]
```

1. Đọc `vbpl_content.html` trước.
2. So các phụ lục tìm được với danh sách mà điều luật dẫn chiếu. Nếu không tìm được hoặc còn thiếu thì đọc file dự phòng
   theo thứ tự **.docx → .pdf → .doc**, chỉ **bổ sung** phụ lục còn thiếu:
   - `.docx`: python-docx (đoạn và bảng);
   - `.pdf`: PyMuPDF, giữ bảng nhận diện được, mỗi đoạn có `data-page`; bản scan cần `--ocr`
     (`APPENDIX_ENABLE_OCR=1`), không thì báo lỗi;
   - `.doc`: LibreOffice headless (`LIBREOFFICE_PATH` hoặc `data/tools/libreoffice/`) chuyển sang HTML, cache ở
     `data/interim/appendix/converted/<sha256>.html`.
3. **Cắt theo tiêu đề, không theo trang.** Tài liệu được trải thành chuỗi khối (đoạn, bảng). Khối ngắn (< 240 ký tự) mà
   **toàn bộ** khớp `Phụ lục I`, `Phụ lục số 2: …` hoặc `Mẫu số 1: …` thì mở một phụ lục mới; mọi khối sau đó thuộc phụ lục
   đó tới tiêu đề kế tiếp. Câu trong thân văn bản như "theo Mẫu số 1 và Mẫu số 2 ban hành kèm theo…" không khớp trọn nên
   không bị nhận nhầm.
4. Phân loại: `reference` (danh mục, bảng tra cứu), `form` (biểu mẫu), `mixed`, `unknown`. Quyết định rà soát tay ở
   `docs/reports/appendix_inventory/review_overrides.csv` và `data/raw/appendix/review.csv` (ưu tiên cao nhất); mục chưa
   rõ vào `review_queue.csv`.

`appendix_id = <document_id>:pl<key>` (ví dụ `01-2020-tt-bldtbxh:plform1` là Mẫu số 1). Khối và hàng có ID ổn định;
`locator.start/end` là vị trí trong **text chuẩn hóa của phụ lục** (kèm `text_sha256`), không phải offset trong file gốc.

| Đầu ra | Nội dung |
|---|---|
| `data/processed/appendices_v1/appendices.jsonl` | Mỗi phụ lục: tiêu đề, loại, hiệu lực, Điều liên quan, file nguồn |
| `…/normalized/<appendix_id>.html` | Phụ lục đã tách, HTML làm sạch có ID khối/hàng |
| `…/chunks.jsonl` | Nội dung đủ điều kiện embedding |
| `…/kg_nodes.jsonl`, `kg_edges.jsonl` | Node/cạnh bổ sung, tham chiếu ID Điều gốc |
| `ontology/abox/appendices/appendices.ttl` | ABox phụ lục |
| `…/*report.json`, `review_queue.csv` | Báo cáo trích xuất, SHACL, nạp DB, R2, benchmark |

Quy tắc nội dung: `unknown` / `needs_review` không vào ngữ cảnh trả lời; `form` chỉ embedding tên/số mẫu (không embedding
nội dung tờ khai); `mixed` phải rà trước. Trường hợp đặc biệt: TT 02/2024 thay đúng Phụ lục II–XI của TT 21/2021;
NĐ 70/2023 chỉ thay một số mẫu của Phụ lục I NĐ 152/2020; các phụ lục số lặp trong từng quy trình của TT 54/2016 đang
chờ rà ranh giới.

### 7.3. Nạp và đồng bộ

```powershell
python -m labor_rag.appendices.graph            # xuất ABox + SHACL
python -m labor_rag.appendices.graph --load     # MERGE bổ sung vào dataset Neo4j lao_dong_v5
python -m labor_rag.appendices.index            # upsert vào collection hiện tại, chỉ embedding phần đổi
python -m labor_rag.appendices.sync_r2 [--upload [--limit 1]]
```

Phụ lục được nạp **bổ sung** lên dataset hiện tại, không rebuild collection hay dataset. Trong Neo4j: node `Appendix`,
`CONTAINS` từ văn bản ban hành, `SOURCE_COMPONENT` tới file nguồn, và Điều liên kết tới phụ lục qua
`CITES_COMPONENT` / `IMPLEMENTS_COMPONENT`.

R2 (cấu hình `OBJECT_STORAGE_*` trong `.env.example`): object có key theo SHA-256 dưới `appendices_v1/artifacts/` và
`appendices_v1/normalized/`, không ghi đè; mỗi object được tải lại và khớp hash trước khi đánh dấu hợp lệ; tiến độ
checkpoint ở `r2_sync_report.json`. `/api/files/{artifact_id}` redirect tới presigned URL 5 phút; R2 lỗi thì dùng bản
local. `--upload` chỉ chạy khi được yêu cầu rõ.

---

## 8. Nạp Qdrant và Neo4j

```powershell
python -m labor_rag.ingest.load_neo4j --replace-dataset
python -m labor_rag.ingest.embed_and_index [--backend modal] [--upsert | --recreate]
```

- Qdrant Cloud bật **strict mode**: lọc theo trường chưa có index trả lỗi 400. Trường lọc mới phải thêm vào
  `PAYLOAD_INDEXES` (`embed_and_index` tự tạo index còn thiếu). Index hiện có: `document_id`, `mapc`, `meta_dieu`,
  `meta_khoan`, `source`, `still_valid`, `effective_from_date`, `effective_to_date`.
- Embedding theo batch sắp theo độ dài, giới hạn `--max-batch-tokens` (mặc định 8.192, vừa GPU 4 GB).
- Modal: `modal deploy scripts/modal_embed.py`, rồi `python scripts/auto_chain_embeddings.py --backend modal` để embed cả
  TH1 và TH2.
- Neo4j Aura Free tự tạm dừng: lỗi `Failed to DNS resolve address` / `ServiceUnavailable` nghĩa là phải bật lại trên
  console.neo4j.io.

---

## 9. Trả lời một câu hỏi

`labor_rag/app/chat.py` (`LaborLawChat`) điều phối:

1. **Viết lại câu hỏi** (`retrieval/query_rewrite.py`): dùng ngữ cảnh hội thoại để câu hỏi đứng độc lập.
2. **Truy hồi lai** (`retrieval/hybrid_retrieve.py`, `HybridRetriever`):
   - Embedding câu hỏi bằng bge-m3, tìm trên Qdrant với bộ lọc hiệu lực (mục 4.6), gom các phần theo Điều.
   - Mở rộng bằng Neo4j:
     - `CONTAINS` / `PART_OF`: ngữ cảnh chương;
     - `REFERS_TO`: liên kết "nội dung liên quan" của Pháp điển (mức Điều);
     - `CITES_COMPONENT` / `IMPLEMENTS_COMPONENT` từ các khoản của chunk trúng: thêm **đúng text khoản đích**, chỉ khi
       Điều đích còn hiệu lực;
     - `AmendmentEvent` có `date > version_date` của chunk (sửa đổi chưa hợp nhất): gắn chunk sửa đổi vào
       `Evidence.amendments`, prompt yêu cầu áp dụng quy định sửa đổi.
   - Phụ lục: tìm trực tiếp bằng vector và đi từ Điều liên kết tới phụ lục (tối đa 2 cạnh).
3. **Rerank** (`retrieval/rerank.py`): LLM chọn top-N Điều/phụ lục liên quan nhất; sau rerank bổ sung tối đa 6 bằng chứng
   phụ lục từ quan hệ Điều–phụ lục.
4. **Sinh câu trả lời** (`generation/answer.py`): prompt theo mục 4.8; phụ lục thiếu nguồn thì nói rõ và dẫn nguồn,
   không bịa danh mục.
5. **Kiểm tra trích dẫn** (`generation/citation_verify.py`): đối chiếu Điều và Phụ lục được trích (cả số và văn bản)
   với bằng chứng thật.

Vector và đồ thị bổ sung cho nhau: vector tìm các Điều "hạt giống", nên nếu hạt giống sai thì đồ thị cũng mở rộng sang
nhánh sai; đồ thị lấy được các Điều dẫn chiếu, văn bản hướng dẫn (ví dụ NĐ 145/2020) mà câu hỏi không có từ khóa tương
đồng, điều vector không tự tìm ra.

### 9.1. Mở rộng 2 bước có rào chắn

Điều khoản giao quyền ("Bộ trưởng quy định danh mục tại điểm h khoản 1 … Điều này") dừng ở 1 bước thì LLM chỉ thấy câu
giao quyền. Mở rộng tự do thì bùng nổ và lạc đề. Truy vấn `REFERENCED_COMPONENTS` áp 4 rào chắn:

1. Tối đa **2 bước**.
2. Bước 2 chỉ đi **trong cùng Điều** của đích bước 1 (`t2.document_id = t1.document_id AND t2.article_number = t1.article_number`).
3. Ngân sách: tối đa 5 bằng chứng mỗi node (`LIMIT 8` trong Cypher); ưu tiên `IMPLEMENTS_COMPONENT` hơn `CITES_COMPONENT`.
4. Bỏ các node đã có trong kết quả vector để tránh vòng lặp.

### 9.2. Giao diện và API

```powershell
python -m labor_rag.app.api      # http://127.0.0.1:8000, tài liệu API ở /docs
python -m labor_rag.app.chat     # REPL
```

| Endpoint | Chức năng |
|---|---|
| `GET /api/appendices`, `/api/appendices/{id}`, `/api/appendices/{id}/view` | Danh sách, chi tiết, HTML phụ lục đã tách |
| `GET /api/files/{artifact_id}` | Tải/xem file nguồn (local hoặc presigned R2); PDF hỗ trợ range request |
| `POST /api/retrieve` | Kiểm tra truy hồi, **không** gọi LLM: Qdrant tìm vector → Neo4j tìm phụ lục liên kết → Qdrant lấy nội dung phụ lục. Trả về thời gian từng bước, Cypher, ID chunk, vị trí nguồn |
| `POST /api/chat` | Luồng đầy đủ có LLM |
| `GET /api/health[?probe=true]` | Trạng thái, kiểm tra lại kết nối cloud |

Đường dẫn file chỉ được giải quyết từ ID trong manifest. Khi Neo4j lỗi, kết quả vector vẫn trả về và báo thiếu liên kết.
Backend embedding lấy `QUERY_EMBEDDING_BACKEND`, rồi `EMBEDDING_BACKEND`.

---

## 10. Benchmark

### 10.1. Benchmark theo phiên bản dữ liệu

Code: `labor_rag/evaluation/benchmark_version.py`, `embedding_benchmark.py`. Một benchmark = (bộ câu hỏi, phiên bản dữ
liệu), viết `<testset>@<dataset_id>`, đóng băng trong `labor_rag/evaluation/benchmarks/<dataset_id>/`:

```text
manifest.json      sha256 của chunks.jsonl, kg_*.jsonl, TBox, ABox; mỗi bộ câu hỏi có hash, số câu, ngày đóng băng
<testset>.jsonl    câu hỏi, gold {mapc: grade 1-3}
<testset>.gold.jsonl  mỗi Điều gold lúc đóng băng: content_hash, document_id, meta_dieu, số phần
```

- Lúc chạy, benchmark **dừng** nếu `chunks.jsonl` hoặc file câu hỏi khác manifest; KG/TBox/ABox đổi chỉ cảnh báo.
- Chuyển sang dataset mới (`freeze --dataset <mới> --testset <tên> --from <cũ>`): gold được tìm theo
  `(document_id, meta_dieu)` rồi so `content_hash`. Không đổi thì giữ nhãn (đổi `mapc` nếu cần); đổi hoặc mất thì câu hỏi
  bị loại để chấm lại (`<testset>.migration.json`).
- Hiện có `lao_dong_v5/v1` (30 câu, đề mục 20.5, 42 Điều gold). Khi `chunks.jsonl` đổi, đóng băng lại bằng
  `benchmark_version freeze --dataset lao_dong_v5 --testset v1 --questions labor_rag/evaluation/benchmark_questions.jsonl --force`.

```powershell
python -m labor_rag.evaluation.benchmark_version check --dataset lao_dong_v5
python -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1 [--model bge] [--rebuild]
```

Kết quả ở `labor_rag/evaluation/results/<dataset_id>/<testset>/<run_id>/` (`summary.csv`, `metrics.csv` có CI 95%
bootstrap, `breakdown.csv` theo đề mục/kiểu câu/tag, `per_query_results.jsonl`, `run.json`). Collection chỉ được dùng
lại khi đủ `chunk_id` **và** đúng text. Notebook `notebooks/embedding_benchmark.ipynb` vẽ bảng và biểu đồ.

### 10.2. Metric

Gold tính theo Điều (gom các phần), grade ≥ 2 là "đúng" cho metric nhị phân; nDCG dùng nguyên thang 0–3.

| Metric | Ý nghĩa |
|---|---|
| HitRate@k (k = 1, 5, 10) | Tỉ lệ câu có ít nhất một Điều đúng trong top-k |
| Recall@k (micro) | Tổng số Điều đúng lấy được / tổng số Điều gold |
| Multi-HitRate@k | Tỉ lệ câu lấy đủ **mọi** Điều gold (quan trọng với câu nhiều Điều) |
| MRR@10 | Trung bình 1/hạng của Điều đúng đầu tiên |
| nDCG@10 | Có tính mức độ liên quan (gain `2^g − 1`) |

### 10.3. Script so sánh truy hồi

| Script | So sánh |
|---|---|
| `scripts/benchmark_retrieval_th1_vs_th2.py` | Chỉ vector: TH1 (`legal_ld_v6_bge`) vs TH2 (`legal_ld_v5_bge`) |
| `scripts/benchmark_retrieval_with_graph.py` | Mỗi biến thể: chỉ vector vs vector + mở rộng Neo4j |
| `scripts/benchmark_v3_*.py` | Như trên trên bộ câu hỏi v3 |

Hai script đầu đọc câu hỏi từ `data/processed/lao_dong_v5/finetune/val.jsonl` và `synthetic_queries.jsonl`. Báo cáo ở
`labor_rag/evaluation/results/retrieval_*`. Bộ câu hỏi: `benchmark_questions.jsonl` (v1), `_v2`, `_v3` trong
`labor_rag/evaluation/`; hướng dẫn gán nhãn ở `labor_rag/evaluation/annotation/`.

Phụ lục có benchmark riêng: `python -m labor_rag.evaluation.appendix_benchmark` với
`labor_rag/evaluation/appendix_questions.jsonl`, `--corpus-scope baseline|extended|appendices`; đo việc tìm đúng **ID
phụ lục**. Benchmark cũ lọc bỏ `chunk_type=appendix` và từ chối rebuild collection có phụ lục.

### 10.4. Chưa làm

Đánh giá cả pipeline sau rerank (P/R/F2 theo câu), ablation (BM25 / dense / + graph / + rerank / + kiểm tra trích dẫn),
chấm câu trả lời (coverage, mâu thuẫn, citation P/R, abstain) với LLM judge đã kiểm định bằng người, hội thoại nhiều
lượt, và kiểm định thống kê giữa các cấu hình.

---

## 11. Thiếu sót đã biết

**Dữ liệu**

- Corpus có thể cũ ở mảng Việc làm / BHXH / Công đoàn: `38-2013-qh13` (Luật Việc làm 2013) và NĐ 28/2015, 61/2015,
  31/2015 vẫn `still_valid = true`. Nếu đã có luật thay thế (Luật Việc làm 2025, Luật BHXH 2024, Luật Công đoàn 2024)
  thì chatbot đang trả lời theo văn bản cũ.
- 3 Điều trùng mã (`20.4.TT.5.2`, `20.5.TT.74.1`, `20.5.TT.74.2`): bản thứ hai có `mapc` là URI `..._dup2`. Graph vẫn
  khớp được, nhưng không dùng làm gold benchmark và thống kê theo đề mục bị lẫn.
- 48 Điều không có tiêu đề trong nguồn (`ten` = "Điều <mã>."); khoản không liên tục ở `20.2.NĐ.4.13`, `20.4.NĐ.3.18`,
  `.22`, `.30` (thiếu ngay trong HTML gốc).
- `meta_chuong` / `meta_muc` của chunk Pháp điển luôn `null`; `effective_to_date` luôn `null` cho tới khi nạp PDF thay thế.
- Điều 14 NĐ 97/2022 (`20.2.NĐ.6.14`) gần như toàn bảng, bị cắt thành 16 phần; `join_parts` còn lặp vài dòng gối đầu.
- Khi dựng ABox cho cả 45 chủ đề (không chỉ Lao động): 15/~66.000 ghi chú nguồn lệch mẫu nên Điều thiếu liên kết văn
  bản nguồn; 8 mã cơ quan chưa có tên đầy đủ; `issuer_codes()` chỉ đọc phần sau dấu `/` cuối. Không ảnh hưởng chủ đề 20.

**PDF / OCR**

- PDF chưa ghép vào dataset (mục 5); parser văn bản sửa đổi mới thử trên văn bản mẫu.
- Dấu chú thích trong câu ("động¹") chưa bị xóa; chú thích tràn sang trang sau còn lẫn vào nội dung; chưa đọc chú thích
  thành sửa đổi.

**Dẫn chiếu**

- 32 dẫn chiếu tới luật không có trong dữ liệu và không kèm số hiệu ("Luật Bảo hiểm xã hội") không thành cạnh.
- "Điều 14" không nêu văn bản được gán cho chính văn bản đang xét dù có thể là văn bản khác.
- "Của Luật này" trong nội dung Điều sửa đổi chèn vào luật khác (Điều 219 BLLĐ) bị hiểu là luật đang xét.

**Phụ lục**

- Tiêu đề phụ lục trình bày bất thường (nằm chung ô bảng, thiếu "Mẫu số") có thể bị cắt sai; tiêu đề lấy tự động đôi khi
  là chuỗi gộp nhiều tên mẫu (ví dụ Phụ lục I TT 09/2020). Cần rà qua `review_queue.csv`.
- PDF scan cần chạy `--ocr` chủ động; chưa tạo file Word riêng cho từng mẫu.

**Chưa quyết**

- Tìm kiếm trực tiếp ở mức khoản (embedding ~3.767 khoản, hoặc giữ mức Điều và thêm bước chọn khoản).

---

## 12. Lưu ý vận hành

- Các lệnh nạp Neo4j/Qdrant, embedding, Modal và upload R2 là thao tác chủ động; mở notebook hay khởi động API không tự
  chạy chúng. Kiểm tra pipeline bằng cách ghi ra thư mục tạm (`build_abox --output <tmp>`,
  `ontology_to_jsonl --out-dir <tmp> --pdf-abox-dir <tmp>`).
- `data/processed/lao_dong_v5/` được git theo dõi và từng bị xóa nhầm khi merge (`c0ece55`, khôi phục ở `5d28985`): kiểm
  tra thư mục này mỗi lần merge `develop`.
- Script in tiếng Việt trên Windows cần `sys.stdout.reconfigure(encoding="utf-8")`.

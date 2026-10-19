# Ánh xạ ZaloAI2021_LTR sang chủ đề Lao động

Module `labor_rag.finetune.map_zaloai_labor` lọc bộ ZaloAI2021_LTR theo
chủ đề Lao động đang có trong `data/processed/lao_dong_v5/chunks.jsonl`.

## Chạy

Từ thư mục gốc repository:

```powershell
python -m labor_rag.finetune.map_zaloai_labor
```

Mặc định module đọc:

```text
data/finetune/zalo/train_data_model.json
data/processed/lao_dong_v5/chunks.jsonl
```

và ghi:

```text
data/processed/finetune/zalo/zaloai_ltr_lao_dong.json
data/processed/finetune/zalo/zaloai_ltr_lao_dong_mapping_report.json
```

Có thể chỉ định đường dẫn khác:

```powershell
python -m labor_rag.finetune.map_zaloai_labor `
  --input data/finetune/zalo/train_data_model.json `
  --chunks data/processed/lao_dong_v5/chunks.jsonl `
  --output data/processed/finetune/zalo/zaloai_ltr_lao_dong.json `
  --report data/processed/finetune/zalo/zaloai_ltr_lao_dong_mapping_report.json
```

## Quy tắc định danh

Ánh xạ là exact match, không dùng fuzzy matching:

```text
ZaloAI law_id + article_id
  -> make_document_id(law_id) + article_key(article_id)
  -> document_id + meta_dieu trong chunks.jsonl
  -> chunk_id, mapc, citation
```

Một Điều dài có thể có nhiều `chunk_id` (`:p1`, `:p2`, ...). Bản ghi được
ánh xạ giữ `chunk_id` đại diện và toàn bộ danh sách `chunk_ids`.

## Phạm vi output

Chỉ câu hỏi có ít nhất một `relevant_articles` ánh xạ được vào 1.407 Điều
trong chủ đề Lao động mới được xuất. Các `non_relevant_articles` chỉ được
giữ lại khi chúng cũng ánh xạ được vào tập này. Bản ghi gốc không bị gán mã
pháp lý suy đoán.

Mỗi article được ánh xạ có thêm:

| Trường | Ý nghĩa |
|---|---|
| `mapping_status` | `mapped` trong output; các trạng thái lỗi nằm trong report |
| `document_id` | Định danh chuẩn, ví dụ `38-2013-qh13` |
| `normalized_article_id` | Số Điều chuẩn hóa |
| `chunk_id` | Chunk đại diện, ví dụ `38-2013-qh13:d50` |
| `chunk_ids` | Tất cả phần của Điều |
| `mapc` | Mã Điều Bộ Pháp điển, ví dụ `20.4.LQ.50` |
| `citation` | Trích dẫn dựng từ metadata Bộ Pháp điển |

`mapping_report.json` ghi coverage theo câu hỏi, số Điều mapped và các lý do
không khớp (`missing_document`, `missing_article`, `invalid_identifier`).

Bước tiếp theo (gộp với các nguồn khác, chia train/val): `docs/FINETUNE_DATA.md`.

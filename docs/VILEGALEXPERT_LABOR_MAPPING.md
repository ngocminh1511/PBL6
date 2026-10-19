# Ánh xạ ViLegalExpert sang chủ đề Lao động

Module `labor_rag.finetune.map_vilegal_labor` xử lý bộ
`structured-single-hop-IR_single_context` của ViLegalExpert.

## Chạy

```powershell
python -m labor_rag.finetune.map_vilegal_labor
```

Mặc định module đọc:

```text
data/finetune/ViLegalExpert/train_data.json
data/processed/lao_dong_v5/chunks.jsonl
```

và ghi:

```text
data/processed/lao_dong_v5/finetune/vilegal_labor_mapped.json
data/processed/lao_dong_v5/finetune/vilegal_labor_review.json
data/processed/lao_dong_v5/finetune/vilegal_labor_mapping_report.json
```

Có thể thay đổi đường dẫn bằng `--input`, `--chunks`, `--output`, `--review`
và `--report`.

## Quy tắc mapping

Metadata nguồn nằm trong `contexts[*]`:

```text
contexts[*]["Số hiệu:"]
contexts[*]["điều"]
contexts[*]["khoản"]
```

Khóa ánh xạ canonical:

```text
Số hiệu + điều
  -> make_document_id(Số hiệu) + article_key(điều)
  -> document_id + meta_dieu trong chunks.jsonl
  -> mapc và chunk_id
```

Ví dụ:

```text
45/2019/QH14 + Điều 36
  -> 45-2019-qh14:d36
  -> 20.2.LQ.36
```

Mapping là exact; không dùng fuzzy matching. Một Điều dài có thể có nhiều
`chunk_id`, vì vậy output lưu cả `chunk_id` đại diện và `chunk_ids` đầy đủ.

## Khôi phục Điều thiếu

Nếu context có `Số hiệu:` nhưng không có `điều`, module tìm các citation
`Điều n` trong `answer`. Chỉ khi đúng một citation khớp với Điều trong cùng
văn bản thì record mới được map và có:

```json
{"article_recovery": "recovered_from_unique_answer_citation"}
```

Citation không khớp hoặc có nhiều Điều ứng viên được đưa vào review, không
được tự động gán mã.

## Output

`vilegal_labor_mapped.json` giữ `record_id`, câu hỏi, answer, link, loại văn
bản và context gốc kèm:

| Trường | Ý nghĩa |
|---|---|
| `document_id` | ID chuẩn hóa từ `Số hiệu:` |
| `article_id` | Số Điều chuẩn từ Pháp điển |
| `mapc` | Mã Điều Bộ Pháp điển |
| `chunk_id` | Chunk đại diện |
| `chunk_ids` | Tất cả phần của Điều |
| `citation` | Citation dựng từ metadata canonical |
| `mapping_status` | Trạng thái, `mapped` trong mapped output |

`vilegal_labor_review.json` chứa record thuộc văn bản Lao động nhưng chưa map
được. Record ngoài tập văn bản Lao động không nằm trong hai output này nhưng
được thống kê trong report với trạng thái `missing_document`.

Nguồn nội dung pháp lý canonical để chưng cất vẫn là
`data/processed/lao_dong_v5/chunks.jsonl`; answer của ViLegalExpert được giữ
để huấn luyện và truy vết, không thay thế văn bản Pháp điển.

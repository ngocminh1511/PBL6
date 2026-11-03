# Pipeline phụ lục v1

File nguồn giữ bản local và có thể đồng bộ chủ động lên R2; Neo4j, Qdrant, Modal và LLM dùng `.env` hiện có. Thêm khóa Cloudflare vào `.env` không làm phát sinh upload.

## Chạy và xem kết quả

Từ thư mục gốc dự án, dùng môi trường Python hiện tại:

```powershell
python -m pip install -r requirements-appendix.txt
python -m labor_rag.app.api
```

Mở <http://127.0.0.1:8000>. Tài liệu API ở `/docs`. Danh sách, xem và tải file dùng catalog trên máy. Ô **Kiểm tra truy hồi phụ lục** dùng `POST /api/retrieve`, không gọi LLM để viết lại câu hỏi, rerank hay tạo câu trả lời. Backend embedding lấy `QUERY_EMBEDDING_BACKEND` nếu có, tiếp theo là `EMBEDDING_BACKEND`. Với Modal, lượt đầu vẫn có thể phải đợi container và model khởi động.

Kết quả kiểm tra có ba phần:

1. **Qdrant tìm vector**: câu hỏi được embedding bằng model đã dùng khi index. Trả tối đa `top_k` chunk còn hiệu lực, giữ nguyên thứ tự và điểm tương đồng; nhiều chunk có thể thuộc cùng một điều/phụ lục.
2. **Neo4j truy vấn ontology**: từ điều luật tìm được, đi qua tối đa hai cạnh `CITES_COMPONENT`/`IMPLEMENTS_COMPONENT` để tìm node `Appendix`. Có thể đi ngược cạnh để đối chiếu văn bản hướng dẫn, nhưng giao diện giữ đúng chiều cạnh lưu trong graph. Chỉ đi qua các node thành phần luật trong cùng dataset, không lan sang mọi phụ lục chỉ vì cùng văn bản. Các phụ lục tìm trực tiếp bằng vector cũng được đối chiếu quan hệ với điều luật. `CONTAINS` cho biết văn bản ban hành; `SOURCE_COMPONENT` liên kết file nguồn với phụ lục.
3. **Qdrant lấy nội dung**: dùng các `appendix_id` vừa tìm được để lấy toàn bộ chunk phụ lục còn hiệu lực qua payload filter, không embedding lại tài liệu. Metadata và URL xem/tải lấy từ catalog local; nội dung chunk trong kết quả lấy từ Qdrant. Biểu mẫu không embedding nội dung nên có thể chỉ có metadata và file nguồn. Phụ lục chưa đủ điều kiện rà soát/hiệu lực chỉ hiện metadata.

Giao diện hiển thị thời gian từng bước, Cypher với tham số, ID chunk, nội dung gốc, vị trí nguồn và JSON kết quả. Điểm vector đo độ tương đồng, không phải xác suất câu trả lời đúng. Khi Neo4j lỗi, kết quả vector vẫn được giữ và liên kết graph được báo chưa lấy được; không suy ra quan hệ từ JSONL thay thế.

Ví dụ gọi trực tiếp từ PowerShell khi API đang chạy:

```powershell
$payload = @{ question = "công việc tổn hại đến sự phát triển thể lực là"; top_k = 8 } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/retrieve -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($payload)) | ConvertTo-Json -Depth 20
```

`/api/chat` vẫn là endpoint riêng cho luồng có LLM; giao diện kiểm tra truy hồi không gọi endpoint này.

Notebook thu thập riêng: [appendix_collection.ipynb](../notebooks/appendix_collection.ipynb). Mở kernel mới và chạy toàn bộ cell an toàn với `ENABLE_NETWORK`, `RUN_SAMPLE`, `RUN_BATCH` mặc định `False`. Notebook không nạp DB hoặc gọi embedding. Bật các cờ cần thiết khi muốn tải thêm.

## Các bước độc lập

```powershell
# Thu thập một văn bản; bỏ qua file đã kiểm tra hash hợp lệ
python -m labor_rag.appendices.collect --document 09-2020-tt-bldtbxh

# Thu thập toàn bộ mục gốc và nguồn sửa đổi bổ sung
python -m labor_rag.appendices.collect

# Trích xuất; không thay đổi các file Pháp điển gốc
python -m labor_rag.appendices.extract

# Xuất ABox và kiểm tra SHACL trên ABox hợp nhất
python -m labor_rag.appendices.graph

# MERGE bổ sung vào dataset Neo4j hiện tại sau khi SHACL đạt
python -m labor_rag.appendices.graph --load

# Upsert phụ lục vào collection hiện tại; chỉ embedding nội dung thay đổi
python -m labor_rag.appendices.index

# Kiểm tra API đang chạy; --chat gọi cả các dịch vụ cloud cấu hình sẵn
python -m labor_rag.appendices.smoke --chat

# Benchmark phụ lục riêng, truy vấn đọc collection hiện tại
python -m labor_rag.evaluation.appendix_benchmark
```

Các lệnh nạp Neo4j/Qdrant là thao tác chủ động. Mở notebook hoặc khởi động API không tự chạy chúng. Không dùng lệnh rebuild collection/dataset để nạp phụ lục.

## Thư mục và định danh

| Vị trí | Nội dung |
|---|---|
| `data/raw/appendix/` | HTML VBPL, Word/PDF, metadata và manifest thu thập |
| `data/raw/appendix/review.csv` | Ghi đè rà soát riêng trên máy, ưu tiên cao nhất |
| `data/interim/appendix/converted/` | Cache HTML chuyển từ DOC theo hash |
| `data/processed/appendices_v1/appendices.jsonl` | Phụ lục, bảng, loại, hiệu lực, điều liên quan và nguồn |
| `data/processed/appendices_v1/normalized/` | HTML đã làm sạch với ID khối/hàng |
| `data/processed/appendices_v1/chunks.jsonl` | Nội dung tra cứu đủ điều kiện embedding |
| `data/processed/appendices_v1/kg_*.jsonl` | Node/cạnh bổ sung, tham chiếu các ID điều gốc |
| `ontology/abox/appendices/appendices.ttl` | ABox bổ sung riêng |
| `data/processed/appendices_v1/*report.json` | Kết quả trích xuất, SHACL, nạp DB, benchmark và API |

`document_id` nhận diện văn bản ban hành; `appendix_id` dạng `<document>:pl<key>` nhận diện phụ lục; `artifact_id=sha256:<hash>` nhận diện file; `chunk_id` thêm `:p<số>` khi chia phần. Một file có thể cung cấp nguồn cho nhiều phụ lục. Hàm xử lý ID chỉ bỏ hậu tố `:p<số>`, giữ nguyên `:pl`.

Khối và hàng có ID ổn định trên bản chuẩn hóa. `locator.start/end` là vị trí trong **text chuẩn hóa của phụ lục**, kèm `text_sha256`; đây không phải offset trong HTML gốc hoặc trong PDF. Giao diện đánh dấu các khối/hàng theo `locator.block_ids`.

## Nguồn và rà soát

Danh sách 38 mục gốc ở `docs/reports/appendix_inventory/documents.csv`. Có thêm bốn nguồn sửa đổi vì một số link cũ thực tế trỏ sang NĐ 61/2020, NĐ 140/2018, TT 24/2017 và NĐ 74/2019. `source_overrides.csv` sửa ItemID của văn bản gốc; `supplemental_sources.csv` giữ danh tính riêng cho các văn bản sửa đổi. `alternative_sources.csv` bổ sung nguồn Công báo khi cần.

Collector kiểm tra **số hiệu trong metadata**, giải mã dữ liệu trang mới và lấy tên file công khai từ metadata. File được kiểm tra signature và SHA-256. Lỗi 404, file rỗng, sai số hiệu hoặc nguồn không đủ được giữ trong manifest. Ngày tải không thay ngày hiệu lực.

Các quyết định rà soát đã ghi ở `docs/reports/appendix_inventory/review_overrides.csv`; có thể chỉnh bảng rồi chạy lại trích xuất → ABox → nạp DB. Bảng `review_queue.csv` trong thư mục processed liệt kê mục chưa rõ. Bốn trạng thái loại là `reference`, `form`, `mixed`, `unknown`.

Nội dung `unknown` hoặc `needs_review` không được đưa vào ngữ cảnh trả lời. Loại `form` chỉ cung cấp tên/số mẫu, nguồn và file; không embedding nội dung tờ khai. Nội dung hỗn hợp cần rà soát trước khi embedding phần tra cứu. Hiệu lực lấy từ metadata nguồn và quyết định rà soát; văn bản hết hiệu lực một phần cần tiếp tục đối chiếu phạm vi sửa đổi.

HTML được ưu tiên; DOCX đọc cấu trúc Word, PDF có text giữ bảng nhận diện được. DOC cũ dùng LibreOffice headless, tự phát hiện công cụ trong `data/tools/libreoffice/` hoặc cấu hình `LIBREOFFICE_PATH`. Cache chuyển đổi được giữ trên máy. Bản scan cần chạy chủ động `python -m labor_rag.appendices.extract --ocr` với môi trường OCR hiện có; V1 không tự chạy OCR dài khi mở notebook hay API. Nội dung chưa khôi phục được luôn ghi trạng thái cần xử lý.

TT 02/2024 được ghi riêng việc thay thế đúng số phụ lục II–XI của TT 21/2021, giữ ngày kết thúc hiệu lực theo nguồn. NĐ 70/2023 được ghi là gói mẫu sửa đổi cụ thể, không tự thay toàn bộ Phụ lục I NĐ 152/2020. Các phụ lục có số lặp trong từng quy trình TT 54/2016 đang chờ rà soát ranh giới. NĐ 97/2022 tận dụng nội dung phụ lục đã có, đồng thời giữ PDF gốc để tải.

## API và truy hồi

API gồm `/api/appendices`, `/api/appendices/{id}`, `/api/appendices/{id}/view`, `/api/files/{artifact_id}`, `/api/chat`, `/api/health`. Dùng `/api/health?probe=true` để kiểm tra lại kết nối cloud. Đường dẫn file chỉ được giải quyết từ ID trong manifest và giới hạn trong thư mục phụ lục. Word/HTML nguồn được tải xuống; PDF hỗ trợ xem trực tiếp và range request. Bản HTML phụ lục đã tách có thể tải riêng; V1 chưa tạo Word riêng cho từng mẫu.

Chat hỗ trợ vector phụ lục và bổ sung tối đa sáu bằng chứng phù hợp sau rerank từ quan hệ điều–phụ lục. Biểu mẫu tìm theo metadata. Thiếu nguồn được phản ánh trong cảnh báo và prompt. Trích dẫn phụ lục được kiểm tra cả số phụ lục và văn bản; giao diện mở bản chuẩn hóa tại đoạn được trích.

Benchmark đóng băng của corpus gốc giữ nguyên. Benchmark cũ lọc bỏ `chunk_type=appendix` và từ chối rebuild collection có phụ lục. Bộ câu hỏi riêng ở `labor_rag/evaluation/appendix_questions.jsonl`, hỗ trợ `--corpus-scope baseline|extended|appendices`. Điểm của bộ mới đo tìm đúng **ID phụ lục**, không phải chất lượng tư vấn; corpus gốc có thể chứa nội dung phụ lục trong điều nhưng chưa có ID phụ lục riêng.

## Đồng bộ R2

Cấu hình theo các trường `OBJECT_STORAGE_*` trong `.env.example`: provider `s3` hoặc `r2`, HTTPS endpoint S3 của R2, region `auto`, bucket, Access Key ID và Secret Access Key. Khóa chỉ được đọc ở backend. Bucket không cần chuyển sang public. Tham khảo [cấu hình boto3 của Cloudflare](https://developers.cloudflare.com/r2/examples/aws/boto3/).

```powershell
# Chỉ kiểm tra bucket và phạm vi; không upload
python -m labor_rag.appendices.sync_r2

# Đồng bộ một file mẫu và tải lại để đối chiếu hash
python -m labor_rag.appendices.sync_r2 --upload --limit 1

# Đồng bộ toàn bộ file nguồn trong manifest và HTML đã tách
python -m labor_rag.appendices.sync_r2 --upload
```

Lệnh `--upload` chỉ chạy khi người dùng yêu cầu rõ ràng. Nội dung có key theo SHA-256 dưới `appendices_v1/artifacts/` hoặc `appendices_v1/normalized/`; không ghi đè object có cùng key. File đã tồn tại được tải kiểm tra lại thay vì upload trùng. Mỗi object phải được tải lại và khớp SHA-256 trước khi vị trí được đánh dấu hợp lệ. Báo cáo tiến độ được checkpoint ở `r2_sync_report.json`, có thể tiếp tục sau gián đoạn.

Manifest gốc trước đồng bộ được lưu ở `data/raw/appendix/manifest.before_r2.json`. Mọi đường dẫn local vẫn được giữ. Sau khi xác minh, `manifest.json`, bản xuất collection và `artifacts.json` được cập nhật vị trí R2; không đổi `artifact_id`, `appendix_id`, chunk, graph hoặc vector. Mới thu thập thêm file sẽ có trạng thái local/mixed cho đến lần đồng bộ chủ động tiếp theo.

`/api/files/{artifact_id}` vẫn là URL dùng trong ứng dụng. Với file đã xác minh trên R2, API tạo redirect tới URL ký tạm thời, thời hạn 5 phút; hỗ trợ xem PDF và tải Word. Đây là [presigned URL](https://developers.cloudflare.com/r2/api/s3/presigned-urls/), không phải đường dẫn công khai cố định. Nếu R2 tạm lỗi, API dùng bản local còn có sẵn; nếu cả hai nguồn đều thiếu, trả trạng thái lỗi phù hợp. Khởi động API, notebook hoặc thêm khóa `.env` không tự upload.

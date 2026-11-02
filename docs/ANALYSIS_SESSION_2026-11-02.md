# Phân tích công việc từ session 02/11/2026

Ngày đối chiếu: 02/11/2026.

Nguồn yêu cầu: [session_2026_2_12.md](session_2026_2_12.md). Tên file không khớp ngày trong tiêu đề; phân tích này dùng ngày trong nội dung.

Phạm vi: đọc code, HTML gốc, ABox và JSONL hiện có trên máy; xác định phần đã có, phần thiếu, thứ tự triển khai và tiêu chí hoàn thành. Chưa sửa code xử lý, dữ liệu pháp lý hoặc dịch vụ Neo4j/Qdrant. Không kiểm tra trạng thái dịch vụ cloud và không xác minh lại HTTP 403/404 hay hiệu lực pháp lý trên nguồn trực tuyến trong lần phân tích này.

## 1. Kết luận chính

Việc cần ưu tiên là hoàn thiện luồng phụ lục: kiểm kê → khôi phục file → đọc nội dung → liên kết đúng phụ lục với điều → truy hồi → trích dẫn. Có thể dùng lại cơ chế index, merge và lọc ngày hiệu lực hiện có.

Danh sách việc trong session cần điều chỉnh ở ba chỗ:

1. Chưa có bằng chứng cần sửa lỗi gán cha theo vị trí trong pipeline hiện tại. Cần bổ sung kiểm thử bảo vệ hành vi đang đúng.
2. Không cần xây lại regex tách số hiệu cho 28 link nếu dùng được parser nguồn hiện có: đối chiếu lần này tách được số hiệu của cả 156 link.
3. PDF luật lao động đã có kết quả OCR đúng ID. Công việc còn lại là kiểm tra, hợp nhất và xử lý phần nguồn bị thiếu.

## 2. Hiện trạng đã kiểm tra

| Hạng mục | Bằng chứng trong repo | Hệ quả đối với kế hoạch |
|---|---|---|
| Quan hệ phân cấp | `parse_demuc_html.py` tạo cây Phần/Chương/Mục/Điều; `build_abox.py` gắn điều vào tiêu đề bao chứa | Không thấy cơ chế lấy điều luật xuất hiện trước làm cha cho điều NĐ/TT |
| Ví dụ `20.2.TT.1.1` | ABox đặt dưới Chương I; quan hệ `cites` đến LQ.143, 145, 146, 147; không đến LQ.2 | Ví dụ gây lo ngại trong session hiện đang được biểu diễn đúng |
| Ví dụ `20.2.TT.1.2` | Cùng nằm dưới Chương I; không có quan hệ `cites` đi ra | Không cần thêm quan hệ hướng dẫn để bù cho việc đứng sau LQ.2 |
| Link phụ lục | HTML có link; parser trả nội dung chữ và tên file, chưa trả trường attachment chứa URL | Phải lấy và giữ URL gốc trước khi thông tin này mất trong ABox/JSONL |
| Kho phụ lục | Chưa có `data/raw/appendix/` và `appendix_map.csv` | Luồng quản lý phụ lục chưa được xây dựng |
| Corpus Pháp điển | `lao_dong_v5/chunks.jsonl`: 1.481 chunk, 1.407 điều, toàn bộ `source=phap_dien`; không có chunk phụ lục hoặc metadata attachment | Nội dung danh mục trong file đính kèm chưa nằm trong corpus JSONL này |
| Phụ lục qua PDF | `pdf_to_chunks.py` có thể xuất phần phụ lục thành nhóm `:pl1`, nhưng gộp tất cả thành một khối | Tái sử dụng được nền tảng, cần tách riêng số phụ lục, liên kết và vị trí nguồn |
| Phiên bản và hiệu lực | Có `version_date`, `effective_from_date`, `effective_to_date`, `still_valid`, merge theo điều, sự kiện sửa đổi/thay thế và bộ lọc `in_force()` | Cần bổ sung dữ liệu và xử lý trường hợp thiếu; không xây lại từ đầu |
| Kiểm tra trích dẫn | `citation_verify.py` nhận diện “Điều …”; chưa nhận diện “Phụ lục …” | Trích dẫn phụ lục có thể bị bỏ qua và kết quả vẫn báo `all_verified=True` khi không có trích dẫn Điều sai |
| Giao diện | Điểm chạy ứng dụng hiện tại là REPL `labor_rag/app/chat.py` | API tải file và giao diện highlight là phần phát triển thêm |
| PDF luật lao động | Có `45-2019-qh14_chunks.jsonl` gồm 216 điều và ABox PDF; session 19/10 ghi nhận scan thiếu trang chứa Điều 76–79 | Ưu tiên kiểm tra đầu ra có sẵn và bù nguồn, tránh OCR lại cùng bản scan |

### Kiểm kê lại phụ lục

| File | Số điều được parser đọc | Link AppFile | Điều có link |
|---|---:|---:|---:|
| `lao_dong.html` | 477 | 39 | 32 |
| `viec_lam.html` | 393 | 84 | 56 |
| `nguoi_lao_dong_viet_nam_di_lam_viec_o_nuoc_ngoai_theo_hop_dong.html` | 187 | 31 | 31 |
| `an_toan_ve_sinh_lao_dong.html` | 350 | 2 | 2 |
| `giao_duc_nghe_nghiep.html` | 0 | 0 | 0 |
| **Tổng** | **1.407** | **156** | **121** |

- 156 URL khác nhau, thuộc 30 số hiệu văn bản: 110 link `.doc`, 46 link `.docx`.
- Dùng `SOURCE_RE` và hàm chuẩn hóa của `build_abox.py` tách được số hiệu cho cả 156 link; không còn link chưa xác định số hiệu trong phép đối chiếu này. Điều này xác nhận khả năng tách metadata, không xác nhận file tải được hoặc đúng nội dung.
- Một văn bản có thể có nhiều URL; nhiều URL cũng có thể dẫn tới các bản sao cùng nội dung. Chưa tải file nên chưa biết số file thực sự khác nhau.
- HTML của TT 09/2020 còn có Phụ lục V được Điều `20.2.TT.1.10` dẫn tới. Mô tả chỉ có Phụ lục I–IV trong session chưa bao quát hết tham chiếu của văn bản này.
- Một số mã Pháp điển bị lặp trong nguồn. Khi định danh liên kết, cần giữ định danh điều nguồn ổn định và thông tin bản ghi, không dùng riêng mã hiển thị làm khóa duy nhất cho mọi trường hợp.

## 3. Những điểm thiết kế cần làm rõ trước khi triển khai

### 3.1. Phân biệt quan hệ bao chứa, liên quan và hướng dẫn

Điều “Phạm vi điều chỉnh” vẫn có vị trí trong Chương/Mục. Không nên loại nó khỏi cây cấu trúc khi xử lý ngoại lệ trong session.

Ghi chú “có nội dung liên quan” là bằng chứng cho quan hệ liên quan; không tự động đồng nghĩa với “quy định chi tiết”. Pipeline hiện đã tách dẫn chiếu chung và `implementsComponent` dựa trên nội dung. Nên giữ cách phân biệt này. Nếu sau này bổ sung suy luận từ vị trí, phải ghi nguồn suy luận và kiểm tra ngoại lệ, thay vì thay thế quan hệ có bằng chứng trực tiếp.

### 3.2. Ánh xạ tới từng phụ lục, không chỉ tới cả file

Một file có thể chứa biểu mẫu và danh mục cùng lúc. Một điều cũng có thể dẫn nhiều phụ lục: TT.1.9 dẫn III và IV, TT.1.8 dẫn II, TT.1.10 dẫn V theo HTML hiện có.

Vì vậy, chỉ có `appfile_url → local_file` chưa đủ để truy hồi chính xác. Cần lưu thêm `appendix_id` và danh sách điều thực sự dẫn đến phụ lục đó. Các điều chỉ nhắc tới mẫu nhưng không có link AppFile riêng cũng cần được nhận diện khi phân tích nội dung.

Không phân loại toàn bộ file là `bieu_mau` rồi bỏ embedding nếu bên trong vẫn có danh mục. Cho phép `mixed` hoặc `unknown` trong lúc kiểm kê, sau đó phân loại ở cấp phụ lục.

### 3.3. Tách trạng thái file khỏi trạng thái pháp lý

`missing/ok` mô tả khả năng đọc file. `con_hieu_luc/het_hieu_luc/het_mot_phan` mô tả trạng thái pháp lý. Hai nhóm phải được lưu riêng.

Văn bản biến mất khỏi snapshot mới chỉ là tín hiệu cần đối chiếu; không đủ để tự động ghi `het_hieu_luc`. Tương tự, `version_date` mới hơn không tự chứng minh quy định đang có hiệu lực tại ngày hỏi.

Các nhận định pháp lý ở mục 4.1 của session cần được xác minh bằng nguồn chính thức và điều khoản chuyển tiếp trước khi chuyển thành quy tắc tự động. Không dùng riêng suy đoán “chưa có văn bản thay thế” để kết luận tiếp tục áp dụng.

Metadata cấp văn bản là bước nền; trường hợp hết hiệu lực một phần cần theo dõi điều/khoản bị ảnh hưởng để tránh loại cả văn bản hoặc dùng lại phần đã bị bãi bỏ. Cập nhật bộ Pháp điển cũng vẫn cần lưu ngày snapshot và đối chiếu hiệu lực.

### 3.4. Quy định vị trí dùng để highlight

`start/end` phải là offset trên một bản text/HTML chuẩn hóa được lưu cố định, có hash hoặc phiên bản. Offset trên text chuyển đổi không thể dùng trực tiếp trên file Word hoặc PDF khác.

Nên lưu vị trí nguồn gồm `rendered_file`, `text_start`, `text_end`, `quote`; bổ sung trang hoặc tọa độ nếu có. Tìm theo quote chỉ là phương án dự phòng vì một câu có thể xuất hiện nhiều nơi.

## 4. Danh sách công việc đề xuất

P0 là nền tảng cần hoàn thành trước khi tích hợp; P1 là phần để luồng hỏi đáp phụ lục chạy được; P2 là mở rộng phục vụ sử dụng và vận hành.

| Mã | Ưu tiên | Công việc và nơi tác động | Tiêu chí hoàn thành |
|---|---|---|---|
| A | P0 | Kiểm thử bảo vệ quan hệ trong parser/ABox | TT.1.1 không trở thành con của LQ.2; vẫn thuộc đúng chương và giữ bốn quan hệ liên quan; TT.1.2 không phát sinh quan hệ hướng dẫn giả |
| B | P0 | Bổ sung lấy attachment trong `parse_demuc_html.py`; tạo script kiểm kê và bảng ánh xạ | Thu đủ 156 liên kết trên dữ liệu hiện tại, gắn đúng 121 điều và 30 văn bản; nhận cả `.doc` và `.docx`; giữ URL vbpl; chạy lại không làm mất thông tin đã rà soát |
| C | P0 | Chốt schema metadata dùng chung từ ingest tới Evidence | Phân biệt file/phụ lục/chunk; có khóa ổn định, liên kết điều, trạng thái tải và nguồn trích dẫn; HTML gốc được giữ nguyên |
| D | P1 | Rà phân loại và khôi phục file, bắt đầu với TT 09/2020 | File đúng văn bản, mở được, đủ các phụ lục cần dùng; ghi nguồn và hash; file chưa có tiếp tục mang trạng thái `missing`; xác minh lại kênh tải thay vì mặc định mọi truy cập tự động đều bị chặn |
| E | P1 | Xây bước đọc `.doc`/`.docx`, chuẩn hóa bảng và tạo chunk phụ lục | Tách đúng II, III, IV, V trong mẫu TT 09/2020; không mất tiêu đề cột, điều kiện hoặc hàng; có vị trí nguồn; chunk có thể đưa vào Qdrant hiện có |
| F | P1 | Mở rộng retrieval và rerank để giữ nội dung phụ lục cần thiết | Tìm trực tiếp được danh mục; đi từ điều liên kết tới đúng phụ lục; phụ lục cần thiết không bị rerank loại hết; giới hạn số chunk/ngân sách token và lọc hiệu lực |
| G | P1 | Mở rộng `Evidence`, `answer.py`, `citation_verify.py` cho phụ lục | Trích dẫn rõ phụ lục và văn bản; trích dẫn không có bằng chứng bị phát hiện; thiếu file thì thông báo thiếu nội dung và dẫn nguồn, không sinh danh mục từ suy đoán |
| H | P1 | Kiểm tra dữ liệu hiệu lực và tích hợp PDF có kiểm soát | Tận dụng merge/lọc ngày hiện có; ghi nguồn xác minh; quản lý phần bị sửa/bãi bỏ; PDF không làm mất Điều 76–79 còn trong Pháp điển; text cấp khoản trong đồ thị khớp phiên bản được dùng để trả lời |
| I | P2 | API trả file, bản HTML/PDF để xem nguồn và UI highlight | Tải đúng file theo citation; mở đúng đoạn trên đúng phiên bản nguồn; không phụ thuộc đường dẫn tuyệt đối của máy phát triển |
| J | P2 | So sánh snapshot, cập nhật index và benchmark | Phát hiện bản mới/thay đổi/biến mất; bảo toàn lịch sử; chỉ cập nhật phần bị ảnh hưởng; tạo phiên bản benchmark phù hợp khi corpus đổi |

## 5. Hợp đồng dữ liệu tối thiểu

Giữ bảng ánh xạ theo hướng đã chốt trong session, bổ sung đủ thông tin để tránh nhập nhằng:

```text
appfile_url, article_id, mapc, document_id, appendix_id,
kind, local_file, source_url, downloaded_at, download_status,
file_hash, review_status
```

Một quan hệ điều–URL có thể cần nhiều dòng khi dẫn tới nhiều phụ lục. Trường chưa xác định được để trống và đánh dấu cần rà soát; không tự gán số phụ lục chỉ từ tên file GUID.

Chunk phụ lục nên dùng chung các trường phiên bản/hiệu lực của pipeline hiện có, cộng thêm:

```text
chunk_id: 09-2020-tt-bldtbxh:pl-III:p1
chunk_type: appendix
document_id: 09-2020-tt-bldtbxh
appendix_id: III
linked_article_ids: [09-2020-tt-bldtbxh:d9]
file, rendered_file, text_start, text_end, quote, file_hash
```

Đây là schema đề xuất, chưa được triển khai. Có một điểm phải xử lý trước khi dùng ID này: `chunk_schema.article_id()` hiện dùng `split(":p", 1)`, nên cả `:pl1` lẫn `:pl-III:p1` đều bị cắt ngay tại tiền tố phụ lục, trả về riêng `document_id`. Nhiều phụ lục của một văn bản sẽ bị gom nhầm khi merge hoặc khử trùng lặp kết quả. Cần sửa bộ đọc ID để chỉ nhận hậu tố phần dạng `:p<số>` ở cuối, hoặc chọn định danh phụ lục tương thích rồi thống nhất giữa các nơi sinh chunk.

Không cần tạo ontology phụ lục riêng ở giai đoạn này. Bảng ánh xạ và metadata chung đủ để hoàn thành luồng đầu tiên; cấu trúc RDF có thể bổ sung khi xuất hiện nhu cầu truy vấn cụ thể.

## 6. Thứ tự thực hiện và phạm vi bản đầu tiên

1. Hoàn thành A–C: bảo vệ quan hệ hiện có, kiểm kê đầy đủ và chốt dữ liệu đầu vào/đầu ra.
2. Thực hiện D–E trên TT 09/2020 trước: lấy đúng file, đọc được danh mục, liên kết II với Điều 8, III–IV với Điều 9, V với Điều 10 theo snapshot đang có. Xác minh hiệu lực trước khi dùng cho câu trả lời về pháp luật hiện hành.
3. Thực hiện F–G: trả lời có nội dung danh mục, có bằng chứng cụ thể và xử lý được trường hợp thiếu file.
4. Thực hiện H trước khi đưa thêm phiên bản luật/PDF vào luồng trả lời chính; việc rà metadata có thể làm đồng thời với thu thập phụ lục.
5. Mở rộng dần sang 29 văn bản còn lại, ưu tiên danh mục; sau đó triển khai I–J.

Bản đầu tiên đạt yêu cầu khi một câu hỏi về danh mục lấy được đúng chunk phụ lục, giữ được điều luật làm căn cứ, xuất trích dẫn có thể kiểm tra, và báo thiếu nguồn khi file chưa được khôi phục. UI highlight và tải toàn bộ biểu mẫu có thể triển khai sau.

## 7. Kiểm chứng cần có khi triển khai

- Kiểm kê khớp baseline 1.407 điều, 156 link, 121 điều có link, 30 văn bản; phân biệt đếm bản ghi với mã Pháp điển duy nhất vì nguồn có mã lặp.
- Chạy lại kiểm kê không ghi đè file đã tải hoặc các phân loại đã duyệt; nhiều URL cùng nội dung có thể dùng chung file theo hash nhưng vẫn giữ quan hệ nguồn.
- File chứa cả biểu mẫu và danh mục vẫn index phần danh mục; các bảng dài giữ được tiêu đề cột và điều kiện áp dụng khi cắt chunk.
- Câu hỏi đi trực tiếp tới phụ lục và câu hỏi bắt đầu từ điều luật đều nhận đủ bằng chứng; không chỉ thử vector tìm trúng tên phụ lục.
- Trích dẫn phụ lục sai, thiếu file và offset lệch phiên bản đều có trường hợp kiểm tra riêng.
- Kiểm tra ngày trước, đúng và sau mốc hiệu lực; thay thế toàn bộ và bãi bỏ một phần; không coi bản ghi mất khỏi snapshot là kết luận hết hiệu lực.
- Không ghi đè bộ benchmark đã đóng băng. Khi corpus đổi, tạo phiên bản tương ứng; bổ sung câu hỏi có gold là phụ lục vì chấm chỉ theo MAPC điều luật chưa đo được việc lấy đủ danh mục.

Các phép kiểm tra trong lần phân tích này là đọc và đối chiếu dữ liệu cục bộ; chưa chạy bộ test hoặc benchmark, chưa gọi LLM và chưa thay đổi index.

## 8. Các file chính để bắt đầu

- [Parser HTML](../labor_rag/ingest/parse_demuc_html.py), [dựng ABox](../labor_rag/ingest/build_abox.py), [chiếu JSONL](../labor_rag/ingest/ontology_to_jsonl.py).
- [Chunk PDF](../labor_rag/ingest/pdf_to_chunks.py), [merge phiên bản](../labor_rag/ingest/merge.py), [embedding và đồng bộ hiệu lực](../labor_rag/ingest/embed_and_index.py).
- [Retrieval](../labor_rag/retrieval/hybrid_retrieve.py), [rerank](../labor_rag/retrieval/rerank.py), [sinh câu trả lời](../labor_rag/generation/answer.py), [kiểm tra trích dẫn](../labor_rag/generation/citation_verify.py).
- [Trạng thái OCR và phần thiếu của PDF](SESSION_2026-10-19.md), [schema JSONL hiện tại](structural_jsonl.md).

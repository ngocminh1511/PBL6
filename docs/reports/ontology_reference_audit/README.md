# Kiểm chứng giá trị của tham chiếu chéo trong truy hồi

Ngày kiểm tra: **03/11/2026**. Collection: `legal_ld_v5_bge`; embedding: `BAAI/bge-m3` trên Modal. Không gọi LLM.

**Đã xác minh 3 câu có thông tin cần thiết nằm ngoài top-8 vector và được lấy thêm qua cạnh dẫn chiếu thật trên Neo4j.** Cấu trúc Pháp điển vẫn chứa các đoạn chỉ dẫn sang điều khác, thay vì chép toàn bộ nội dung được dẫn chiếu vào cùng một chunk.

## Cách kiểm tra

1. Dò 79 câu: 18 câu viết để kiểm tra tình huống/đối chứng và 61 câu lấy từ bộ câu hỏi có sẵn. Nhãn có sẵn chỉ dùng để tìm ứng viên.
2. Giữ cách lấy top-8 của `HybridRetriever.vector_search`: lấy 16 chunk vector, gộp theo điều/phụ lục rồi chọn tối đa 8 kết quả. Dùng collection đang có và bộ lọc hiệu lực tại ngày kiểm tra. Đây khác với màn kiểm tra phụ lục đang hiển thị top-8 chunk thô.
3. Lấy thêm tối đa 50 chunk vector để xem điều đích nằm ở đâu, không dùng chúng làm đầu vào mở rộng graph.
4. Dò các cạnh `CITES_COMPONENT`/`IMPLEMENTS_COMPONENT` trong bản chiếu ontology để tìm ứng viên. Có 11 câu có điều đích dự kiến bị thiếu trong top-8; con số này **không phải** 11 câu đã chứng minh cần ontology.
5. Với 3 câu được chọn sau khi đọc nội dung, chạy truy vấn thật trên Neo4j và hàm `HybridRetriever.reference_expand(..., limit_per_node=3)` với đúng các kết quả vector đã lưu. Xác nhận điều đích và nội dung của nó tồn tại trên Qdrant, đồng thời kiểm tra các thông tin cụ thể có xuất hiện trong ngữ cảnh trước/sau hay không.

## Ba câu đã xác minh

### 1. Nội dung hội nghị người lao động

**Câu hỏi:** Hội nghị người lao động hằng năm do ai tổ chức và được bàn những vấn đề gì?

- Qdrant xếp **Điều 47 Nghị định 145/2020/NĐ-CP** ở hạng 1, điểm **0,6409**.
- Điều 47 cho biết bên tổ chức, nhưng khoản 2 dẫn sang **Điều 64 Bộ luật Lao động** cho nội dung hội nghị.
- Điều 64 không nằm trong top-8, và cũng không xuất hiện trong 50 chunk vector đã dò thêm.
- Cạnh thật: **Khoản 2 Điều 47 NĐ 145 → `CITES_COMPONENT` → Điều 64 Bộ luật 45/2019/QH14**.
- Hàm mở rộng mặc định trả được nội dung Điều 64. Chẳng hạn, nội dung về tình hình sản xuất, kinh doanh của người sử dụng lao động không có trong top-8 ban đầu, nhưng có trong nội dung lấy thêm.
- Một số cụm chung như “điều kiện làm việc” đã có ở các đoạn khác trong top-8. Giá trị bổ sung ở đây là danh sách nội dung cụ thể mà Điều 47 dẫn tới, không phải mọi từ ngữ trong điều đích đều mới.

ID kiểm tra: `manual08`; cũng có biến thể từ bộ câu hỏi sẵn là `ld048`.

### 2. Thành phần cuộc họp xử lý bồi thường thiệt hại

**Câu hỏi:** Cuộc họp xử lý bồi thường thiệt hại do người lao động làm hỏng tài sản phải có những ai tham gia?

- Qdrant xếp **Điều 71 Nghị định 145/2020/NĐ-CP** ở hạng 1, điểm **0,6938**.
- Điều này nêu cuộc họp và thẩm định viên về giá nếu có, nhưng dẫn sang **điểm b, c khoản 1 Điều 122 Bộ luật Lao động** cho các thành phần còn lại.
- Điều 122 không nằm trong top-8. Trong danh sách gộp theo điều từ 50 chunk vector, nó ở hạng **41**.
- Hai cạnh thật: **Khoản 2 Điều 71 NĐ 145 → `CITES_COMPONENT` → điểm b và điểm c khoản 1 Điều 122**.
- Nội dung lấy thêm có điều kiện về tổ chức đại diện mà người lao động là thành viên, quyền tham gia/bào chữa của người lao động và trường hợp cần người đại diện theo pháp luật cho người chưa đủ 15 tuổi. Những đoạn cụ thể được đánh dấu trong `verified.json` đều thiếu ở ngữ cảnh vector ban đầu.
- Truy vấn còn tìm được đường từ Điều 72 NĐ 145 tới khoản 4 Điều 122; đường đó không phải căn cứ chính cho câu hỏi về thành phần họp.

ID kiểm tra: `manual13`.

### 3. Tai nạn khi nhận việc gia công tại nhà

**Câu hỏi:** Người lao động nhận việc gia công tại nhà không thuộc diện đóng bảo hiểm tai nạn lao động thì được bên giao việc bảo đảm các quyền lợi gì khi bị tai nạn?

- **Điều 69 Luật An toàn, vệ sinh lao động 84/2015/QH13** có trong top-8, ở hạng 4, điểm **0,6093**.
- Khoản 2 Điều 69 dẫn sang các khoản 1–8 và 10 Điều 38 để xác định quyền lợi.
- Điều 38 không có trong top-8; nó ở hạng **13** trong danh sách gộp theo điều từ 50 chunk vector.
- Các cạnh thật nối **Khoản 2 Điều 69 → `CITES_COMPONENT` → các khoản tương ứng của Điều 38**.
- Hàm mở rộng mặc định lấy được thêm thông tin về chi phí y tế và cách tính bồi thường. Các dấu hiệu văn bản được kiểm tra, như mức “1,5 tháng tiền lương” và quy định thanh toán toàn bộ chi phí y tế cho người không tham gia bảo hiểm y tế, thiếu trong top-8 nhưng có ở kết quả mở rộng.
- Top-8 cũng có Điều 40 và Điều 39 dẫn về Điều 38. Vì vậy đây là một ví dụ có nhiều đường hợp lệ tới điều đích, không phải chỉ có duy nhất đường đi qua Điều 69.

ID kiểm tra: `manual15`.

## Các đối chứng và ứng viên bị loại

- `control01`: câu hỏi về mức khấu trừ lương tối đa đã tìm được Điều 102 Bộ luật ở hạng 2.
- `control02`: câu hỏi về thời hạn tạm đình chỉ đã tìm được Điều 128 ở hạng 1.
- `control03`: câu hỏi về nghỉ phép và thâm niên đã tìm được cả Điều 113, 114 ở hạng 1, 2.
- `kg_ref_41`: hỏi thời hạn thanh toán khi nghỉ việc; Điều 48 có sẵn và đủ cho trọng tâm câu hỏi. Việc graph thêm Điều 46 về trợ cấp không chứng minh được lợi ích trả lời.
- `kg_ref_42`: hỏi xác nhận thời gian đóng và trả giấy tờ bảo hiểm; thêm Điều 47 về trợ cấp mất việc không giải quyết trọng tâm đó.
- `kg_ref_50`: nghĩa vụ chi trả bảo hiểm cho người giúp việc đã có ở Điều 163 và Điều 89 trong top-8; Điều 90 được thêm nói về thông báo cho địa phương.
- `kg_ref_38`: Điều 46 bị thiếu, nhưng Điều 8 NĐ 145 đã có trong top-8 và cung cấp một số nội dung tính trợ cấp tương ứng. Không chọn làm minh chứng rõ về nội dung chỉ graph mới bổ sung.

Có đường tham chiếu hoặc được gắn nhãn `graph_expanded` chưa đủ chứng minh điều đích cần thiết. Phải đọc nội dung câu hỏi và ngữ cảnh đã có.

## Kết luận trong phạm vi kiểm tra

Các trường hợp rõ nhất là **câu hỏi về thủ tục, thành phần, điều kiện hoặc quyền lợi được quy định bằng dẫn chiếu**. Chunk nguồn khớp ngữ nghĩa với tình huống, trong khi chunk đích dùng thuật ngữ khác hoặc có tiêu đề chung nên nằm ngoài ngân sách vector.

Kết quả này chứng minh thông tin tham chiếu chéo vẫn có ích trong corpus Pháp điển đang dùng. Nó không chứng minh ontology luôn cần thiết, cũng không phải phép đánh giá chất lượng trả lời hay tỷ lệ cải thiện trên câu hỏi thực tế. Tăng top-k hoặc thay câu hỏi/model có thể khiến Qdrant tìm được điều đích trực tiếp.

Màn `/api/retrieve` hiện tập trung vào đường điều–phụ lục. Kiểm tra này dùng riêng hàm `reference_expand` của bộ truy hồi hybrid để xác minh các tham chiếu giữa các điều. Giao diện và mã truy hồi ứng dụng chưa thay đổi trong lượt kiểm tra này.

## File và cách chạy lại

- `manual_questions.jsonl`: 18 câu kiểm tra ban đầu, gồm 3 câu đối chứng.
- `questions.jsonl`: toàn bộ 79 câu đã chạy, kèm các đích dự kiến để tìm ứng viên.
- `discovery.json`: cấu hình, hash corpus, kết quả vector và các cạnh ứng viên; các cạnh ở bước này lấy từ bản chiếu ontology local.
- `verified.json`: kết quả xác nhận trực tiếp trên Neo4j/Qdrant và các dấu hiệu nội dung trước/sau cho 3 câu.

Từ thư mục gốc dự án:

```powershell
python scripts/audit_cross_references.py --questions docs/reports/ontology_reference_audit/questions.jsonl --output docs/reports/ontology_reference_audit/discovery.json --as-of 2026-11-03
python scripts/verify_reference_audit.py --discovery docs/reports/ontology_reference_audit/discovery.json --output docs/reports/ontology_reference_audit/verified.json
```

Lệnh đầu gọi embedding trên backend cấu hình sẵn và đọc Qdrant. Lệnh thứ hai dùng lại kết quả vector, đọc Neo4j/Qdrant và gọi hàm mở rộng tham chiếu; không tạo embedding mới. Các lần chạy sau có thể khác do dữ liệu, hiệu lực và dịch vụ thay đổi.

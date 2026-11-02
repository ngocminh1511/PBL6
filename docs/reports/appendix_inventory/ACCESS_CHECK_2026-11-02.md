# Kiểm tra truy cập tự động vbpl.vn

Ngày kiểm tra: 02/11/2026. Mục đích: kiểm chứng nhận định “vbpl.vn chặn bot nên bắt buộc tải tay” sau khi người dùng xác nhận xem được phụ lục trong trình duyệt.

## Kết luận

**Đã lấy tự động được cả nội dung HTML, PDF và Word của TT 09/2020 từ URL mới người dùng cung cấp. Nhận định bắt buộc tải tay không đúng với trường hợp đã kiểm tra này.** HTTP 403 trên trang giao diện phụ thuộc vào User-Agent; API tải file công khai của giao diện mới nhận yêu cầu và trả file được ngay cả với User-Agent mặc định của Python.

Thử nghiệm trên máy hiện tại cho thấy chỉ đổi `User-Agent` đã làm kết quả thay đổi. Điều này là bằng chứng phù hợp với một bộ lọc theo User-Agent; chưa xác định được toàn bộ cơ chế bảo vệ, quy tắc IP, phiên truy cập hoặc yêu cầu JavaScript của trang văn bản mới.

## Kết quả với URL mới do người dùng cung cấp

Trang được kiểm tra:

[TT 09/2020 trên giao diện hiện tại của vbpl.vn](https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-09-2020-tt-bldtbxh-quy-dinh-chi-tiet-va-huong-dan-thi-hanh-mot-so-dieu-cua-bo-luat-lao-dong-ve-lao-dong-chua-thanh-nien--152670).

| Yêu cầu | Kết quả |
|---|---|
| URL mới, Python mặc định | 403, trang lỗi |
| Cùng URL, chỉ đặt `User-Agent: Mozilla/5.0` | 200 tại đúng URL văn bản, tiêu đề đúng TT 09/2020 |
| Đọc nội dung từ dữ liệu trang gửi kèm | Trích xuất được HTML 79.067 ký tự, text 40.281 ký tự; có tiêu đề Phụ lục I–V |
| API công khai tải PDF, Python mặc định | 200, dấu đầu file đúng `%PDF-` |
| API công khai tải Word, Python mặc định | 200, dấu đầu file đúng định dạng Word OLE |
| Tải và lưu toàn bộ PDF/Word bằng User-Agent Mozilla | Thành công; không dùng tài khoản, cookie, token hoặc giải CAPTCHA |

Nội dung thông tư nằm trong dữ liệu React/Next.js gửi kèm trang, không phải các thẻ nội dung đã dựng sẵn trong phần HTML hiển thị ban đầu. Chỉ dùng `BeautifulSoup.get_text()` trên trang ngoài sẽ đọc được khoảng 266 ký tự của khung giao diện; cần giải mã dữ liệu trang rồi lấy HTML văn bản bên trong. Đã kiểm tra các tiêu đề phụ lục và nội dung danh mục thực tế, thay vì chỉ tìm các câu dẫn “ban hành kèm theo”.

API tải file được xác định từ chính mã giao diện công khai, với mẫu đường dẫn:

```text
https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/minio/buckets/vbpl/{document_id}/{file_name}/download
```

`document_id=152670`, tên file được lấy từ metadata trang, không đoán từ GUID AppFile cũ. Đây là endpoint công khai mà giao diện dùng để tải/xem file; không có bước đăng nhập hoặc vượt kiểm soát truy cập trong phép thử này.

Đã lưu các mẫu kiểm chứng:

- [Bản Word gốc tải được](samples/09_2020_tt_bldtbxh.original.doc): 251.392 byte; kiểm tra dấu đầu file OLE.
- [Bản PDF gốc tải được](samples/09_2020_tt_bldtbxh.original.pdf): 2.713.463 byte, 25 trang; đọc được 39.161 ký tự, có các dấu mốc Phụ lục I–V. Bản này là file từ vbpl.vn, khác cách dàn trang của bản Công báo 26 trang đã kiểm tra trước.
- [HTML nội dung đã trích xuất](samples/09_2020_tt_bldtbxh.vbpl.html), [text nội dung](samples/09_2020_tt_bldtbxh.vbpl.txt).
- [Metadata và hash của mẫu HTML](samples/09_2020_tt_bldtbxh.vbpl.json), [kết quả kiểm tra API tải file](samples/09_2020_tt_bldtbxh.download_check.json).

Các file này là mẫu chẩn đoán, chưa nhập vào bảng ánh xạ AppFile hoặc index. Chưa kiểm tra tương tự toàn bộ 38 mục thu thập; kết quả này chứng minh phương án lấy tự động khả thi cho TT 09/2020, không khẳng định mọi văn bản đều hoạt động giống nhau.

## Đối chiếu với URL cũ

Công cụ: Python 3.12 `urllib.request`. Không dùng tài khoản, cookie trình duyệt hoặc token. So sánh cùng URL, cùng phương thức GET; ở thử nghiệm chính chỉ thay header `User-Agent`. Tắt theo chuyển hướng để nhìn thấy mã và đích chuyển hướng gốc.

| Địa chỉ | User-Agent mặc định của Python | Chỉ đặt `User-Agent: Mozilla/5.0` |
|---|---|---|
| `https://vbpl.vn/` | 403 | 200, HTML trang chủ |
| `https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=152670` | 403 | 308, `Location: /` |
| URL PDF cũ dạng `/FileData/TW/Lists/vbpq/Attachments/152670/...pdf` tìm thấy qua tìm kiếm | 403 | 404, HTML, không phải PDF |

Kiểm tra bổ sung trên URL văn bản cũ:

- User-Agent mặc định, `Python-urllib/3.12` và `curl/8.0.0`: đều nhận 403.
- `Mozilla/5.0` và chuỗi User-Agent trình duyệt Chrome: đều nhận 308 về `/`.
- Chỉ thêm header `Accept` và giữ User-Agent mặc định: vẫn nhận 403.
- Tự động theo chuyển hướng với User-Agent Mozilla: nhận 200 tại `https://vbpl.vn/`, tiêu đề “Trang chủ | CSDL quốc gia về pháp luật”; không có nội dung TT 09/2020 hoặc Phụ lục II trong HTML nhận được.
- URL tương tự dưới `/bolaodong/Pages/` cũng nhận 403 với User-Agent mặc định; với các header trình duyệt thì cuối cùng về trang chủ.
- Công cụ duyệt web bên ngoài vẫn nhận 403. Kết quả công cụ đó không thể dùng để suy ra rằng mọi chương trình trên máy đều bị từ chối.

Header phản hồi có `Server: PWS/8.3.1.0.8`. Chỉ thông tin này chưa đủ xác định sản phẩm hoặc cấu hình chống bot. Trang chủ có ứng dụng JavaScript; thấy từ “captcha” trong mã trang cũng không chứng minh yêu cầu đang vướng CAPTCHA, nên không dùng dấu hiệu đó làm kết luận.

Không có kết nối trình duyệt khả dụng trong phiên kiểm tra này. Các kết quả ở trên là đo HTTP trực tiếp, không phải kết quả chạy và tương tác đầy đủ với giao diện JavaScript trong trình duyệt.

## Ý nghĩa đối với việc thu thập phụ lục

1. Ưu tiên kiểm tra cách lấy tự động từ giao diện và API hiện tại. Tải tay là phương án dự phòng cho những văn bản không lấy được.
2. Dùng ItemID/số hiệu từ HTML Pháp điển để nối sang văn bản trên giao diện mới. Không tiếp tục coi URL cũ `Pages/vbpq-toanvan.aspx?ItemID=...` là nguồn tải đang hoạt động.
3. Đọc metadata trang để lấy đúng tên file, rồi gọi endpoint tải file công khai của giao diện. Giữ nguồn, hash và thông tin phiên bản.
4. Kiểm tra dấu đầu file và nội dung thực tế. API thành công ở đây trả `application/octet-stream` cho cả PDF và Word, nên không thể chỉ dùng Content-Type để xác định định dạng.
5. Chạy thử trên thêm một số văn bản có file khác nhau trước khi xây bộ thu thập cho toàn bộ danh sách. Việc kiểm chứng khả năng truy cập không thay thế bước kiểm tra phiên bản/hiệu lực nội dung.

Các thử nghiệm này giữ nguyên HTML Pháp điển, ontology, index và các bảng CSV kiểm kê; chỉ bổ sung mẫu tải được và báo cáo chẩn đoán. Link cũ bị chuyển hướng/mất file và việc một kiểu yêu cầu bị trả 403 là hai vấn đề riêng biệt.

Các mẫu tải thử trong `samples/` được giữ trên máy và không đưa vào Git. Có thể tải lại nguồn bằng notebook thu thập; dữ liệu đã xử lý và báo cáo được quản lý phiên bản riêng.

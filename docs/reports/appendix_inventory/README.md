# Kiểm kê phụ lục và biểu mẫu trong HTML Lao động

Ngày phân tích: 02/11/2026. Phạm vi: toàn bộ 5 file trong `data/raw/bophapdien/linh_vuc/lao_dong/`.

## Kết quả để lập kế hoạch thu thập

**Danh sách thu thập có 38 mục văn bản/bộ phụ lục–biểu mẫu.** Trong đó, 32 văn bản được nhận diện qua file đính kèm; 5 văn bản chỉ được dẫn phụ lục trong nội dung; 1 nhóm biểu mẫu đánh số được dẫn mà không gọi là “phụ lục”. Đây là số mục cần tìm bản đầy đủ để đối chiếu và thu thập, không phải số file vật lý đã xác minh cần tải.

| Cách đếm | Số lượng | Ý nghĩa |
|---|---:|---|
| Điều trong 5 file | 1.407 | Đếm bản ghi điều, giữ cả các mã Pháp điển bị lặp |
| Điều có link đính kèm | 121 | Khoảng 8,6% số điều |
| URL file đính kèm khác nhau | 156 | 110 `.doc`, 46 `.docx` |
| Nhóm file theo văn bản và tên file chuẩn hóa | 91 | Danh sách đại diện để đối chiếu file; chưa chứng minh các URL cùng tên có cùng nội dung |
| Văn bản chứa các điều có link | 30 | Cách đếm sơ bộ trong session trước |
| Văn bản thực sự được tên file và ghi chú nguồn xác định | 32 | Tách thêm NĐ 70/2023 và TT 02/2024 từ các điều đã hợp nhất sửa đổi |
| Văn bản chỉ có dẫn chiếu phụ lục, không có link | 5 | Các trường hợp dễ bỏ sót khi chỉ quét AppFile |
| Nhóm biểu mẫu được dẫn thêm, không có link | 1 | NĐ 28/2015; cần đối chiếu NĐ 61/2020 |
| Tổng mục thu thập | **38** | 32 + 5 + 1 |
| Định danh phụ lục đánh số nhận diện được | 88 | Khóa là văn bản + số phụ lục; gồm cả phần đã có trong HTML; chưa bao gồm toàn bộ phụ lục không số và biểu mẫu |

Không thể quy đổi trực tiếp 156 URL, 91 nhóm tên file hoặc 88 định danh thành một con số file tải cuối cùng. Một file có thể chứa nhiều phụ lục; nhiều URL cùng tên cũng có thể là các bản sao hoặc các phiên bản khác nhau. Có thể tải một bản văn bản đầy đủ chứa toàn bộ phụ lục thay cho nhiều file rời nếu kiểm tra thấy nội dung tương ứng đầy đủ.

## Theo từng file nguồn

| File | Số điều | Link đính kèm | Điều có link |
|---|---:|---:|---:|
| `lao_dong.html` | 477 | 39 | 32 |
| `viec_lam.html` | 393 | 84 | 56 |
| `nguoi_lao_dong_viet_nam_di_lam_viec_o_nuoc_ngoai_theo_hop_dong.html` | 187 | 31 | 31 |
| `an_toan_ve_sinh_lao_dong.html` | 350 | 2 | 2 |
| `giao_duc_nghe_nghiep.html` | 0 | 0 | 0 |
| **Tổng** | **1.407** | **156** | **121** |

File giáo dục nghề nghiệp chỉ có 618 byte và không có điều; kết quả không đại diện cho nhu cầu phụ lục của lĩnh vực này ngoài snapshot hiện có.

## Sáu mục bổ sung ngoài các file có link

| Văn bản | Phần cần tìm | Bằng chứng trong HTML |
|---|---|---|
| 145/2020/NĐ-CP | Phụ lục I–VI; có cả biểu mẫu và danh mục | Các điều 20.2.NĐ.3 dẫn các phụ lục này; Điều 30 dẫn danh mục công việc được cho thuê lại lao động tại Phụ lục II |
| 02/2023/TT-BYT | Phụ lục số 35 | 20.5.TT.21.8 dẫn Mục 3 của phụ lục về bệnh nghề nghiệp COVID-19 |
| 08/2017/TT-BQP | Phụ lục II | 20.5.TT.51.3 dẫn danh mục đối tượng kiểm định |
| 10/2017/TT-BCT | Phụ lục tên/ký hiệu quy trình; kiểm tra kèm bộ quy trình | 20.5.TT.55.1 nêu 18 quy trình kiểm định và phụ lục của thông tư |
| 44/2016/NĐ-CP | Phụ lục Ib được dẫn từ văn bản khác | 20.5.TT.54.1 của TT 09/2017/TT-BCT dẫn rõ Phụ lục Ib của NĐ 44/2016; không gán phụ lục này cho TT 09/2017 |
| 28/2015/NĐ-CP, đối chiếu 61/2020/NĐ-CP | Các Mẫu số 01–05 trong phần nội dung đã sửa đổi | 20.4.NĐ.3.18, .24, .25 dẫn mẫu; ghi chú nguồn xác định có sửa đổi bởi NĐ 61/2020 |

Riêng mục cuối, cụm “Nghị định này” nằm trong nội dung đã hợp nhất. Chỉ từ HTML chưa chốt được từng mẫu phải lấy từ bản gốc hay văn bản sửa đổi. Khi thu thập, dùng bản hợp nhất có đủ mẫu hoặc đối chiếu cả NĐ 28/2015 và NĐ 61/2020. Vì vậy, danh sách có 38 mục; nếu tải riêng các văn bản trong mục này, có thể phải lấy thêm NĐ 61/2020. Số file vật lý vẫn phụ thuộc cách nguồn phát hành đóng gói.

## Hai văn bản sửa đổi cần tách riêng khi tải

- **70/2023/NĐ-CP:** 4 link tại các điều 20.2.NĐ.4.4, .6, .9, .11. Điều nguồn thuộc NĐ 152/2020, nhưng tên file ghi NĐ 70/2023 và ghi chú nguồn cũng xác nhận văn bản sửa đổi này. Sau tách, NĐ 152/2020 còn 15 link, 2 nhóm tên file; NĐ 70/2023 có 4 link, 1 nhóm tên file.
- **02/2024/TT-BLĐTBXH:** 2 link tại 20.3.TT.2.4 và .7. Điều nguồn thuộc TT 21/2021, nhưng file ghi TT 02/2024 và ghi chú nguồn khớp. Sau tách, TT 21/2021 có 6 link, 1 nhóm tên file; TT 02/2024 có 2 link, 1 nhóm tên file.

## Danh sách đầy đủ 38 mục

“Nhóm file” ở đây gom các URL có cùng văn bản và tên file sau chuẩn hóa khoảng trắng/hoa thường/dấu tiếng Việt. Không dùng tên file để khẳng định trùng nội dung hoặc tự động bỏ qua URL khi tải.

| Văn bản/bộ cần thu thập | Link cũ | Nhóm tên file |
|---|---:|---:|
| 01/2020/TT-BLĐTBXH | 12 | 12 |
| 01/2022/TT-BLĐTBXH | 4 | 1 |
| 02/2023/TT-BYT | 0 | — |
| 02/2024/TT-BLĐTBXH | 2 | 1 |
| 03/2016/TTLT-BLĐTBXH-BQP-BCA | 1 | 1 |
| 08/2017/TT-BQP | 0 | — |
| 09/2016/TTLT-BLĐTBXH-BTC | 3 | 3 |
| 09/2020/TT-BLĐTBXH | 6 | 1 |
| 09/2023/TT-BLĐTBXH | 1 | 1 |
| 10/2017/TT-BCT | 0 | — |
| 10/2020/TT-BLĐTBXH | 1 | 1 |
| 11/2017/TT-BLĐTBXH | 3 | 3 |
| 112/2021/NĐ-CP | 13 | 1 |
| 135/2020/NĐ-CP | 3 | 3 |
| 145/2020/NĐ-CP | 0 | — |
| 152/2020/NĐ-CP | 15 | 2 |
| 16/2022/TT-BLĐTBXH | 1 | 1 |
| 17/2023/TT-BLĐTBXH | 3 | 1 |
| 18/2021/TT-BLĐTBXH | 2 | 2 |
| 19/2016/TT-BLĐTBXH | 19 | 18 |
| 19/2021/TT-BLĐTBXH | 1 | 1 |
| 21/2021/TT-BLĐTBXH | 6 | 1 |
| 23/2021/NĐ-CP | 14 | 2 |
| 28/2015/NĐ-CP + đối chiếu 61/2020/NĐ-CP | 0 | — |
| 28/2015/TT-BLĐTBXH | 1 | 1 |
| 29/2021/TT-BYT | 1 | 1 |
| 293/2025/NĐ-CP | 1 | 1 |
| 31/2015/NĐ-CP | 1 | 1 |
| 38/2015/TT-BLĐTBXH | 6 | 6 |
| 40/2021/QĐ-TTg | 9 | 1 |
| 43/2016/TT-BLĐTBXH | 4 | 4 |
| 44/2016/NĐ-CP | 0 | — |
| 45/2015/TT-BLĐTBXH | 3 | 3 |
| 54/2016/TT-BLĐTBXH | 1 | 1 |
| 56/2015/TT-BLĐTBXH | 6 | 6 |
| 61/2015/NĐ-CP | 6 | 6 |
| 70/2023/NĐ-CP | 4 | 1 |
| 97/2022/NĐ-CP | 3 | 3 |
| **Tổng** | **156** | **91** |

## Ưu tiên khôi phục nội dung phục vụ hỏi đáp

Đây là ưu tiên theo nội dung được HTML mô tả, chưa phải phân loại cuối cùng của các file chưa tải.

| Văn bản | Lý do ưu tiên |
|---|---|
| 09/2020/TT-BLĐTBXH | Phụ lục II–V chứa các danh mục về lao động chưa thành niên; Phụ lục I là biểu mẫu |
| 145/2020/NĐ-CP | Có danh mục cho thuê lại lao động ở Phụ lục II nhưng không có link AppFile |
| 10/2020/TT-BLĐTBXH | Danh mục công việc ảnh hưởng xấu tới chức năng sinh sản và nuôi con |
| 135/2020/NĐ-CP | Bảng đối chiếu tuổi nghỉ hưu và danh mục công việc khai thác than trong hầm lò |
| 19/2021/TT-BLĐTBXH | Danh mục vùng đặc biệt khó khăn để xác định trường hợp nghỉ hưu sớm |
| 293/2025/NĐ-CP | Danh mục địa bàn áp dụng mức lương tối thiểu theo vùng |
| 112/2021/NĐ-CP | Phụ lục II chứa mức trần tiền ký quỹ; Phụ lục I có biểu mẫu |
| 21/2021/TT-BLĐTBXH và 02/2024/TT-BLĐTBXH | Có phụ lục về mức trần giá dịch vụ/tiền dịch vụ, đồng thời có các mẫu hợp đồng; cần đối chiếu sửa đổi |
| 31/2015/NĐ-CP | Danh mục công việc phải có chứng chỉ kỹ năng nghề quốc gia |
| 08/2017/TT-BQP và 44/2016/NĐ-CP | Danh mục liên quan đối tượng/hoạt động kiểm định |
| 02/2023/TT-BYT | Nội dung chuyên môn tại Phụ lục 35 về bệnh nghề nghiệp |
| 54/2016/TT-BLĐTBXH và 10/2017/TT-BCT | Phụ lục và các quy trình kiểm định; tên file của TT 54/2016 cần kiểm tra riêng |
| 09/2023/TT-BLĐTBXH và 16/2022/TT-BLĐTBXH | Nội dung định mức kinh tế kỹ thuật/chương trình đào tạo nằm trong file kèm theo |

Các mẫu đơn/báo cáo có thể thu thập sau để phục vụ xem và tải xuống. Chưa chốt số file `danh_muc` và `bieu_mau` vì nhiều file chứa cả hai loại, một số còn chứa quy trình hoặc chương trình đào tạo. Việc phân loại cần thực hiện ở cấp phần nội dung sau khi mở file.

## Các trường hợp phải xử lý riêng

1. **NĐ 97/2022 đã có nội dung phụ lục trong HTML.** Điều 20.2.NĐ.6.14 có khoảng 37 nghìn ký tự và các tiêu đề `PHỤ LỤC I`, `PHỤ LỤC II`, kèm quy trình và các mẫu. Có thể tận dụng phần text này trước; chưa khẳng định định dạng/bảng đã đầy đủ tương đương bản gốc. File gốc vẫn cần nếu cho người dùng tải xuống.
2. **Tên file lệch số hiệu:** điều 20.5.TT.48.1 có nguồn TT 54/2016, nhưng tên đính kèm ghi `54.2019`. Đã đánh dấu `filename_document_mismatch`, chưa tự đổi thành TT 54/2019.
3. **Phụ lục bị dẫn trong câu bãi bỏ:** Phụ lục I của NĐ 128/2025 được nhắc tại 20.2.NĐ.8.5 trong câu “Bãi bỏ…”. Đưa bằng chứng vào CSV nhưng không tính là mục cần tải để bổ sung nội dung đang được điều này dẫn áp dụng. Khi làm tra cứu lịch sử có thể thu thập riêng.
4. **Phụ lục do các bên tự lập:** loại các cụm “phụ lục hợp đồng lao động”, phụ lục nội quy của người sử dụng lao động và phụ lục quyết định hưởng trợ cấp của cá nhân khỏi danh sách phụ lục văn bản cần tải.
5. **Dẫn chiếu mẫu chưa xác định văn bản ban hành:** các câu chung như “theo mẫu do Bộ trưởng… quy định” hoặc mẫu điện tử trên một hệ thống chưa đủ để xác định một file cần tải. Không tự coi văn bản chứa câu đó là văn bản ban hành mẫu; cần xử lý khi triển khai từng thủ tục.

## Tệp bàn giao và cách chạy lại

- [documents.csv](documents.csv): 38 mục thu thập, số link, nhóm tên file, số phụ lục nhận diện, mẫu được dẫn, văn bản sửa đổi và link nguồn từ HTML.
- [file_groups.csv](file_groups.csv): 91 nhóm file đại diện, tên file, điều sử dụng, số URL cùng tên và trường cần kiểm tra.
- [attachment_links.csv](attachment_links.csv): toàn bộ 156 URL gốc, giữ riêng văn bản chứa điều và văn bản được tên file xác định.
- [numbered_appendices.csv](numbered_appendices.csv): 88 định danh phụ lục đánh số, kèm điều dẫn và đoạn bằng chứng.
- [appendix_references.csv](appendix_references.csv): bằng chứng dẫn chiếu phụ lục/biểu mẫu; giữ cả các trường hợp bị loại để rà soát.
- [summary.json](summary.json): số liệu tổng hợp và SHA-256 của từng HTML để kiểm tra snapshot.

CSV dùng UTF-8 có BOM để mở bằng Excel. `source_url` là nguồn văn bản lấy từ HTML, không đồng nghĩa với link tải đã kiểm tra hoạt động. Trạng thái tải để `not_checked` vì lần này chỉ kiểm kê cục bộ, chưa tải file hoặc xác minh hiệu lực trực tuyến.

Kiểm tra truy cập bổ sung sau bước kiểm kê: [ACCESS_CHECK_2026-11-02.md](ACCESS_CHECK_2026-11-02.md). **Đã lấy tự động được HTML có Phụ lục I–V và cả file Word/PDF của TT 09/2020 qua URL mới và API công khai của giao diện.** Trang giao diện có lọc theo User-Agent trong phép thử, nhưng API tải file vẫn trả 200 với Python mặc định. URL văn bản cũ chuyển hướng 308 về trang chủ. Vì vậy, ưu tiên kiểm tra bộ thu thập tự động cho các văn bản còn lại; tải tay là phương án dự phòng. Các CSV ở trên vẫn là kết quả kiểm kê ban đầu, chưa cập nhật trạng thái tải từ mẫu chẩn đoán này.

Chạy từ thư mục gốc repo:

```powershell
python -X utf8 scripts/inventory_appendices.py
```

Script chỉ sinh lại các bảng CSV/JSON; báo cáo README này là phần nhận xét đã rà soát và cần cập nhật nếu snapshot thay đổi. Script có kiểm tra đối chiếu tất cả link với DOM gốc, không gộp các điều có mã bị lặp, và kiểm tra tổng giữa bảng văn bản, bảng nhóm file và bảng phụ lục.

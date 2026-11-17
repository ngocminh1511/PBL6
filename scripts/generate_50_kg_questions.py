import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

# List of 50 curated cross-reference questions with real legal context in Vietnam Labor Code 2019 & Decree 145/2020
CURATED_50_KG = [
    {
        "id": "kg_ref_01",
        "question": "Khi người lao động nghỉ hằng năm thì có được tạm ứng trước tiền lương không và mức tạm ứng được tính thế nào?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.101",
        "src_ten": "Tạm ứng tiền lương",
        "src_chunk": "45-2019-qh14:d101",
        "tgt_mapc": "20.2.LQ.113",
        "tgt_ten": "Nghỉ hằng năm",
        "tgt_chunk": "45-2019-qh14:d113",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_02",
        "question": "Công ty có quyền trừ tiền lương của nhân viên để bồi thường thiệt hại do làm hỏng thiết bị không và mức khấu trừ tối đa là bao nhiêu?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.102",
        "src_ten": "Khấu trừ tiền lương",
        "src_chunk": "45-2019-qh14:d102",
        "tgt_mapc": "20.2.LQ.129",
        "tgt_ten": "Bồi thường thiệt hại",
        "tgt_chunk": "45-2019-qh14:d129",
        "category": "ky_luat_trach_nhiem_vat_chat"
    },
    {
        "id": "kg_ref_03",
        "question": "Quy chế thưởng của doanh nghiệp trước khi ban hành có phải tham khảo ý kiến tổ chức đại diện người lao động thông qua đối thoại tại nơi làm việc không?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.104",
        "src_ten": "Thưởng",
        "src_chunk": "45-2019-qh14:d104",
        "tgt_mapc": "20.2.LQ.63",
        "tgt_ten": "Tổ chức đối thoại tại nơi làm việc",
        "tgt_chunk": "45-2019-qh14:d63",
        "category": "doi_thoai_thuong_luong_cong_doan"
    },
    {
        "id": "kg_ref_04",
        "question": "Khi người lao động làm việc vượt quá thời giờ làm việc bình thường thì mức tiền lương làm thêm giờ được xác định ra sao?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.105",
        "src_ten": "Thời giờ làm việc bình thường",
        "src_chunk": "45-2019-qh14:d105",
        "tgt_mapc": "20.2.NĐ.3.55",
        "tgt_ten": "Tiền lương làm thêm giờ",
        "tgt_chunk": "145-2020-nd-cp:d55",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_05",
        "question": "Người làm việc vào ban đêm có được nghỉ giữa ca không và quy định về thời giờ nghỉ trong giờ làm việc ban đêm như thế nào?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.106",
        "src_ten": "Giờ làm việc ban đêm",
        "src_chunk": "45-2019-qh14:d106",
        "tgt_mapc": "20.2.NĐ.3.64",
        "tgt_ten": "Nghỉ trong giờ làm việc",
        "tgt_chunk": "145-2020-nd-cp:d64",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_06",
        "question": "Doanh nghiệp tổ chức làm thêm giờ thì số giờ làm thêm tối đa trong một ngày và trong một tháng được giới hạn như thế nào?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.107",
        "src_ten": "Làm thêm giờ",
        "src_chunk": "45-2019-qh14:d107",
        "tgt_mapc": "20.2.NĐ.3.60",
        "tgt_ten": "Giới hạn số giờ làm thêm",
        "tgt_chunk": "145-2020-nd-cp:d60",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_07",
        "question": "Những trường hợp và ngành nghề nào được phép tổ chức làm thêm giờ từ trên 200 giờ đến 300 giờ trong một năm?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.107",
        "src_ten": "Làm thêm giờ",
        "src_chunk": "45-2019-qh14:d107",
        "tgt_mapc": "20.2.NĐ.3.61",
        "tgt_ten": "Các trường hợp được tổ chức làm thêm từ trên 200 giờ đến 300 giờ trong một năm",
        "tgt_chunk": "145-2020-nd-cp:d61",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_08",
        "question": "Trường hợp nào người sử dụng lao động có quyền yêu cầu người lao động làm thêm giờ mà người lao động không được từ chối?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.108",
        "src_ten": "Làm thêm giờ trong trường hợp đặc biệt",
        "src_chunk": "45-2019-qh14:d108",
        "tgt_mapc": "20.2.NĐ.3.59",
        "tgt_ten": "Sự đồng ý của người lao động khi làm thêm giờ",
        "tgt_chunk": "145-2020-nd-cp:d59",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_09",
        "question": "Người lao động làm việc theo ca liên tục từ 6 giờ trở lên thì thời gian nghỉ giữa giờ được tính vào giờ làm việc theo điều kiện nào?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.109",
        "src_ten": "Nghỉ trong giờ làm việc",
        "src_chunk": "45-2019-qh14:d109",
        "tgt_mapc": "20.2.NĐ.3.64",
        "tgt_ten": "Nghỉ trong giờ làm việc",
        "tgt_chunk": "145-2020-nd-cp:d64",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_10",
        "question": "Người lao động làm công việc đặc biệt nặng nhọc, độc hại, nguy hiểm thì số ngày nghỉ hằng năm tăng thêm được quy định ra sao?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.113",
        "src_ten": "Nghỉ hằng năm",
        "src_chunk": "45-2019-qh14:d113",
        "tgt_mapc": "20.2.NĐ.3.65",
        "tgt_ten": "Thời gian được coi là thời gian làm việc để tính số ngày nghỉ hằng năm",
        "tgt_chunk": "145-2020-nd-cp:d65",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_11",
        "question": "Thời gian thử việc hoặc học nghề có được tính là thời gian làm việc để tính ngày nghỉ phép hằng năm không?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.113",
        "src_ten": "Nghỉ hằng năm",
        "src_chunk": "45-2019-qh14:d113",
        "tgt_mapc": "20.2.NĐ.3.66",
        "tgt_ten": "Cách tính số ngày nghỉ hằng năm trong một số trường hợp đặc biệt",
        "tgt_chunk": "145-2020-nd-cp:d66",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_12",
        "question": "Trường hợp người lao động chưa làm đủ 12 tháng thì cách tính số ngày nghỉ hằng năm theo tỷ lệ thời gian làm việc như thế nào?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "doi_thuong",
        "src_mapc": "20.2.LQ.113",
        "src_ten": "Nghỉ hằng năm",
        "src_chunk": "45-2019-qh14:d113",
        "tgt_mapc": "20.2.NĐ.3.67",
        "tgt_ten": "Thanh toán tiền lương những ngày chưa nghỉ hằng năm hoặc chưa nghỉ hết số ngày nghỉ hằng năm",
        "tgt_chunk": "145-2020-nd-cp:d67",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_13",
        "question": "Khi thôi việc hoặc mất việc làm mà chưa nghỉ hết phép năm thì tiền lương những ngày chưa nghỉ được thanh toán tính theo căn cứ nào?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.113",
        "src_ten": "Nghỉ hằng năm",
        "src_chunk": "45-2019-qh14:d113",
        "tgt_mapc": "20.2.NĐ.3.67",
        "tgt_ten": "Thanh toán tiền lương những ngày chưa nghỉ hằng năm",
        "tgt_chunk": "145-2020-nd-cp:d67",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_14",
        "question": "Người lao động làm việc liên tục cho một người sử dụng lao động thì cứ bao nhiêu năm được cộng thêm một ngày phép năm?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.114",
        "src_ten": "Ngày nghỉ hằng năm tăng thêm theo thâm niên làm việc",
        "src_chunk": "45-2019-qh14:d114",
        "tgt_mapc": "20.2.LQ.113",
        "tgt_ten": "Nghỉ hằng năm",
        "tgt_chunk": "45-2019-qh14:d113",
        "category": "thoi_gio_lam_viec_nghi_ngoi"
    },
    {
        "id": "kg_ref_15",
        "question": "Những ngày nghỉ lễ, tết nào người lao động được nghỉ việc hưởng nguyên lương theo quy định hiện hành?",
        "de_muc": "20.2",
        "category": "thoi_gio_lam_viec_nghi_ngoi",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.112",
        "src_ten": "Nghỉ lễ, tết",
        "src_chunk": "45-2019-qh14:d112",
        "tgt_mapc": "20.2.LQ.98",
        "tgt_ten": "Tiền lương làm thêm giờ, làm việc vào ban đêm",
        "tgt_chunk": "45-2019-qh14:d98",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_16",
        "question": "Người lao động đi làm vào đúng ngày nghỉ lễ, tết thì được hưởng tiền lương làm thêm giờ tối thiểu bằng bao nhiêu phần trăm?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.98",
        "src_ten": "Tiền lương làm thêm giờ, làm việc vào ban đêm",
        "src_chunk": "45-2019-qh14:d98",
        "tgt_mapc": "20.2.NĐ.3.55",
        "tgt_ten": "Tiền lương làm thêm giờ",
        "tgt_chunk": "145-2020-nd-cp:d55",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_17",
        "question": "Tiền lương làm việc vào ban đêm được trả thêm ít nhất bao nhiêu phần trăm so với tiền lương ban ngày?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.98",
        "src_ten": "Tiền lương làm thêm giờ, làm việc vào ban đêm",
        "src_chunk": "45-2019-qh14:d98",
        "tgt_mapc": "20.2.NĐ.3.56",
        "tgt_ten": "Tiền lương làm việc vào ban đêm",
        "tgt_chunk": "145-2020-nd-cp:d56",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_18",
        "question": "Cách tính tiền lương làm thêm giờ vào ban đêm được hướng dẫn cụ thể theo công thức nào trong Nghị định 145?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.98",
        "src_ten": "Tiền lương làm thêm giờ, làm việc vào ban đêm",
        "src_chunk": "45-2019-qh14:d98",
        "tgt_mapc": "20.2.NĐ.3.57",
        "tgt_ten": "Tiền lương làm thêm giờ vào ban đêm",
        "tgt_chunk": "145-2020-nd-cp:d57",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_19",
        "question": "Người lao động phải ngừng việc do lỗi của người sử dụng lao động thì tiền lương ngừng việc được chi trả như thế nào?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.99",
        "src_ten": "Tiền lương ngừng việc",
        "src_chunk": "45-2019-qh14:d99",
        "tgt_mapc": "20.2.LQ.90",
        "tgt_ten": "Tiền lương",
        "tgt_chunk": "45-2019-qh14:d90",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_20",
        "question": "Trường hợp ngừng việc do sự cố điện nước hoặc thiên tai, dịch bệnh thì mức lương ngừng việc trong 14 ngày đầu được thỏa thuận không thấp hơn mức nào?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.99",
        "src_ten": "Tiền lương ngừng việc",
        "src_chunk": "45-2019-qh14:d99",
        "tgt_mapc": "20.2.LQ.91",
        "tgt_ten": "Mức lương tối thiểu",
        "tgt_chunk": "45-2019-qh14:d91",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_21",
        "question": "Mức lương tối thiểu được xác lập theo vùng và ấn định theo những tiêu chí đánh giá đời sống nào?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.91",
        "src_ten": "Mức lương tối thiểu",
        "src_chunk": "45-2019-qh14:d91",
        "tgt_mapc": "20.2.LQ.92",
        "tgt_ten": "Hội đồng tiền lương quốc gia",
        "tgt_chunk": "45-2019-qh14:d92",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_22",
        "question": "Doanh nghiệp xây dựng thang lương, bảng lương có bắt buộc phải tham khảo ý kiến tổ chức đại diện người lao động tại cơ sở không?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.93",
        "src_ten": "Xây dựng thang lương, bảng lương và định mức lao động",
        "src_chunk": "45-2019-qh14:d93",
        "tgt_mapc": "20.2.LQ.63",
        "tgt_ten": "Tổ chức đối thoại tại nơi làm việc",
        "tgt_chunk": "45-2019-qh14:d63",
        "category": "doi_thoai_thuong_luong_cong_doan"
    },
    {
        "id": "kg_ref_23",
        "question": "Tiền lương ghi trong hợp đồng lao động và tiền lương trả cho người lao động bằng tiền Việt Nam Đồng hay ngoại tệ?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "doi_thuong",
        "src_mapc": "20.2.LQ.95",
        "src_ten": "Trả lương",
        "src_chunk": "45-2019-qh14:d95",
        "tgt_mapc": "20.2.NĐ.3.54",
        "tgt_ten": "Hình thức trả lương",
        "tgt_chunk": "145-2020-nd-cp:d54",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_24",
        "question": "Người sử dụng lao động trả lương qua tài khoản ngân hàng của người lao động thì các loại phí mở và duy trì tài khoản do ai trả?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.96",
        "src_ten": "Hình thức trả lương",
        "src_chunk": "45-2019-qh14:d96",
        "tgt_mapc": "20.2.NĐ.3.54",
        "tgt_ten": "Hình thức trả lương",
        "tgt_chunk": "145-2020-nd-cp:d54",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_25",
        "question": "Trường hợp vì lý do bất khả kháng mà người sử dụng lao động chậm trả lương thì được chậm tối đa bao nhiêu ngày và phải đền bù thế nào?",
        "de_muc": "20.2",
        "category": "tien_luong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.97",
        "src_ten": "Kỳ hạn trả lương",
        "src_chunk": "45-2019-qh14:d97",
        "tgt_mapc": "20.2.LQ.95",
        "tgt_ten": "Trả lương",
        "tgt_chunk": "45-2019-qh14:d95",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_26",
        "question": "Hợp đồng lao động xác định thời hạn có thể được ký tối đa bao nhiêu lần trước khi phải chuyển thành không xác định thời hạn?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.20",
        "src_ten": "Loại hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d20",
        "tgt_mapc": "20.2.LQ.22",
        "tgt_ten": "Hiệu lực của hợp đồng lao động",
        "tgt_chunk": "45-2019-qh14:d22",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_27",
        "question": "Hợp đồng lao động phải có những nội dung chủ yếu nào theo quy định của Bộ luật Lao động và Thông tư hướng dẫn?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.21",
        "src_ten": "Nội dung hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d21",
        "tgt_mapc": "20.2.TT.2.3",
        "tgt_ten": "Nội dung chủ yếu của hợp đồng lao động",
        "tgt_chunk": "10-2020-tt-bldtbxh:d3",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_28",
        "question": "Khi thuê người lao động làm công việc liên quan trực tiếp đến bí mật kinh doanh thì thỏa thuận bảo vệ bí mật công nghệ được thực hiện ra sao?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.21",
        "src_ten": "Nội dung hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d21",
        "tgt_mapc": "20.2.TT.2.4",
        "tgt_ten": "Hợp đồng lao động với người lao động làm việc trong lĩnh vực bí mật kinh doanh, bí mật công nghệ",
        "tgt_chunk": "10-2020-tt-bldtbxh:d4",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_29",
        "question": "Thời gian thử việc tối đa đối với vị trí quản lý doanh nghiệp và công việc đòi hỏi trình độ đại học trở lên là bao nhiêu ngày?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.25",
        "src_ten": "Thời gian thử việc",
        "src_chunk": "45-2019-qh14:d25",
        "tgt_mapc": "20.2.LQ.26",
        "tgt_ten": "Tiền lương thử việc",
        "tgt_chunk": "45-2019-qh14:d26",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_30",
        "question": "Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận nhưng ít nhất phải bằng bao nhiêu phần trăm lương chính thức?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "doi_thuong",
        "src_mapc": "20.2.LQ.26",
        "src_ten": "Tiền lương thử việc",
        "src_chunk": "45-2019-qh14:d26",
        "tgt_mapc": "20.2.LQ.27",
        "tgt_ten": "Kết thúc thời gian thử việc",
        "tgt_chunk": "45-2019-qh14:d27",
        "category": "tien_luong"
    },
    {
        "id": "kg_ref_31",
        "question": "Khi kết thúc thời gian thử việc mà đạt yêu cầu thì người sử dụng lao động phải ký hợp đồng lao động với người lao động khi nào?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.27",
        "src_ten": "Kết thúc thời gian thử việc",
        "src_chunk": "45-2019-qh14:d27",
        "tgt_mapc": "20.2.LQ.24",
        "tgt_ten": "Thử việc",
        "tgt_chunk": "45-2019-qh14:d24",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_32",
        "question": "Công ty có được điều chuyển người lao động sang làm công việc khác so với hợp đồng không và được chuyển tối đa bao nhiêu ngày trong một năm?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.29",
        "src_ten": "Chuyển người lao động làm công việc khác so với hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d29",
        "tgt_mapc": "20.2.LQ.90",
        "tgt_ten": "Tiền lương",
        "tgt_chunk": "45-2019-qh14:d90",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_33",
        "question": "Những trường hợp nào người lao động được tạm hoãn thực hiện hợp đồng lao động theo luật định?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.30",
        "src_ten": "Tạm hoãn thực hiện hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d30",
        "tgt_mapc": "20.2.LQ.31",
        "tgt_ten": "Nhận lại người lao động hết thời hạn tạm hoãn thực hiện hợp đồng lao động",
        "tgt_chunk": "45-2019-qh14:d31",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_34",
        "question": "Hết thời hạn tạm hoãn hợp đồng lao động thì trong vòng bao nhiêu ngày người lao động phải có mặt tại nơi làm việc để công ty bố trí công việc?",
        "de_muc": "20.2",
        "category": "hop_dong_lao_dong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.31",
        "src_ten": "Nhận lại người lao động hết thời hạn tạm hoãn thực hiện hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d31",
        "tgt_mapc": "20.2.LQ.30",
        "tgt_ten": "Tạm hoãn thực hiện hợp đồng lao động",
        "tgt_chunk": "45-2019-qh14:d30",
        "category": "hop_dong_lao_dong"
    },
    {
        "id": "kg_ref_35",
        "question": "Người lao động làm việc theo hợp đồng không xác định thời hạn muốn đơn phương chấm dứt hợp đồng thì phải báo trước bao nhiêu ngày?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.35",
        "src_ten": "Quyền đơn phương chấm dứt hợp đồng lao động của người lao động",
        "src_chunk": "45-2019-qh14:d35",
        "tgt_mapc": "20.2.NĐ.3.7",
        "tgt_ten": "Thời hạn báo trước khi đơn phương chấm dứt hợp đồng lao động đối với một số ngành, nghề, công việc đặc thù",
        "tgt_chunk": "145-2020-nd-cp:d7",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_36",
        "question": "Người lái máy bay hoặc thuyền viên làm việc trên tàu biển thì thời hạn báo trước khi đơn phương chấm dứt hợp đồng lao động là bao lâu?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.35",
        "src_ten": "Quyền đơn phương chấm dứt hợp đồng lao động của người lao động",
        "src_chunk": "45-2019-qh14:d35",
        "tgt_mapc": "20.2.NĐ.3.7",
        "tgt_ten": "Thời hạn báo trước khi đơn phương chấm dứt hợp đồng lao động đối với công việc đặc thù",
        "tgt_chunk": "145-2020-nd-cp:d7",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_37",
        "question": "Doanh nghiệp có quyền đơn phương chấm dứt hợp đồng khi người lao động thường xuyên không hoàn thành công việc theo tiêu chí nào?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.36",
        "src_ten": "Quyền đơn phương chấm dứt hợp đồng lao động của người sử dụng lao động",
        "src_chunk": "45-2019-qh14:d36",
        "tgt_mapc": "20.2.LQ.63",
        "tgt_ten": "Tổ chức đối thoại tại nơi làm việc",
        "tgt_chunk": "45-2019-qh14:d63",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_38",
        "question": "Khi người sử dụng lao động đơn phương chấm dứt hợp đồng lao động trái pháp luật thì phải bồi thường những khoản tiền nào cho người lao động?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.41",
        "src_ten": "Nghĩa vụ của người sử dụng lao động khi đơn phương chấm dứt hợp đồng lao động trái pháp luật",
        "src_chunk": "45-2019-qh14:d41",
        "tgt_mapc": "20.2.LQ.46",
        "tgt_ten": "Trợ cấp thôi việc",
        "tgt_chunk": "45-2019-qh14:d46",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_39",
        "question": "Thời gian làm việc để tính trợ cấp thôi việc là tổng thời gian người lao động đã làm việc thực tế trừ đi thời gian nào?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.46",
        "src_ten": "Trợ cấp thôi việc",
        "src_chunk": "45-2019-qh14:d46",
        "tgt_mapc": "20.2.NĐ.3.8",
        "tgt_ten": "Trợ cấp thôi việc, trợ cấp mất việc làm",
        "tgt_chunk": "145-2020-nd-cp:d8",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_40",
        "question": "Tiền lương để tính trợ cấp mất việc làm được căn cứ theo tiền lương bình quân của bao nhiêu tháng liền kề trước khi mất việc?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.47",
        "src_ten": "Trợ cấp mất việc làm",
        "src_chunk": "45-2019-qh14:d47",
        "tgt_mapc": "20.2.NĐ.3.8",
        "tgt_ten": "Trợ cấp thôi việc, trợ cấp mất việc làm",
        "tgt_chunk": "145-2020-nd-cp:d8",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_41",
        "question": "Trong thời hạn bao nhiêu ngày kể từ ngày chấm dứt hợp đồng lao động, hai bên có trách nhiệm thanh toán đầy đủ các khoản tiền liên quan?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.48",
        "src_ten": "Trách nhiệm khi chấm dứt hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d48",
        "tgt_mapc": "20.2.LQ.46",
        "tgt_ten": "Trợ cấp thôi việc",
        "tgt_chunk": "45-2019-qh14:d46",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_42",
        "question": "Công ty có phải hoàn thành thủ tục xác nhận thời gian đóng bảo hiểm xã hội và trả lại sổ bảo hiểm cho người lao động khi họ nghỉ việc không?",
        "de_muc": "20.2",
        "category": "cham_dut_hop_dong",
        "style": "doi_thuong",
        "src_mapc": "20.2.LQ.48",
        "src_ten": "Trách nhiệm khi chấm dứt hợp đồng lao động",
        "src_chunk": "45-2019-qh14:d48",
        "tgt_mapc": "20.2.LQ.47",
        "tgt_ten": "Trợ cấp mất việc làm",
        "tgt_chunk": "45-2019-qh14:d47",
        "category": "cham_dut_hop_dong"
    },
    {
        "id": "kg_ref_43",
        "question": "Người sử dụng lao động sử dụng từ bao nhiêu lao động trở lên thì nội quy lao động bắt buộc phải bằng văn bản?",
        "de_muc": "20.2",
        "category": "ky_luat_trach_nhiem_vat_chat",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.118",
        "src_ten": "Nội quy lao động",
        "src_chunk": "45-2019-qh14:d118",
        "tgt_mapc": "20.2.NĐ.3.69",
        "tgt_ten": "Nội quy lao động",
        "tgt_chunk": "145-2020-nd-cp:d69",
        "category": "ky_luat_trach_nhiem_vat_chat"
    },
    {
        "id": "kg_ref_44",
        "question": "Hồ sơ đăng ký nội quy lao động gửi cơ quan chuyên môn về lao động cấp tỉnh bao gồm những loại tài liệu nào?",
        "de_muc": "20.2",
        "category": "ky_luat_trach_nhiem_vat_chat",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.120",
        "src_ten": "Hồ sơ đăng ký nội quy lao động",
        "src_chunk": "45-2019-qh14:d120",
        "tgt_mapc": "20.2.LQ.119",
        "tgt_ten": "Đăng ký nội quy lao động",
        "tgt_chunk": "45-2019-qh14:d119",
        "category": "ky_luat_trach_nhiem_vat_chat"
    },
    {
        "id": "kg_ref_45",
        "question": "Khi xử lý kỷ luật lao động, thành phần tham dự cuộc họp xử lý kỷ luật bắt buộc phải có những ai?",
        "de_muc": "20.2",
        "category": "ky_luat_trach_nhiem_vat_chat",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.122",
        "src_ten": "Nguyên tắc, trình tự, thủ tục xử lý kỷ luật lao động",
        "src_chunk": "45-2019-qh14:d122",
        "tgt_mapc": "20.2.NĐ.3.70",
        "tgt_ten": "Trình tự, thủ tục xử lý kỷ luật lao động",
        "tgt_chunk": "145-2020-nd-cp:d70",
        "category": "ky_luat_trach_nhiem_vat_chat"
    },
    {
        "id": "kg_ref_46",
        "question": "Thời hiệu xử lý kỷ luật lao động tối đa là bao nhiêu tháng đối với hành vi vi phạm liên quan trực tiếp đến tài chính, tài sản của doanh nghiệp?",
        "de_muc": "20.2",
        "category": "ky_luat_trach_nhiem_vat_chat",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.123",
        "src_ten": "Thời hiệu xử lý kỷ luật lao động",
        "src_chunk": "45-2019-qh14:d123",
        "tgt_mapc": "20.2.LQ.122",
        "tgt_ten": "Nguyên tắc, trình tự, thủ tục xử lý kỷ luật lao động",
        "tgt_chunk": "45-2019-qh14:d122",
        "category": "ky_luat_trach_nhiem_vat_chat"
    },
    {
        "id": "kg_ref_47",
        "question": "Những hành vi vi phạm nào người sử dụng lao động được áp dụng hình thức xử lý kỷ luật sa thải người lao động?",
        "de_muc": "20.2",
        "category": "ky_luat_trach_nhiem_vat_chat",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.125",
        "src_ten": "Áp dụng hình thức xử lý kỷ luật sa thải",
        "src_chunk": "45-2019-qh14:d125",
        "tgt_mapc": "20.2.LQ.122",
        "tgt_ten": "Nguyên tắc, trình tự, thủ tục xử lý kỷ luật lao động",
        "tgt_chunk": "45-2019-qh14:d122",
        "category": "ky_luat_trach_nhiem_vat_chat"
    },
    {
        "id": "kg_ref_48",
        "question": "Trường hợp người lao động làm mất dụng cụ, thiết bị của doanh nghiệp thì mức bồi thường thiệt hại được xử lý căn cứ theo quy định nào?",
        "de_muc": "20.2",
        "category": "ky_luat_trach_nhiem_vat_chat",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.129",
        "src_ten": "Bồi thường thiệt hại",
        "src_chunk": "45-2019-qh14:d129",
        "tgt_mapc": "20.2.NĐ.3.71",
        "tgt_ten": "Trách nhiệm vật chất",
        "tgt_chunk": "145-2020-nd-cp:d71",
        "category": "ky_luat_trach_nhiem_vat_chat"
    },
    {
        "id": "kg_ref_49",
        "question": "Hợp đồng lao động đối với lao động là người giúp việc gia đình phải có những nội dung đặc thù gì?",
        "de_muc": "20.2",
        "category": "lao_dong_dac_thu",
        "style": "truc_tiep",
        "src_mapc": "20.2.LQ.162",
        "src_ten": "Hợp đồng lao động đối với lao động là người giúp việc gia đình",
        "src_chunk": "45-2019-qh14:d162",
        "tgt_mapc": "20.2.NĐ.3.89",
        "tgt_ten": "Hợp đồng lao động đối với lao động là người giúp việc gia đình",
        "tgt_chunk": "145-2020-nd-cp:d89",
        "category": "lao_dong_dac_thu"
    },
    {
        "id": "kg_ref_50",
        "question": "Người sử dụng lao động có trách nhiệm chi trả tiền bảo hiểm xã hội, bảo hiểm y tế cho người giúp việc gia đình như thế nào?",
        "de_muc": "20.2",
        "category": "lao_dong_dac_thu",
        "style": "tinh_huong",
        "src_mapc": "20.2.LQ.163",
        "src_ten": "Nghĩa vụ của người sử dụng lao động khi sử dụng lao động là người giúp việc gia đình",
        "src_chunk": "45-2019-qh14:d163",
        "tgt_mapc": "20.2.NĐ.3.90",
        "tgt_ten": "Tiền lương đối với lao động là người giúp việc gia đình",
        "tgt_chunk": "145-2020-nd-cp:d90",
        "category": "lao_dong_dac_thu"
    }
]

def build_kg_item(curated):
    return {
        "id": curated["id"],
        "question": curated["question"],
        "de_muc": curated["de_muc"],
        "category": curated["category"],
        "style": curated["style"],
        "tags": ["kg_cross_ref"],
        "retrieval_type": "graph_expanded",
        "relevance": {
            curated["src_mapc"]: 3,
            curated["tgt_mapc"]: 2
        },
        "chunk_relevance": {
            curated["src_chunk"]: 3,
            curated["tgt_chunk"]: 2
        },
        "kg_relevance": {
            "seed_mapcs": {curated["src_mapc"]: 3},
            "graph_edges": [
                {
                    "source": curated["src_mapc"],
                    "source_grade": 3,
                    "type": "REFERS_TO",
                    "target": curated["tgt_mapc"],
                    "target_grade": 2,
                    "predicate": "https://example.org/vn-legal/relation#cites"
                }
            ],
            "expanded_mapcs": {
                curated["tgt_mapc"]: 2
            }
        },
        "target_khoan": None,
        "origin": "kg_cross_ref_v3",
        "notes": f"Câu hỏi kiểm thử khả năng mở rộng tri thức qua liên kết REFERS_TO từ {curated['src_ten']} ({curated['src_mapc']}) sang {curated['tgt_ten']} ({curated['tgt_mapc']})."
    }

# Load current benchmark_questions_v3.jsonl
v3_path = "labor_rag/evaluation/results/benchmark_questions_v3.jsonl"
mirror_path = "labor_rag/evaluation/benchmark_questions_v3.jsonl"

existing = []
with open(v3_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            existing.append(json.loads(line))

print(f"Existing questions before expansion: {len(existing)}")

# Check if any kg_ref already added
existing_ids = {q["id"] for q in existing}
new_items = []
for c in CURATED_50_KG:
    if c["id"] not in existing_ids:
        new_items.append(build_kg_item(c))

print(f"Adding {len(new_items)} new KG cross-reference questions.")

all_questions = existing + new_items
print(f"Total questions after expansion: {len(all_questions)}")

# Write to both paths
for p in [v3_path, mirror_path]:
    with open(p, "w", encoding="utf-8") as f:
        for q in all_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

print(f"Successfully updated benchmark_questions_v3.jsonl with {len(all_questions)} questions!")

# Hướng dẫn gán nhãn bộ test v2 (chủ đề Lao động)

File cần duyệt: `review.xlsx`, tạo bằng lệnh `build_testset export`.
Chỉ sửa các **cột tô vàng**. Các cột khác do script sinh ra và sẽ bị ghi đè ở lần export sau.

> Đóng Excel trước khi chạy `export` hoặc `finalize`.
> Chạy lại `export` (ví dụ sau khi có thêm câu hỏi) **không làm mất** những gì bạn đã nhập:
> script giữ lại `question`, `category`, `action`, `notes` và `grade`.

---

## Bước 1: Sheet `questions`, duyệt từng câu hỏi

| Cột | Ý nghĩa |
|---|---|
| `style` | Kiểu câu hỏi: `truc_tiep`, `tinh_huong`, `doi_thuong`, `tu_khoa`, `nhieu_dieu` |
| `tags` | `deep_khoan`: câu hỏi nhắm vào **một Khoản ở phần sau** của Điều dài. `multi_dieu`: cần **2 Điều** mới trả lời đủ |
| `seed_mapcs`, `seed_titles`, `target_khoan` | Điều (và Khoản) dùng để sinh câu hỏi |
| `answer_hint` | Câu trả lời tóm tắt do LLM viết, chỉ để tham khảo |
| `question_draft` | Bản nháp gốc của LLM (không sửa) |
| **`question`** | Câu hỏi cuối cùng. **Sửa trực tiếp ở đây** |
| **`category`** | Chủ đề (chọn trong danh sách) |
| **`action`** | `keep` (giữ) hoặc `drop` (bỏ). Bắt buộc phải điền |
| **`notes`** | Ghi chú tùy ý |

**Bỏ (`drop`)** khi câu hỏi:
- sai nội dung luật, hoặc đoạn luật nguồn không trả lời được;
- vô nghĩa, quá chung chung ("quy định về lao động là gì?");
- trùng ý với câu khác đã giữ;
- là câu `tu_khoa` nhưng thực chất trả lời được bằng quá nhiều Điều (hơn 8 Điều cùng đúng ở mức 3).

**Sửa (`question`)** khi câu hỏi:
- dùng quá nhiều thuật ngữ trong khi `style` là `doi_thuong` hoặc `tinh_huong`. Hãy viết lại như người lao động bình thường sẽ nói;
- chép gần nguyên tiêu đề Điều, hoặc lộ đáp án;
- dài dòng. Câu tình huống nên gọn trong 1–3 câu.

Nên **giữ đúng kiểu câu** (`style`) khi sửa. Bộ test cần đa dạng cách hỏi chứ không chỉ đa dạng nội dung.

Nếu bạn **viết lại câu hỏi nhiều**, hãy chạy lại `pool`, `judge`, `export`, vì danh sách ứng viên được tạo từ câu hỏi cũ.
Script tự đọc câu hỏi đã sửa từ `review.xlsx`, và chỉ chấm lại những câu có thay đổi.

---

## Bước 2: Sheet `judgments`, chấm mức liên quan

Mỗi dòng là một cặp (câu hỏi, Điều ứng viên). Ứng viên được gom từ BM25 và 3 mô hình embedding
(`pooled_by`, ví dụ `bkai#1, bm25#3` nghĩa là bkai xếp hạng 1, BM25 xếp hạng 3) cùng Điều nguồn (`is_seed = x`).
Cách gom từ nhiều hệ thống giúp bộ test **không thiên vị** một mô hình nào.

Điền cột **`grade`** theo thang sau:

| Điểm | Khi nào |
|---|---|
| **3** | Điều này **trả lời trực tiếp**, đầy đủ câu hỏi, hoặc phần chính của câu hỏi |
| **2** | Chứa **một phần quan trọng** của câu trả lời, nhưng phải kết hợp với Điều khác |
| **1** | **Có liên quan** hoặc cho ngữ cảnh (định nghĩa, nguyên tắc chung), nhưng không trả lời câu hỏi |
| **0** | Không liên quan |

Ví dụ với câu hỏi *"Công ty có được đuổi việc tôi khi tôi đang nghỉ thai sản không?"*:
- Điều về *trường hợp người sử dụng lao động không được đơn phương chấm dứt hợp đồng* → **3**
- Điều về *bảo vệ thai sản đối với lao động nữ* → **2**
- Điều về *quyền đơn phương chấm dứt hợp đồng của người sử dụng lao động* → **1**
- Điều về *thời giờ làm việc* → **0**

Lưu ý khi chấm:
- `suggested_grade` / `suggested_reason` là gợi ý của LLM. **Hãy tự đọc `snippet`** (hoặc `full_text`) rồi mới chấm.
  Đừng chép lại gợi ý. Nếu chỉ sao chép, bộ test sẽ chỉ đo được độ đồng ý với LLM.
- `snippet` của Điều dài gồm phần mở đầu và các Khoản gần câu hỏi nhất. Nếu chưa chắc, mở `full_text`.
- Chấm theo nội dung luật, **không** theo việc Điều đó đến từ Luật, Nghị định hay Thông tư.
  Nghị định hoặc Thông tư hướng dẫn chi tiết thường đạt **3** nếu trả lời đúng điều được hỏi.
- Điều nguồn (`is_seed`) thường đạt 3. Nếu bạn chấm nó 0, nghĩa là câu hỏi đã lệch khỏi Điều nguồn. Hãy sửa câu hỏi hoặc `drop`.
- Mỗi câu `keep` cần **ít nhất một Điều đạt 2 hoặc 3**.
- Có thể dùng bộ lọc (filter) của Excel theo `qid` để chấm từng câu một.

---

## Bước 3: Tạo bộ test

```powershell
python -m labor_rag.evaluation.build_testset finalize
python -m labor_rag.evaluation.build_testset stats
```

`finalize` báo lỗi và **không ghi file** nếu còn câu chưa điền `action`, còn ứng viên chưa có `grade`,
hoặc có câu không có Điều nào đạt 2–3. Hai tùy chọn sau chỉ dùng khi chạy thử:
- `--allow-unreviewed`: bỏ qua các câu chưa duyệt.
- `--use-suggested`: lấy gợi ý của LLM cho các ô trống. Số ô lấy gợi ý được ghi lại ở trường `grades_from_suggestion`.
  **Không nên dùng cho bộ test chính thức.**

Kết quả là file `labor_rag/evaluation/benchmark_questions_v2.jsonl`.
File v1 (`benchmark_questions.jsonl`) được giữ nguyên để so sánh với kết quả cũ.

## Ước lượng thời gian

Khoảng 150 câu, mỗi câu khoảng 12 ứng viên, tức khoảng 1.800 lượt chấm. Mỗi lượt mất 10–20 giây, tổng cộng khoảng **6–8 giờ**.
Nên chia cho 2–3 người theo đề mục. Nếu đủ thời gian, hãy cho 2 người chấm chung khoảng 20 câu
để đo độ đồng thuận và đưa vào báo cáo.

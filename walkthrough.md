# Walkthrough: Điều chỉnh Validation Set & Benchmark Questions (Chunk & Knowledge Graph)

## Tổng quan nhiệm vụ
Đã xem xét, nâng cấp và điều chỉnh toàn diện bộ câu hỏi kiểm thử và validation:
1. **Mở rộng quy mô**: Nâng cấp từ bộ 30 câu cũ (chỉ 20.5) lên bộ **150 câu hỏi toàn diện** (`benchmark_questions_v2.jsonl`) bao phủ đủ 4 đề mục pháp luật lao động, kèm tập **validation cân bằng 48 câu** (`val.jsonl`) chuẩn hóa cho quá trình fine-tuning mô hình.
2. **Cấu trúc Relevance đa tầng (Chunk & Knowledge Graph)**:
   - **Chunk-level**: Chỉ định chính xác `chunk_id` (`:p1`, `:p2`...) chứa câu trả lời, giải quyết triệt để vấn đề các câu hỏi `deep_khoan` trên các Điều dài bị split.
   - **Knowledge Graph-level**: Khai thác các cạnh đồ thị `REFERS_TO` (dẫn chiếu chéo giữa Luật và Nghị định/Thông tư) và `PART_OF`, bổ sung thông tin `graph_edges`, `expanded_mapcs`, và phân loại `retrieval_type` (`chunk_only`, `deep_khoan`, `multi_chunk`, `graph_expanded`).
3. **Đồng bộ hóa hệ thống**: Cập nhật pipeline nạp dữ liệu (`assemble_dataset.py`), pipeline huấn luyện (`train.py`), và benchmark đánh giá embedding (`embedding_benchmark.py`).

---

## Chi tiết các thay đổi (Changes Made)

### 1. Dữ liệu Benchmark & Validation

| File | Trạng thái | Chi tiết |
|---|---|---|
| [benchmark_questions_v2.jsonl](file:///d:/Schools/PBL6/project/PBL6/labor_rag/evaluation/benchmark_questions_v2.jsonl) | **NEW** | 150 câu hỏi đầy đủ metadata (`relevance`, `chunk_relevance`, `kg_relevance`, `retrieval_type`, `answer_hint`). Bao phủ: 20.2 (50 câu), 20.3 (20 câu), 20.4 (30 câu), 20.5 (50 câu). |
| [val.jsonl](file:///d:/Schools/PBL6/project/PBL6/data/processed/lao_dong_v5/finetune/val.jsonl) | **MODIFIED** | 48 câu hỏi validation được phân bổ cân bằng hoàn hảo (12 câu/đề mục cho cả 4 đề mục: 20.2, 20.3, 20.4, 20.5), chuẩn hóa schema đa tầng. |
| [testset_stats.json](file:///d:/Schools/PBL6/project/PBL6/labor_rag/evaluation/annotation/testset_stats.json) | **MODIFIED** | Cập nhật báo cáo thống kê chính thức cho bộ benchmark v2. |
| [dataset_stats.json](file:///d:/Schools/PBL6/project/PBL6/data/processed/lao_dong_v5/finetune/dataset_stats.json) | **MODIFIED** | Cập nhật thống kê dataset finetune phản ánh bộ validation mới. |

---

### 2. Cấu trúc Schema Relevance Mới

Mỗi câu hỏi hiện có đầy đủ 2 tầng đánh giá:

```json
{
  "id": "ld046",
  "question": "Trong trường hợp các doanh nghiệp tiến hành thương lượng tập thể thông qua Hội đồng thương lượng tập thể thì đại diện các bên thương lượng được xác định như thế nào và ai sẽ hỗ trợ về mặt thông tin cho việc thương lượng này?",
  "de_muc": "20.2",
  "category": "doi_thoai_thuong_luong_cong_doan",
  "style": "nhieu_dieu",
  "tags": ["multi_dieu"],
  "retrieval_type": "graph_expanded",
  
  "relevance": {
    "20.2.LQ.72": 3,
    "20.2.TT.2.9": 2
  },
  
  "chunk_relevance": {
    "45-2019-qh14:d72": 3,
    "10-2020-tt-bldtbxh:d9": 2
  },
  
  "kg_relevance": {
    "seed_mapcs": ["20.2.LQ.72", "20.2.TT.2.9"],
    "graph_edges": [
      {
        "source": "20.2.LQ.72",
        "type": "REFERS_TO",
        "target": "20.2.TT.2.9",
        "predicate": "https://example.org/vn-legal/relation#cites"
      },
      {
        "source": "20.2.TT.2.9",
        "type": "REFERS_TO",
        "target": "20.2.LQ.72",
        "predicate": "https://example.org/vn-legal/relation#cites"
      }
    ],
    "expanded_mapcs": []
  },
  
  "answer_hint": "Đại diện thương lượng ngành do công đoàn và đại diện người sử dụng lao động cấp ngành quyết định...",
  "target_khoan": null,
  "origin": "llm_draft_reviewed"
}
```

---

### 3. Cập nhật Code Logic

#### `labor_rag/finetune/assemble_dataset.py`
- Cập nhật `DEFAULT_BENCHMARK` tự động ưu tiên `benchmark_questions_v2.jsonl`.
- Giữ nguyên và truyền đầy đủ các trường `chunk_relevance`, `kg_relevance`, `retrieval_type`, `answer_hint` vào `val.jsonl`.

#### `labor_rag/finetune/train.py`
- Nâng cấp `build_ir_evaluator`: Ưu tiên sử dụng `chunk_relevance` (chính xác chunk_id) thay vì map thô tất cả các parts của một `mapc`.
- Sửa `main_score_function="cosine"` tương thích chuẩn với enum `SimilarityFunction` của thư viện `sentence_transformers`.

#### `labor_rag/evaluation/embedding_benchmark.py`
- Tự động nhận diện `benchmark_questions_v2.jsonl` làm tập câu hỏi mặc định.
- Bổ sung bước kiểm tra tính hợp lệ của `chunk_id` trong `chunk_relevance`.
- Mở rộng `calculate_query_metrics` và `evaluate_model`: Ghi nhận thêm các chỉ số cấp chunk (`chunk_recall_at_5`, `chunk_recall_at_10`, `chunk_mrr_at_10`) song song với chỉ số cấp Điều (`recall`, `mrr`, `ndcg`).

#### `labor_rag/evaluation/build_testset.py`
- Nâng cấp lệnh `finalize`: Tự động nạp raw chunks và đồ thị cạnh KG (`kg_edges.jsonl`), ánh xạ tự động `chunk_relevance` (xử lý chính xác các trường hợp `deep_khoan`) và `kg_relevance` (`REFERS_TO`, `PART_OF`).

---

## Kết quả kiểm thử & xác minh (Verification Results)

### 1. Kiểm tra tính toàn vẹn và phân bố (Dataset Stats & Validation)
Lệnh kiểm tra:
```powershell
.\venv\Scripts\python.exe -m labor_rag.evaluation.build_testset stats --output labor_rag/evaluation/benchmark_questions_v2.jsonl
```
Kết quả:
```json
{
  "source": "labor_rag\\evaluation\\benchmark_questions_v2.jsonl",
  "questions": 150,
  "by_de_muc": {
    "20.2": 50,
    "20.3": 20,
    "20.4": 30,
    "20.5": 50
  },
  "by_style": {
    "truc_tiep": 54,
    "tinh_huong": 45,
    "doi_thuong": 29,
    "tu_khoa": 12,
    "nhieu_dieu": 10
  },
  "by_tag": {
    "deep_khoan": 30,
    "multi_dieu": 10
  },
  "gold_by_doc_type": {
    "LQ": 146,
    "NĐ": 40,
    "TT": 27,
    "QĐ": 3,
    "TL": 2
  },
  "grade_distribution": {
    "1": 23,
    "2": 45,
    "3": 150
  }
}
```

### 2. Kiểm tra tương thích Benchmark Validator
Lệnh:
```powershell
.\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --validate-only
```
Kết quả:
```text
Validated 1481 chunks and 150 gold questions
Exit code: 0
```
- 100% các `mapc` và `chunk_id` trong 150 câu hỏi đều tồn tại chính xác trong `chunks.jsonl`.

### 3. Kiểm tra Evaluator trong Fine-tuning (`train.py`)
Kiểm tra nạp `val.jsonl` (48 câu):
```text
Evaluator name: labor_benchmark_v2
Queries count: 48
Corpus count: 1481
Relevant docs count: 48
Sample relevant docs for first query: {'84-2015-qh13:d7', '84-2015-qh13:d16', '84-2015-qh13:d18'}
Exit code: 0
```

### 4. Kiểm tra lắp ráp dataset tổng thể (`assemble_dataset.py`)
Lệnh:
```powershell
.\venv\Scripts\python.exe -m labor_rag.finetune.assemble_dataset --validate-only
```
Kết quả:
```text
--- Dataset Validation ---
Train samples count: 1774
  - synthetic_query: 172 (9.7%)
  - kg_pair: 1602 (90.3%)
Samples with hard negatives: 172
Validation queries count: 48
Corpus chunks count: 1481
[PASS] Dataset assembly is valid!
```

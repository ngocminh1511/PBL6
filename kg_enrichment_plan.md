# Kế hoạch: Enrich `kg_relevance` từ Knowledge Graph

## Mục tiêu

`benchmark_questions_v2.jsonl` hiện có **150 câu hỏi** nhưng:
- **133/150** câu có `kg_relevance.graph_edges = []` (rỗng)
- Chỉ **17/150** câu (`graph_expanded / multi_dieu`) được điền đầy đủ quan hệ đồ thị

Mục tiêu: Khai thác quan hệ **`REFERS_TO`** từ `kg_edges.jsonl` (nguồn từ `vlr:cites` trong ABox TTL) để tự động làm giàu `graph_edges`, `expanded_mapcs`, `chunk_relevance` và `retrieval_type` cho tất cả câu phù hợp.

---

## Phát hiện từ nghiên cứu

### Cấu trúc Knowledge Graph (ABox TTL)

Các file ABox encode quan hệ giữa các Điều như sau:

```turtle
inst:Article_20_5_LQ_14 a vld:Article ;
    vlr:cites inst:Article_20_5_LQ_56,        # dẫn chiếu trực tiếp
              inst:Article_20_5_NĐ_1_32,
              inst:Article_20_5_TT_74_2 .
```

| Predicate | Ý nghĩa | Số lượng trong `kg_edges.jsonl` |
|---|---|---|
| **`REFERS_TO`** | Điều A dẫn chiếu/cites Điều B | **2,498** (1,229 có source là mapc) |
| `PART_OF` | Điều → Chương/Đề mục | 2,994 |
| `HAS_CROSS_REFERENCE` | Dẫn chiếu chưa resolve IRI | 1,249 |

### Kết quả phân tích

```
Tổng câu hỏi:                        150
Đã có graph_edges (non-empty):         17   ← bảo toàn
Chưa có graph_edges:                  133

Trong 133 câu chưa có edges:
  Enrichable từ REFERS_TO (fwd+rev):   68   ← sẽ tự động enrich
  Không có REFERS_TO nào:              65   ← giữ nguyên (đúng)
```

**65 câu không enrichable là ĐÚNG** — chúng là các điều "standalone" không dẫn chiếu sang điều nào khác trong cùng đề mục.

### Vấn đề logic hiện tại trong `build_testset.py`

`cmd_finalize` (dòng 1094-1113) chỉ thêm edge khi `tgt in relevance`:
```python
if tgt in relevance and tgt not in seed_mapcs:  # quá hẹp!
    connected_edges.append(...)
```
→ Câu `chunk_only` với 1 seed dù có REFERS_TO đến điều liên quan vẫn bị bỏ qua.

---

## User Review Required

> [!IMPORTANT]
> **Chiến lược enrich `graph_edges` cho câu `chunk_only` và `deep_khoan`:**
> Khi Điều seed (ví dụ `20.5.LQ.14`) có `REFERS_TO` → `20.5.LQ.56` và `20.5.NĐ.1.32`:
> - Thêm các edge này vào `graph_edges`
> - Thêm `20.5.LQ.56` vào `expanded_mapcs`
> - Thêm chunks của `expanded_mapcs` vào `chunk_relevance` với **grade = 1** (peripheral)
> - `retrieval_type`: `chunk_only` → `graph_expanded`; `deep_khoan` → **giữ nguyên**

> [!WARNING]
> **17 câu đã có graph_edges thủ công sẽ được bảo toàn nguyên vẹn** — script chỉ enrich câu chưa có edges.

> [!NOTE]
> **Về reverse edges:** Nếu `20.5.LQ.70 REFERS_TO 20.5.LQ.16`, và câu hỏi về `20.5.LQ.16`, sẽ thêm edge chiều ngược `20.5.LQ.70 → 20.5.LQ.16`. Điều này có giá trị vì hệ thống KG retrieve sẽ thấy điều nào dẫn chiếu đến điều cần tìm.

---

## Open Questions

> [!IMPORTANT]
> **Giới hạn số edges mỗi câu?** Đề xuất: tối đa **5 forward + 5 reverse** edges mỗi seed (tổng ≤ 10). Bạn có muốn giữ tất cả hay giới hạn?

---

## Proposed Changes

### Component 1: Script enrich độc lập

#### [NEW] `labor_rag/evaluation/enrich_kg_relevance.py`

```python
"""
Enrich benchmark_questions_v2.jsonl với graph_edges từ REFERS_TO.

Usage:
    python -m labor_rag.evaluation.enrich_kg_relevance          # ghi file
    python -m labor_rag.evaluation.enrich_kg_relevance --dry-run # preview
    python -m labor_rag.evaluation.enrich_kg_relevance --max-edges 5
"""

CITES_IRI = "https://example.org/vn-legal/relation#cites"

def build_refers_to_graph(edges_path):
    fwd, rev = defaultdict(set), defaultdict(set)
    for e in read_jsonl(edges_path):
        if e.get("type") != "REFERS_TO":
            continue
        src, tgt = e["source"], iri_to_mapc(e["target"])
        if src.startswith("20.") and tgt and tgt.startswith("20."):
            fwd[src].add(tgt)
            rev[tgt].add(src)
    return fwd, rev

def enrich_question(q, fwd, rev, mapc_to_chunks, max_edges=5):
    if q.get("kg_relevance", {}).get("graph_edges"):
        return q  # bảo toàn edges thủ công

    seeds = q.get("kg_relevance", {}).get("seed_mapcs", [])
    found_edges, expanded = [], []

    for seed in seeds:
        for tgt in sorted(fwd.get(seed, set()))[:max_edges]:
            if tgt not in seeds:
                found_edges.append({"source": seed, "type": "REFERS_TO",
                                    "target": tgt, "predicate": CITES_IRI})
                expanded.append(tgt)
        for src in sorted(rev.get(seed, set()))[:max_edges]:
            if src not in seeds:
                found_edges.append({"source": src, "type": "REFERS_TO",
                                    "target": seed, "predicate": CITES_IRI})

    if not found_edges:
        return q  # không enrichable

    chunk_rel = dict(q.get("chunk_relevance", {}))
    for em in set(expanded):
        for cid in mapc_to_chunks.get(em, []):
            if cid not in chunk_rel:
                chunk_rel[cid] = 1

    rt = q.get("retrieval_type", "chunk_only")
    if rt in ("chunk_only", "multi_chunk"):
        rt = "graph_expanded"

    q["kg_relevance"]["graph_edges"] = found_edges
    q["kg_relevance"]["expanded_mapcs"] = list(set(expanded))
    q["chunk_relevance"] = dict(sorted(chunk_rel.items(), key=lambda kv: -kv[1]))
    q["retrieval_type"] = rt
    return q
```

---

### Component 2: Cập nhật `build_testset.py`

#### [MODIFY] `labor_rag/evaluation/build_testset.py`

Mở rộng logic KG edges trong `cmd_finalize` (dòng 1090-1113):

```diff
  for sm in seed_mapcs:
      for edge in edge_map.get(sm, []):
-         tgt = edge.get("target")
-         if tgt in relevance and tgt not in seed_mapcs:
-             connected_edges.append({...})
-         elif "multi_dieu" in tags and tgt in seed_mapcs and tgt != sm:
-             connected_edges.append({...})
+         if edge.get("type") != "REFERS_TO":
+             continue
+         tgt = edge.get("target")
+         if not (tgt and tgt.startswith("20.") and tgt != sm):
+             continue
+         connected_edges.append({
+             "source": sm, "type": "REFERS_TO",
+             "target": tgt, "predicate": edge.get("predicate_iri", ""),
+         })
+         if tgt not in expanded_mapcs and tgt not in seed_mapcs:
+             expanded_mapcs.append(tgt)
+             for c in mapc_to_raw.get(tgt, []):
+                 if c["chunk_id"] not in chunk_rel:
+                     chunk_rel[c["chunk_id"]] = relevance.get(tgt, 1)
```

---

### Component 3: Cập nhật `embedding_benchmark.py`

#### [MODIFY] `labor_rag/evaluation/embedding_benchmark.py`

Thêm metric `graph_recall_at_k` vào `calculate_query_metrics`:

```python
expanded = set(q.get("kg_relevance", {}).get("expanded_mapcs", []))
expanded_chunk_ids = set()
for mapc_code in expanded:
    expanded_chunk_ids.update(mapc_to_chunks.get(mapc_code, []))

if expanded_chunk_ids:
    graph_recall_5  = int(bool(expanded_chunk_ids & set(top5_cids)))
    graph_recall_10 = int(bool(expanded_chunk_ids & set(top10_cids)))
```

---

## Verification Plan

### Automated Tests

```powershell
# 1. Preview (không ghi file)
.\venv\Scripts\python.exe -m labor_rag.evaluation.enrich_kg_relevance --dry-run

# 2. Chạy enrich
.\venv\Scripts\python.exe -m labor_rag.evaluation.enrich_kg_relevance

# 3. Validate sau enrich
.\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --validate-only

# 4. Stats mới
.\venv\Scripts\python.exe -m labor_rag.evaluation.build_testset stats --output labor_rag/evaluation/benchmark_questions_v2.jsonl
```

### Expected Results

| Metric | Before | After |
|---|---|---|
| Questions with `graph_edges` | 17 | ~85 |
| `retrieval_type: graph_expanded` | 17 | ~85 |
| `retrieval_type: chunk_only` | 100 | ~32 |
| `retrieval_type: deep_khoan` | 30 | 30 (giữ nguyên) |
| Validation (1481 chunks, 150 q) | PASS | PASS |

### Manual Verification

1. Chọn 5 câu enriched ngẫu nhiên → xác nhận edges có ý nghĩa
2. Xác nhận 17 câu đã có edges **không bị thay đổi**
3. Xác nhận 65 câu không enrichable giữ nguyên `graph_edges = []`

---

## Implementation Order

1. Tạo `enrich_kg_relevance.py` (script độc lập, backup file cũ)
2. Chạy enrich → `benchmark_questions_v2.jsonl` mới
3. Cập nhật `build_testset.py` cmd_finalize
4. Cập nhật `embedding_benchmark.py` graph_recall metrics
5. Validate toàn bộ

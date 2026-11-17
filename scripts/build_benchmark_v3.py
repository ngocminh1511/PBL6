"""Create benchmark_questions_v3.jsonl by:
1. Loading all 150 questions from benchmark_questions_v2.jsonl.
2. Completely removing the `answer_hint` field (avoiding data leakage).
3. Standardizing and enriching `kg_relevance` with exact scores (1, 2, 3) and fine-grained reference parameters:
   - `expanded_mapcs`: converted from list to dict {mapc: grade}
   - `graph_edges`: includes `target_grade`, `source_grade`, and where available `source_khoan`, `target_khoan`, `reference_text`
4. Adding the fine-grained clause-level cross-reference question from NĐ 145 Điều 2 Khoản 2 -> BLLĐ Điều 2 Khoản 2.
5. Saving to labor_rag/evaluation/results/benchmark_questions_v3.jsonl and labor_rag/evaluation/benchmark_questions_v3.jsonl.
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
V2_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "benchmark_questions_v2.jsonl"
OUT_RESULTS_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "results" / "benchmark_questions_v3.jsonl"
OUT_EVAL_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "benchmark_questions_v3.jsonl"
CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "lao_dong_v5" / "chunks.jsonl"

def load_chunks_map():
    chunks = {}
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                mapc = c.get("mapc")
                if mapc:
                    chunks.setdefault(str(mapc), []).append(c)
    return chunks

def extract_reference_params(source_text, target_dieu_num=None):
    """Extract clause-level reference text like 'khoản 2 Điều 2 của Bộ luật Lao động'."""
    pattern = re.compile(
        r"(?:theo|tại|quy định tại)\s+(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)(?:\s+của\s+([^\n,.;]+))?",
        re.IGNORECASE
    )
    for m in pattern.finditer(source_text):
        khoan = int(m.group(1)) if m.group(1) else None
        dieu = int(m.group(2)) if m.group(2) else None
        ref_text = m.group(0).strip()
        if target_dieu_num is None or dieu == target_dieu_num:
            return khoan, dieu, ref_text
    return None, None, ""

def main():
    print(f"Loading questions from {V2_PATH}...")
    with open(V2_PATH, "r", encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]

    chunks_map = load_chunks_map()
    v3_questions = []

    for q in questions:
        # 1. Remove answer_hint
        q.pop("answer_hint", None)

        relevance = q.get("relevance", {})
        chunk_rel = q.get("chunk_relevance", {})
        kg_rel = q.get("kg_relevance", {})
        tags = q.get("tags", [])
        style = q.get("style", "")

        # 2. Convert expanded_mapcs to dict with grades {mapc: grade}
        raw_expanded = kg_rel.get("expanded_mapcs", [])
        expanded_dict = {}
        if isinstance(raw_expanded, list):
            for m in raw_expanded:
                expanded_dict[m] = relevance.get(m, 2)
        elif isinstance(raw_expanded, dict):
            expanded_dict = raw_expanded

        # 3. Enrich graph_edges with target_grade & clause parameters
        edges = kg_rel.get("graph_edges", [])
        enriched_edges = []
        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            tgt_grade = relevance.get(tgt, 2)
            src_grade = relevance.get(src, 2)

            # Try to get reference text & target_khoan from chunk text
            src_chunks = chunks_map.get(src, [])
            combined_src_text = "\n".join(c.get("text", "") for c in src_chunks)
            
            # Determine target dieu number
            tgt_dieu_num = None
            if tgt:
                parts = tgt.split(".")
                if parts[-1].isdigit():
                    tgt_dieu_num = int(parts[-1])

            t_khoan, _, ref_text = extract_reference_params(combined_src_text, tgt_dieu_num)

            new_edge = {
                "source": src,
                "source_grade": src_grade,
                "type": edge.get("type", "REFERS_TO"),
                "target": tgt,
                "target_grade": tgt_grade,
                "predicate": edge.get("predicate", "https://example.org/vn-legal/relation#cites")
            }
            if t_khoan:
                new_edge["target_khoan"] = t_khoan
            if ref_text:
                new_edge["reference_text"] = ref_text
            enriched_edges.append(new_edge)

        # Update seed_mapcs to dict or list
        seed_list = kg_rel.get("seed_mapcs", [])
        seed_dict = {s: relevance.get(s, 3) for s in seed_list}

        q["kg_relevance"] = {
            "seed_mapcs": seed_dict,
            "graph_edges": enriched_edges,
            "expanded_mapcs": expanded_dict,
        }
        v3_questions.append(q)

    # 4. Add the specific clause-level cross-reference question from the user's image:
    # NĐ 145 Điều 2 Khoản 2 -> BLLĐ Điều 2 Khoản 2
    nd145_q = {
        "id": "ld_ref_145",
        "question": "Theo Nghị định 145/2020/NĐ-CP, người sử dụng lao động thuộc đối tượng áp dụng của nghị định này gồm những ai?",
        "de_muc": "20.2",
        "category": "lao_dong_dac_thu",
        "style": "nhieu_dieu",
        "tags": ["multi_dieu", "cross_reference_khoan"],
        "retrieval_type": "graph_expanded",
        "relevance": {
            "20.2.NĐ.3.2": 2,
            "20.2.LQ.2": 3
        },
        "chunk_relevance": {
            "145-2020-nd-cp:d2": 2,
            "45-2019-qh14:d2": 3
        },
        "kg_relevance": {
            "seed_mapcs": {"20.2.NĐ.3.2": 2},
            "graph_edges": [
                {
                    "source": "20.2.NĐ.3.2",
                    "source_khoan": 2,
                    "source_grade": 2,
                    "type": "REFERS_TO",
                    "target": "20.2.LQ.2",
                    "target_khoan": 2,
                    "target_grade": 3,
                    "reference_text": "khoản 2 Điều 2 của Bộ luật Lao động",
                    "predicate": "https://example.org/vn-legal/relation#cites"
                }
            ],
            "expanded_mapcs": {"20.2.LQ.2": 3}
        },
        "target_khoan": 2,
        "origin": "cross_reference_benchmark",
        "notes": "Dẫn chiếu cụ thể cấp Khoản: Điều 2 Khoản 2 NĐ 145/2020 viện dẫn Khoản 2 Điều 2 Bộ luật Lao động 2019."
    }
    v3_questions.append(nd145_q)

    # Save outputs
    OUT_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_RESULTS_PATH, "w", encoding="utf-8") as f:
        for q in v3_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    OUT_EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_EVAL_PATH, "w", encoding="utf-8") as f:
        for q in v3_questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    print(f"Successfully generated benchmark_questions_v3.jsonl with {len(v3_questions)} questions!")
    print(f"  Saved to: {OUT_RESULTS_PATH}")
    print(f"  Saved to: {OUT_EVAL_PATH}")

if __name__ == "__main__":
    main()

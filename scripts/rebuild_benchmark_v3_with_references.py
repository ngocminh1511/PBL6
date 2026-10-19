import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
CHUNKS_PATH = REPO_ROOT / "data" / "processed" / "lao_dong_v5" / "chunks.jsonl"
EDGES_PATH = REPO_ROOT / "data" / "processed" / "lao_dong_v5" / "kg_edges.jsonl"
QUESTIONS_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "results" / "benchmark_questions_v3.jsonl"
MIRROR_PATH = REPO_ROOT / "labor_rag" / "evaluation" / "benchmark_questions_v3.jsonl"

# 1. Load chunks mapping
mapc_to_chunk = {}
with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        m = c.get("mapc")
        if m and m not in mapc_to_chunk:
            mapc_to_chunk[m] = c.get("chunk_id")

print(f"Loaded {len(mapc_to_chunk)} valid MAPC -> Chunk mappings.")

# 2. Load REFERS_TO edges
refers_to = {}
with open(EDGES_PATH, "r", encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        if e.get("type") == "REFERS_TO":
            src = e.get("source")
            tgt = e.get("target")
            if src in mapc_to_chunk and tgt in mapc_to_chunk and src != tgt:
                if src not in refers_to:
                    refers_to[src] = []
                if tgt not in refers_to[src]:
                    refers_to[src].append(tgt)

print(f"Loaded REFERS_TO for {len(refers_to)} unique source MAPCs.")

# 3. Load questions
with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
    questions = [json.loads(line) for line in f]

print(f"Loaded {len(questions)} questions.")

enriched_count = 0
total_ref_added = 0

for q in questions:
    rel = dict(q.get("relevance", {}))
    chunk_rel = dict(q.get("chunk_relevance", {}))
    kg_rel = q.get("kg_relevance", {})
    
    # Identify seeds (grade >= 2)
    seeds = {m: g for m, g in rel.items() if g >= 2}
    if not seeds:
        seeds = dict(rel)
    
    seed_mapcs_dict = {m: g for m, g in seeds.items()}
    graph_edges = []
    expanded_mapcs = {}
    
    # Process edges
    seen_targets = set()
    for src, src_grade in seeds.items():
        targets = refers_to.get(src, [])[:4] # limit max 4 references per seed
        for tgt in targets:
            tgt_chunk = mapc_to_chunk.get(tgt)
            if not tgt_chunk:
                continue
                
            # If target already in relevance with grade >= 2
            if tgt in rel:
                tgt_grade = rel[tgt]
            else:
                tgt_grade = 1
                rel[tgt] = 1
                chunk_rel[tgt_chunk] = 1
                expanded_mapcs[tgt] = 1
                total_ref_added += 1
                
            graph_edges.append({
                "source": src,
                "source_grade": src_grade,
                "type": "REFERS_TO",
                "target": tgt,
                "target_grade": tgt_grade,
                "predicate": "https://example.org/vn-legal/relation#cites"
            })
            seen_targets.add(tgt)
            
    if expanded_mapcs:
        enriched_count += 1
        if q.get("retrieval_type") != "graph_expanded":
            q["retrieval_type"] = "graph_expanded"
            
    q["relevance"] = rel
    q["chunk_relevance"] = chunk_rel
    q["kg_relevance"] = {
        "seed_mapcs": seed_mapcs_dict,
        "graph_edges": graph_edges,
        "expanded_mapcs": expanded_mapcs
    }

print(f"Enriched {enriched_count} questions with {total_ref_added} grade-1 referenced provisions!")

# Verify ld046
ld046 = next(q for q in questions if q["id"] == "ld046")
print("\n--- Verification on ld046 ---")
print(json.dumps(ld046, ensure_ascii=False, indent=2))

# Write back
for path in [QUESTIONS_PATH, MIRROR_PATH]:
    with open(path, "w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

print(f"\nSuccessfully written {len(questions)} updated questions to {QUESTIONS_PATH}")

# Ontology v4 projection

The Turtle ABox (`ontology/abox/abox_lao_dong.ttl`, chu de 20 "Lao dong",
1,407 Dieu) is the canonical legal representation. The JSONL files under
`data/processed/lao_dong_v4` are a versioned projection for Neo4j and Qdrant;
they do not replace the ABox. Every script below defaults to these paths.

## Build and validate

From the repository root:

```powershell
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.ingest.build_abox --chu-de 20 --output .\ontology\abox\abox_lao_dong.ttl
& .\labor_rag\venv\Scripts\python.exe .\scripts\validate_abox.py --report .\ontology\reports\validation_report.json
& .\labor_rag\venv\Scripts\python.exe .\tests\test_cq_v4.py
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.ingest.ontology_to_jsonl
```

`build_abox` parses the HTML in memory (`parse_demuc_html.parse_demuc_nodes`);
no intermediate JSON is written.

## Load the projection

```powershell
docker compose up -d
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.ingest.load_neo4j --replace-dataset
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.ingest.embed_and_index
```

This loads Neo4j dataset `lao_dong_v4` and Qdrant collection `legal_ld_v4_bkai`.

## Run retrieval

`labor_rag.app.chat` defaults to `QDRANT_COLLECTION=legal_ld_v4_bkai` and
`DATASET_ID=lao_dong_v4`; override them in `.env` if needed.

```powershell
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.app.chat
```

## Benchmark embeddings

The vector-only benchmark uses the 1,407 Lao dong chunks and keeps one Qdrant
collection per model (`legal_ld_v4_bkai`, `legal_ld_v4_bge`, `legal_ld_v4_mpnet`):

```powershell
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --validate-only
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --rebuild `
    --questions .\labor_rag\evaluation\benchmark_questions_v2.jsonl `
    --results-dir .\labor_rag\evaluation\results\lao_dong_v2
```

Without `--questions` it uses the v1 set (30 questions on 20.5). The first full
run downloads BGE-M3 and multilingual MPNet when they are not already cached.

Results are written to the results directory:

```text
summary.csv
per_query_results.jsonl
model_metadata.json
```

When an existing collection already contains the expected MAPCs, the
benchmark reports `index_action=reused` and `index_time_seconds=0` for that
run. Use `--rebuild` whenever the chunk text changed (the reuse check compares
MAPCs only) or for a fresh indexing-time measurement.

Open `notebooks/embedding_benchmark.ipynb` after the CLI run to show
the metric table, Recall/MRR/nDCG charts, latency charts, per-question heatmap,
and a top-5 comparison.

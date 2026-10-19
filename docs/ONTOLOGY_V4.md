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

The vector-only benchmark runs on a frozen benchmark version: a test set
frozen against one projection (`labor_rag/evaluation/benchmarks/lao_dong_v5/`,
see docs/BENCHMARK.md). It keeps one Qdrant collection per model
(`legal_ld_v5_bkai`, `legal_ld_v5_bge`, `legal_ld_v5_mpnet`):

```powershell
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1 --validate-only
& .\labor_rag\venv\Scripts\python.exe -m labor_rag.evaluation.embedding_benchmark --benchmark lao_dong_v5 --testset v1
```

The run stops if `chunks.jsonl` or the frozen questions changed since freezing.

Chunks are embedded in length-sorted batches capped by `--max-batch-tokens`
(default 8192 = batch size x longest chunk), so one long Dieu no longer pads a
whole batch. The default fits a 4 GB GPU (bge-m3 fp32 peaks at ~2.5 GB); on a
large GPU such as an A100 raise it, e.g. `--max-batch-tokens 131072`. The same
flag exists on `embed_and_index`. The first full
run downloads BGE-M3 and multilingual MPNet when they are not already cached.

Each run is written to `results/<dataset_id>/<testset>/<run_id>/`:

```text
summary.csv               one row per model
metrics.csv               every metric with its 95% bootstrap CI
breakdown.csv             metrics per de muc / question style / tag
per_query_results.jsonl
run.json                  config, git commit, frozen data hashes
```

When an existing collection already holds the expected chunk ids with the
same text, the benchmark reports `index_action=reused` and
`index_time_seconds=0`; otherwise it rebuilds that collection. Use
`--rebuild` for a fresh indexing-time measurement.

Open `notebooks/embedding_benchmark.ipynb` after the CLI run to show
the metric table with CIs, HitRate/MRR/nDCG charts, latency charts,
per-question heatmap, and a top-5 comparison.

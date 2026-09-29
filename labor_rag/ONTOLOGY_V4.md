# Ontology v4 projection

The Turtle ABox is the canonical legal representation. The JSONL files under
`data/ontology_v4` are a versioned projection for Neo4j and Qdrant; they do
not replace the ABox.

## Build and validate the pilot

From the repository root:

```powershell
& .\labor_rag\venv\Scripts\python.exe .\ontology\parse_an_toan_ve_sinh_lao_dong_abox.py
& .\labor_rag\venv\Scripts\python.exe .\ontology\validate_abox.py --report .\ontology\validation_report.json
& .\labor_rag\venv\Scripts\python.exe .\ontology\test_cq_an_toan_ve_sinh_lao_dong.py
& .\labor_rag\venv\Scripts\python.exe .\labor_rag\ingest\ontology_to_jsonl.py `
    --abox .\ontology\abox_an_toan_ve_sinh_lao_dong.ttl `
    --out-dir .\labor_rag\data\ontology_v4
```

## Load the projection

```powershell
docker compose -f .\labor_rag\docker-compose.yml up -d
& .\labor_rag\venv\Scripts\python.exe .\labor_rag\ingest\load_neo4j.py `
    --data-dir .\labor_rag\data\ontology_v4 `
    --dataset-id an_toan_ve_sinh_lao_dong_v4
& .\labor_rag\venv\Scripts\python.exe .\labor_rag\ingest\embed_and_index.py `
    --chunks .\labor_rag\data\ontology_v4\chunks.jsonl `
    --collection legal_v4_bkai
```

## Run retrieval against the pilot

Set these environment variables before starting the application:

```powershell
$env:QDRANT_COLLECTION = "legal_v4_bkai"
$env:DATASET_ID = "an_toan_ve_sinh_lao_dong_v4"
$env:EMBEDDING_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
python -m app.chat
```

The legacy defaults remain `labor_dieu` and the old JSONL directory, so the
existing pipeline is not overwritten by the ontology pilot.

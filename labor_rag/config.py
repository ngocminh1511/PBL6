"""Project-wide paths, resolved from this file so nothing depends on where
the repository is cloned or which directory a script is launched from.

Layout:
  data/raw/bophapdien/        raw Bo Phap Dien dump (jsonData.js, linh_vuc/*.html)
  data/interim/               chu_de.json, de_muc.json, testset_cache/
  data/processed/lao_dong_v4/ JSONL projection of the Lao dong ABox (tracked in git)
  ontology/                   schema/, abox/, reports/
"""
from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BOPHAPDIEN_DIR = RAW_DIR / "bophapdien"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
LAO_DONG_V4_DIR = PROCESSED_DIR / "lao_dong_v4"
LAO_DONG_DATASET_ID = "lao_dong_v4"

ONTOLOGY_DIR = ROOT_DIR / "ontology"
SCHEMA_V4_PATH = ONTOLOGY_DIR / "schema" / "vn_legal_ontology_schema_v4.ttl"
SHAPES_V4_PATH = ONTOLOGY_DIR / "schema" / "vn_legal_ontology_shapes_v4.ttl"
ABOX_DIR = ONTOLOGY_DIR / "abox"
LAO_DONG_ABOX_PATH = ABOX_DIR / "abox_lao_dong.ttl"

EVALUATION_DIR = ROOT_DIR / "labor_rag" / "evaluation"
ANNOTATION_DIR = EVALUATION_DIR / "annotation"
TESTSET_CACHE_DIR = INTERIM_DIR / "testset_cache"

"""Project-wide paths, resolved from this file so nothing depends on where
the repository is cloned or which directory a script is launched from.

Layout:
  data/raw/bophapdien/        raw Bo Phap Dien dump (jsonData.js, linh_vuc/*.html)
  data/interim/               chu_de.json, de_muc.json, mapc_index.json, parsed/
  data/legacy/                pre-v4 chunks + KG (Qdrant collection labor_dieu)
  data/processed/ontology_v4/ JSONL projection of the v4 ABox (tracked in git)
  ontology/                   schema/, abox/, reports/
"""
from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
BOPHAPDIEN_DIR = RAW_DIR / "bophapdien"
INTERIM_DIR = DATA_DIR / "interim"
PARSED_DIR = INTERIM_DIR / "parsed"
LEGACY_DIR = DATA_DIR / "legacy"
PROCESSED_DIR = DATA_DIR / "processed"
ONTOLOGY_V4_DIR = PROCESSED_DIR / "ontology_v4"

ONTOLOGY_DIR = ROOT_DIR / "ontology"
SCHEMA_V4_PATH = ONTOLOGY_DIR / "schema" / "vn_legal_ontology_schema_v4.ttl"
SHAPES_V4_PATH = ONTOLOGY_DIR / "schema" / "vn_legal_ontology_shapes_v4.ttl"
ABOX_DIR = ONTOLOGY_DIR / "abox"

EVALUATION_DIR = ROOT_DIR / "labor_rag" / "evaluation"

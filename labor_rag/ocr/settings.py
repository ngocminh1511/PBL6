"""Tunables for the document OCR pipeline. Values that depend on the machine
(device, model, DPI) can be overridden from .env; see .env.example.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# --- PDF page classification (text layer vs scan) ---
# A page with at least this many text-layer characters is read directly.
MIN_TEXT_CHARS = 50
# Below that, a page whose largest image covers more than this share is a scan.
SCAN_IMAGE_COVERAGE = 0.3

# --- VietOCR ---
# "vgg_transformer" (more accurate) or "vgg_seq2seq" (faster).
OCR_MODEL = os.getenv("OCR_MODEL", "vgg_transformer")
# Empty = cuda:0 when torch sees a GPU, otherwise cpu.
OCR_DEVICE = os.getenv("OCR_DEVICE", "")
OCR_DPI = int(os.getenv("OCR_DPI", "300"))
OCR_BEAMSEARCH = os.getenv("OCR_BEAMSEARCH", "0") == "1"

# --- Text cleaning ---
# A line repeated in the header/footer zone of this share of pages is dropped.
HEADER_FOOTER_FREQ_THRESHOLD = 0.5
DUPLICATE_PAGE_SIMILARITY = 0.95

# --- Chunking ---
CHUNK_MAX_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200
# Semantic splitting of over-long records loads a sentence-embedding model;
# off by default so a user upload does not pull a 2 GB model. When off, long
# records are split recursively at Dieu/Khoan/Diem/paragraph boundaries.
SEMANTIC_CHUNKING = os.getenv("OCR_SEMANTIC_CHUNKING", "0") == "1"
SEMANTIC_MODEL = os.getenv("OCR_SEMANTIC_MODEL", "BAAI/bge-m3")
SEMANTIC_SIMILARITY_THRESHOLD = 0.5
SEMANTIC_MIN_CHUNK_CHARS = 100

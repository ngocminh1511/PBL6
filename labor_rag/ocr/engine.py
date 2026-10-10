"""VietOCR engine for scanned pages and photos.

VietOCR recognises one text line at a time; it does not locate lines. The
page is therefore segmented first:

1. grayscale, denoise, adaptive threshold -> ink mask
2. horizontal projection of the mask -> text-line bands; bands only a few
   pixels apart are merged so detached diacritics stay with their line, and
   bands several lines tall (tight spacing) are split at their thinnest rows
3. each band is split at wide horizontal gaps (the two-column agency/motto
   header, signature blocks, table cells) and cropped to its ink
4. pieces wider than the model input are cut at the widest word gap.
   VietOCR resizes every crop to 32 px high and clamps the width at
   image_max_width (512 px), so a full-width line would otherwise be
   squeezed 2-3x horizontally and misread
5. pieces are recognised in one batch per page, on the original
   (non-binarised) crop with a white margin, and reassembled
   top-to-bottom, left-to-right

The model config and weights are downloaded once into data/models/vietocr/,
so later runs work offline.
"""
from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from labor_rag.config import VIETOCR_DIR
from labor_rag.ocr import settings

logger = logging.getLogger(__name__)

_CONFIG_URL = "https://vocr.vn/data/vietocr/config/{}"
_MODEL_CONFIG_FILES = {
    "vgg_transformer": "vgg-transformer.yml",
    "vgg_seq2seq": "vgg-seq2seq.yml",
}

# Segmentation constants, in pixels of a 300 DPI render.
_ROW_INK_RATIO = 0.02  # a row is text when its ink exceeds this share of the densest row
_LINE_MERGE_GAP = 9  # bands closer than this are one line (diacritics, underlines)
_LINE_MIN_HEIGHT = 10  # shorter bands are specks
_LINE_PAD = 2
_COLUMN_GAP_RATIO = 0.04  # a horizontal gap this wide (share of page width) separates columns
_CROP_PAD = 4
# White margin (x, y) added around each crop. Without it VietOCR tends to
# invent a word ("xã", "thế") at the edges of a tightly cropped piece; more
# page context instead of white pulls in fragments of neighbouring lines.
_WHITE_BORDER = (8, 4)
_MIN_PIECE_WIDTH = 6
_MIN_PIECE_INK = 15  # ink pixels; below this a piece is noise and VietOCR would hallucinate

_predictor = None
_predictor_lock = threading.Lock()


class OCRUnavailableError(RuntimeError):
    """VietOCR (or one of its dependencies / model files) cannot be loaded."""


@dataclass
class OCRPage:
    text: str
    line_count: int
    # Mean VietOCR character probability over the recognised pieces, 0-1.
    confidence: float


# ============================================================
# Model loading
# ============================================================

def _download(url: str, dest: Path) -> Path:
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(partial, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    partial.replace(dest)
    return dest


def _load_config(model_name: str):
    """base.yml + the model's yml, with `weights` pointing at the local copy."""
    import yaml
    from vietocr.tool.config import Cfg

    if model_name not in _MODEL_CONFIG_FILES:
        raise ValueError(f"OCR_MODEL must be one of {sorted(_MODEL_CONFIG_FILES)}, got {model_name!r}")

    merged: dict = {}
    for name in ("base.yml", _MODEL_CONFIG_FILES[model_name]):
        path = VIETOCR_DIR / name
        if not path.exists():
            _download(_CONFIG_URL.format(name), path)
        merged.update(yaml.safe_load(path.read_text(encoding="utf-8")))

    weights_url = merged["weights"]
    weights_path = VIETOCR_DIR / weights_url.rsplit("/", 1)[-1]
    if not weights_path.exists():
        logger.info("Downloading VietOCR weights %s -> %s", weights_url, weights_path)
        _download(weights_url, weights_path)
    merged["weights"] = str(weights_path)
    return Cfg(merged)


def _resolve_device() -> str:
    if settings.OCR_DEVICE:
        return settings.OCR_DEVICE
    import torch

    return "cuda:0" if torch.cuda.is_available() else "cpu"


def get_predictor():
    """Load the VietOCR predictor once per process."""
    global _predictor
    with _predictor_lock:
        if _predictor is None:
            try:
                from vietocr.tool.predictor import Predictor

                cfg = _load_config(settings.OCR_MODEL)
                cfg["device"] = _resolve_device()
                # The VGG backbone's ImageNet weights are overwritten by the OCR
                # checkpoint anyway; skip that extra download.
                cfg["cnn"]["pretrained"] = False
                cfg["predictor"]["beamsearch"] = settings.OCR_BEAMSEARCH
                logger.info("Loading VietOCR %s on %s", settings.OCR_MODEL, cfg["device"])
                _predictor = Predictor(cfg)
            except Exception as e:
                raise OCRUnavailableError(
                    "VietOCR could not be loaded. Install the OCR dependencies "
                    "(see README, section OCR) and check network access for the "
                    f"first model download. Cause: {e}"
                ) from e
        return _predictor


# ============================================================
# Segmentation
# ============================================================

def _ink_mask(image: Image.Image) -> np.ndarray:
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, h=10)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, blockSize=15, C=8
    )
    return binary > 0


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) of each run of True values."""
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


def _merge_runs(runs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in runs:
        if merged and start - merged[-1][1] <= max_gap:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def _split_tall_bands(bands: list[tuple[int, int]], profile: np.ndarray) -> list[tuple[int, int]]:
    """Split bands that hold several text lines.

    With tight line spacing the diacritics of one line touch the descenders
    of the line above, so the projection never drops to zero between them.
    A band about n line pitches tall is cut n-1 times, each cut at the row
    with the least ink near its expected position.
    """
    heights = sorted(y1 - y0 for y0, y1 in bands)
    median = heights[len(heights) // 2]
    # Single lines vary in height (with or without descenders and stacked
    # diacritics); the pitch is close to the tallest of them plus leading.
    single = [h for h in heights if h < 1.6 * median]
    pitch = 1.1 * single[int(len(single) * 0.8)]
    window = max(1, int(pitch // 3))
    out = []
    for y0, y1 in bands:
        n_lines = round((y1 - y0) / pitch)
        if n_lines < 2:
            out.append((y0, y1))
            continue
        step = (y1 - y0) / n_lines
        edges = [y0]
        for i in range(1, n_lines):
            expected = int(y0 + i * step)
            lo, hi = max(edges[-1] + 1, expected - window), min(y1 - 1, expected + window)
            edges.append(lo + int(np.argmin(profile[lo:hi])) if hi > lo else expected)
        edges.append(y1)
        out.extend(zip(edges[:-1], edges[1:]))
    return out


def _find_lines(ink: np.ndarray) -> list[tuple[int, int]]:
    profile = ink.sum(axis=1)
    if profile.max() == 0:
        return []
    bands = _merge_runs(_runs(profile > profile.max() * _ROW_INK_RATIO), _LINE_MERGE_GAP)
    bands = [(y0, y1) for y0, y1 in bands if y1 - y0 + 2 * _LINE_PAD >= _LINE_MIN_HEIGHT]
    if not bands:
        return []
    height = ink.shape[0]
    return [
        (max(0, y0 - _LINE_PAD), min(height, y1 + _LINE_PAD))
        for y0, y1 in _split_tall_bands(bands, profile)
    ]


def _cut_wide(x0: int, x1: int, has_ink: np.ndarray, max_width: int) -> list[tuple[int, int]]:
    """Cut [x0, x1) into pieces no wider than max_width, each cut in the widest
    blank gap of the right half of the window so words are not split."""
    pieces = []
    start = x0
    while x1 - start > max_width:
        lo = start + max_width // 2
        gaps = _runs(~has_ink[lo:start + max_width])
        if gaps:
            g0, g1 = max(gaps, key=lambda g: (g[1] - g[0], g[0]))
            cut = lo + (g0 + g1) // 2
        else:
            cut = start + max_width
        pieces.append((start, cut))
        start = cut
    pieces.append((start, x1))
    return pieces


def _line_pieces(ink_line: np.ndarray, page_width: int, max_width: int) -> list[tuple[int, int]]:
    """Horizontal pieces of one text line, left to right."""
    column_ink = ink_line.sum(axis=0)
    has_ink = column_ink >= 2  # ignore single-pixel specks
    segments = _merge_runs(_runs(has_ink), int(page_width * _COLUMN_GAP_RATIO))
    pieces = []
    for x0, x1 in segments:
        if x1 - x0 < _MIN_PIECE_WIDTH or column_ink[x0:x1].sum() < _MIN_PIECE_INK:
            continue
        pieces.extend(_cut_wide(x0, x1, has_ink, max_width))
    return pieces


# ============================================================
# Recognition
# ============================================================

def ocr_image(image: Image.Image) -> OCRPage:
    """OCR one page image (a rendered PDF page or a photo)."""
    predictor = get_predictor()
    image = image.convert("RGB")
    ink = _ink_mask(image)
    dataset_cfg = predictor.config["dataset"]
    # Width/height ratio the model accepts without squeezing, with some slack
    # for its rounding to multiples of 10.
    max_ratio = 0.95 * dataset_cfg["image_max_width"] / dataset_cfg["image_height"]

    crops: list[Image.Image] = []
    owners: list[int] = []  # line index of each crop
    lines = _find_lines(ink)
    for line_idx, (y0, y1) in enumerate(lines):
        max_width = int((y1 - y0) * max_ratio)
        for x0, x1 in _line_pieces(ink[y0:y1], image.width, max_width):
            crop = image.crop((max(0, x0 - _CROP_PAD), y0, min(image.width, x1 + _CROP_PAD), y1))
            crops.append(ImageOps.expand(crop, border=_WHITE_BORDER, fill=(255, 255, 255)))
            owners.append(line_idx)

    if not crops:
        return OCRPage(text="", line_count=0, confidence=0.0)

    # A piece decoded to no characters gets probability 0/0 = nan; dropped below.
    with np.errstate(invalid="ignore"):
        texts, probs = predictor.predict_batch(crops, return_prob=True)

    line_texts: list[list[str]] = [[] for _ in lines]
    kept_probs = []
    for line_idx, text, prob in zip(owners, texts, probs):
        text = text.strip()
        if text:
            line_texts[line_idx].append(text)
            if not math.isnan(prob):
                kept_probs.append(prob)
    page_lines = [" ".join(parts) for parts in line_texts if parts]
    return OCRPage(
        text="\n".join(page_lines),
        line_count=len(page_lines),
        confidence=float(np.mean(kept_probs)) if kept_probs else 0.0,
    )

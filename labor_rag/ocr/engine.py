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
5. page numbers and specks are dropped by layout (_margin_lines,
   _side_specks): VietOCR returns characters for any crop, so dust next to
   "40" comes out as "4U e" and no text filter can catch it
6. pieces are recognised in one batch per page, on the original
   (non-binarised) crop with a white margin, and reassembled
   top-to-bottom, left-to-right

The model config and weights are downloaded once into data/models/vietocr/,
so later runs work offline.
"""
from __future__ import annotations

import logging
import math
import re
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
_LINE_PAD = 3
_COLUMN_GAP_RATIO = 0.04  # a horizontal gap this wide (share of page width) separates columns
_CROP_PAD = 4
# White margin (x, y) added around each crop. Without it VietOCR tends to
# invent a word ("xã", "thế") at the edges of a tightly cropped piece; more
# page context instead of white pulls in fragments of neighbouring lines.
_WHITE_BORDER = (8, 4)
_MIN_PIECE_WIDTH = 6
_MIN_PIECE_INK = 15  # ink pixels; below this a piece is noise and VietOCR would hallucinate
# Page numbers and specks in the margins (see _margin_lines), as shares of the page.
_BODY_LINE_RATIO = 0.25  # a line whose pieces cover this much of the width is body text
_MARGIN_PIECE_RATIO = 0.06  # pieces narrower than this can be a page number ("82" is ~3%)
_MARGIN_ZONE_RATIO = 0.15  # top / bottom band searched for them
_SIDE_MARGIN_RATIO = 0.02  # pieces this far outside the text block's left / right edge are specks

_predictor = None
_predictor_key = None
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
    global _predictor, _predictor_key
    with _predictor_lock:
        key = (settings.OCR_MODEL, settings.OCR_DEVICE, settings.OCR_BEAMSEARCH)
        if _predictor is None or _predictor_key != key:
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
                _predictor_key = key
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

_DESKEW_MIN_DIM = 200
_DESKEW_MAX_ANGLE = 4.0
_REPEAT_WORD_RE = re.compile(r"\b([^\W\d_]+)(?:\s+\1){4,}\b", re.IGNORECASE | re.UNICODE)


def _deskew_image(image: Image.Image) -> Image.Image:
    """Correct slight scan tilt (-4..+4 deg) by maximising horizontal-projection
    variance on a fast 4x downscaled mask so tilted lines do not merge."""
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    if min(h, w) < _DESKEW_MIN_DIM:
        return image

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(gray, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_AREA)
    mask = (
        cv2.adaptiveThreshold(small, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 6) > 0
    ).astype(np.uint8)
    if int(mask.sum()) < 200:
        return image

    sh, sw = mask.shape
    center = (sw / 2.0, sh / 2.0)
    base_var = float(np.var(mask.sum(axis=1)))
    best_angle, best_var = 0.0, base_var

    # Coarse 0.25 deg sweep, then fine 0.05 deg sweep around the peak.
    for angle in np.linspace(-_DESKEW_MAX_ANGLE, _DESKEW_MAX_ANGLE, 33):
        M = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        rot = cv2.warpAffine(mask, M, (sw, sh), flags=cv2.INTER_NEAREST)
        var = float(np.var(rot.sum(axis=1)))
        if var > best_var:
            best_var, best_angle = var, float(angle)

    coarse_best = best_angle
    for angle in np.linspace(coarse_best - 0.3, coarse_best + 0.3, 13):
        M = cv2.getRotationMatrix2D(center, float(angle), 1.0)
        rot = cv2.warpAffine(mask, M, (sw, sh), flags=cv2.INTER_NEAREST)
        var = float(np.var(rot.sum(axis=1)))
        if var > best_var:
            best_var, best_angle = var, float(angle)

    if abs(best_angle) < 0.05 or best_var <= base_var * 1.02:
        return image

    M_full = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), best_angle, 1.0)
    rotated = cv2.warpAffine(rgb, M_full, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
    return Image.fromarray(rotated)


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
    ref_h = median
    if len(heights) >= 4:
        p25 = heights[len(heights) // 4]
        if median > 1.7 * p25 and p25 >= _LINE_MIN_HEIGHT * 2:
            ref_h = p25
    # Single lines vary in height (with or without descenders and stacked
    # diacritics); the pitch is close to the tallest of them plus leading.
    single = [h for h in heights if h < 1.6 * ref_h] or heights[:1]
    pitch = 1.1 * single[int(len(single) * 0.8)]
    window = max(1, int(pitch // 3))
    smooth = np.convolve(profile.astype(np.float32), [0.25, 0.5, 0.25], mode="same")
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
            edges.append(lo + int(np.argmin(smooth[lo:hi])) if hi > lo else expected)
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

def _margin_lines(lines: list[tuple[int, int]], pieces: list[list[tuple[int, int]]],
                  width: int, height: int) -> set[int]:
    """Indexes of page-number / speck lines above the first or below the last body line.

    VietOCR always returns characters, so a page number with dust next to it
    comes out as "4U e" or "rn" and no text filter can recognise it. Such
    lines are told apart by layout instead: they sit in the top or bottom
    margin, every piece is narrow, and a gap of at least one line height
    separates them from the body. A heading at the top of a page ("Chương II",
    "Điều 5.") is wider than a page number or close to the next line.
    """
    # Width actually covered by text: a speck far right of a page number must
    # not make that line look as wide as a body line.
    def covered(index: int) -> int:
        return sum(x1 - x0 for x0, x1 in pieces[index])

    body = [i for i in range(len(lines)) if covered(i) >= _BODY_LINE_RATIO * width]
    if not body:
        return set()
    heights = sorted(lines[i][1] - lines[i][0] for i in body)
    line_height = heights[len(heights) // 2]

    def narrow(index: int) -> bool:
        return all(x1 - x0 < _MARGIN_PIECE_RATIO * width for x0, x1 in pieces[index])

    # Walk outwards from the body: a narrow line is margin when a gap of a line
    # height separates it from the nearest line kept on the body side (specks
    # next to a dropped page number therefore go too); anything else is kept
    # and becomes the new reference.
    dropped: set[int] = set()
    edge = lines[body[0]][0]
    for i in range(body[0] - 1, -1, -1):
        if lines[i][1] > _MARGIN_ZONE_RATIO * height:
            edge = lines[i][0]
        elif narrow(i) and edge - lines[i][1] >= line_height:
            dropped.add(i)
        else:
            edge = lines[i][0]
    edge = lines[body[-1]][1]
    for i in range(body[-1] + 1, len(lines)):
        if lines[i][0] < (1 - _MARGIN_ZONE_RATIO) * height:
            edge = lines[i][1]
        elif narrow(i) and lines[i][0] - edge >= line_height:
            dropped.add(i)
        else:
            edge = lines[i][1]
    return dropped


def _side_specks(pieces: list[list[tuple[int, int]]], width: int) -> list[list[tuple[int, int]]]:
    """Pieces with narrow pieces in the left / right page margin removed.

    Dust beside a line ("· ·" left of a heading) is read as "1" or "e" and
    glued to the line. The text block's edges are taken from the body lines;
    a narrow piece lying wholly outside them is a speck.
    """
    def wide(piece: tuple[int, int]) -> bool:
        return piece[1] - piece[0] >= _MARGIN_PIECE_RATIO * width

    # Edges come from the wide pieces of body lines only, so a speck on a body
    # line cannot widen the block; an outdented heading still counts.
    body = [[p for p in line if wide(p)] for line in pieces
            if sum(x1 - x0 for x0, x1 in line) >= _BODY_LINE_RATIO * width]
    body = [line for line in body if line]
    if len(body) < 3:
        return pieces
    margin = _SIDE_MARGIN_RATIO * width
    left = min(line[0][0] for line in body) - margin
    right = max(line[-1][1] for line in body) + margin

    def speck(x0: int, x1: int) -> bool:
        return not wide((x0, x1)) and (x1 < left or x0 > right)

    return [[(x0, x1) for x0, x1 in line if not speck(x0, x1)] for line in pieces]


# VietOCR has no curly quotes in its vocabulary and reads them as "?":
# “Điều 32. ...” comes out as ?Điều 32. ...? . A "?" opening a line before a
# letter or closing one after punctuation is such a quote; a real question
# mark follows a word.
_OPEN_QUOTE_RE = re.compile(r"^\?(?=[^\W\d_])", re.UNICODE)
_CLOSE_QUOTE_RE = re.compile(r"(?<=[.;:,!])\?(?=[.;,]?(?:\s|$))")  # "...giải quyết.?;" too


def _restore_quotes(line: str) -> str:
    return _CLOSE_QUOTE_RE.sub('"', _OPEN_QUOTE_RE.sub('"', line))


def _clean_ocr_piece(text: str) -> str:
    """Collapse Transformer repetition loops (e.g. 'thời thời thời thời thời')."""
    return _REPEAT_WORD_RE.sub(r"\1", text.strip())


def ocr_image(image: Image.Image) -> OCRPage:
    """OCR one page image (a rendered PDF page or a photo)."""
    predictor = get_predictor()
    image = _deskew_image(image.convert("RGB"))
    ink = _ink_mask(image)
    dataset_cfg = predictor.config["dataset"]
    # Width/height ratio the model accepts without squeezing, with some slack
    # for its rounding to multiples of 10.
    max_ratio = 0.95 * dataset_cfg["image_max_width"] / dataset_cfg["image_height"]

    crops: list[Image.Image] = []
    owners: list[int] = []  # line index of each crop
    lines = _find_lines(ink)
    pieces = _side_specks([_line_pieces(ink[y0:y1], image.width, int((y1 - y0) * max_ratio)) for y0, y1 in lines],
                          image.width)
    margin = _margin_lines(lines, pieces, image.width, image.height)
    for line_idx, (y0, y1) in enumerate(lines):
        if line_idx in margin:
            continue
        for x0, x1 in pieces[line_idx]:
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
        text = _clean_ocr_piece(text)
        if text:
            line_texts[line_idx].append(text)
            if not math.isnan(prob):
                kept_probs.append(prob)
    page_lines = [_restore_quotes(" ".join(parts)) for parts in line_texts if parts]
    return OCRPage(
        text="\n".join(page_lines),
        line_count=len(page_lines),
        confidence=float(np.mean(kept_probs)) if kept_probs else 0.0,
    )

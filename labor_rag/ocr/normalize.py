"""Unicode normalisation for Vietnamese text coming out of PDFs and OCR:
NFC composition, typographic look-alikes to ASCII, and the eth/đ confusion
OCR engines often make.
"""
from __future__ import annotations

import re
import unicodedata

_SPECIAL_CHAR_MAP = {
    # dashes
    "–": "-", "—": "-", "―": "-", "‒": "-",
    # double quotes
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    # single quotes
    "‘": "'", "’": "'", "‚": "'",
    "…": "...",
    # special spaces and zero-width characters
    " ": " ", " ": " ", " ": " ", " ": " ", " ": " ",
    "​": "", "‌": "", "‍": "", "﻿": "",
    # bullets
    "•": "-", "‣": "-", "●": "-", "○": "-", "■": "-", "□": "-",
}
_SPECIAL_CHAR_PATTERN = re.compile("|".join(re.escape(k) for k in _SPECIAL_CHAR_MAP))


def normalize_unicode_nfc(text: str) -> str:
    """Combining diacritics -> precomposed characters ('a' + U+0300 -> 'à')."""
    return unicodedata.normalize("NFC", text)


def replace_special_chars(text: str) -> str:
    return _SPECIAL_CHAR_PATTERN.sub(lambda m: _SPECIAL_CHAR_MAP[m.group()], text)


def fix_vietnamese_ocr_errors(text: str) -> str:
    """OCR and legacy fonts emit the Latin eth (ð/Ð) where Vietnamese has đ/Đ."""
    return text.replace("ð", "đ").replace("Ð", "Đ")


def full_normalize(text: str) -> str:
    text = normalize_unicode_nfc(text)
    text = replace_special_chars(text)
    return fix_vietnamese_ocr_errors(text)

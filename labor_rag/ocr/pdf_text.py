"""Text-layer extraction with PyMuPDF, in natural reading order.

Blocks are sorted top-to-bottom; on a two-column page the left column is
read before the right one.
"""
from __future__ import annotations

from dataclasses import dataclass

import pymupdf


@dataclass
class TextBlock:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2


def _is_two_column(blocks: list[TextBlock], page_width: float) -> bool:
    """Most blocks sit clearly left or right of the page centre."""
    if len(blocks) < 4:
        return False
    mid_x = page_width / 2
    margin = page_width * 0.1
    left = sum(1 for b in blocks if b.x1 < mid_x - margin)
    right = sum(1 for b in blocks if b.x0 > mid_x + margin)
    return left > 2 and right > 2 and (left + right) / len(blocks) >= 0.6


def _reading_order(blocks: list[TextBlock], page_width: float) -> list[TextBlock]:
    if not _is_two_column(blocks, page_width):
        return sorted(blocks, key=lambda b: (b.y0, b.x0))
    mid_x = page_width / 2
    left = sorted((b for b in blocks if b.center_x < mid_x), key=lambda b: b.y0)
    right = sorted((b for b in blocks if b.center_x >= mid_x), key=lambda b: b.y0)
    return left + right


def extract_page_text(page: pymupdf.Page) -> str:
    # get_text("blocks") rows: (x0, y0, x1, y1, text, block_no, block_type)
    blocks = [
        TextBlock(x0, y0, x1, y1, text.strip())
        for x0, y0, x1, y1, text, _, block_type in page.get_text("blocks")
        if block_type == 0
    ]
    ordered = _reading_order(blocks, page.rect.width)
    return "\n".join(b.text for b in ordered if b.text)

"""Length-aware batching for embedding long legal chunks on a small GPU.

A batch is padded to its longest text, so one 2,000-token Dieu among 63 short
ones pads the whole batch to 2,000 tokens. Sorting by length and capping each
batch at a token budget (batch size x longest length) keeps padding near zero
and peak VRAM roughly constant: short chunks go ~40 per batch, the longest go
alone. Measured on an RTX 3050 4 GB: bge-m3 in fp32 (SDPA attention) peaks at
2.5 GB for a single 8,192-token chunk.
"""
from __future__ import annotations

from typing import Any

DEFAULT_MAX_BATCH_TOKENS = 8192


def length_batches(
    texts: list[str],
    tokenizer: Any,
    max_seq_length: int,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
    max_batch_size: int = 64,
) -> list[list[int]]:
    """Group text indices into batches, longest texts first, so that
    len(batch) * longest_in_batch <= max_batch_tokens (always >= 1 text)."""
    lengths = [
        min(len(tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"]), max_seq_length)
        for text in texts
    ]
    # Longest first: if the budget is too high for the GPU it fails at once.
    order = sorted(range(len(texts)), key=lambda i: lengths[i], reverse=True)
    batches: list[list[int]] = []
    current: list[int] = []
    for index in order:
        longest = lengths[current[0]] if current else lengths[index]
        if current and ((len(current) + 1) * longest > max_batch_tokens or len(current) >= max_batch_size):
            batches.append(current)
            current = []
        current.append(index)
    if current:
        batches.append(current)
    return batches

"""Align fine-tune records to the v5 corpus (docs/FINETUNE_DATA.md).

A record's legal passage is matched to v5 chunks by shared word 8-grams, so
the positive is always the chunk text the index actually serves, whatever
version or excerpt the source quoted. Per chunk:

    score = max(shared / passage_grams, shared / chunk_grams)

the first term covers an excerpt of one clause, the second an answer that
quotes the whole article inside commentary. Sources that already mapped
exact chunk ids are checked against their passage; a failed check falls
back to the corpus-wide match.

Tiers: A score >= 0.5, B 0.1-0.5, C below 0.1 or no chunk.
Temporal status, compared with the corpus snapshot:
    keep      cited document is the one the positive belongs to (or none cited)
    remap     content matches v5 but the source cited another document
              (an older or amending version, e.g. BLLD 2012 -> 45/2019/QH14)
    pending   no v5 match and the cited document is not in v5 but was issued in
              PENDING_FROM_YEAR or later: likely newer than the corpus, kept
              aside until the corpus is updated
    outside   no v5 match otherwise (other topic, or an older law v5 replaced)
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from labor_rag.ingest.chunk_schema import article_id

NGRAM = 8
MIN_SHARED = 3
TIER_A = 0.5
TIER_B = 0.1
MAX_POSITIVES = 3
# Exact ids from these sources were already verified by content (15-word probe).
VERIFIED_EXACT = {"tvpl"}

WORD_RE = re.compile(r"\W+")
YEAR_RE = re.compile(r"^\d+[a-z]?-((?:19|20)\d{2})-")
# Laws from here on (BHXH 2024, Viec lam 2025, ...) may postdate the Phap dien snapshot.
PENDING_FROM_YEAR = 2024


def norm(text: str) -> str:
    return WORD_RE.sub(" ", (text or "").lower()).strip()


def grams(text: str, n: int = NGRAM) -> set[str]:
    words = norm(text).split()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def body(chunk_text: str) -> str:
    """Chunk text without the 'Lao động > Bộ luật ... > Chương' breadcrumb line."""
    head, sep, rest = chunk_text.partition("\n")
    return rest if sep and " > " in head else chunk_text


def tier_of(score: float | None) -> str:
    if score is None:
        return "C"
    return "A" if score >= TIER_A else "B" if score >= TIER_B else "C"


def doc_year(document_id: str | None) -> int | None:
    match = YEAR_RE.match(document_id or "")
    return int(match.group(1)) if match else None


class V5Index:
    """Inverted 8-gram index over the v5 chunk bodies."""

    def __init__(self, chunks: list[dict[str, Any]]):
        self.chunks = {c["chunk_id"]: c for c in chunks}
        self.size: dict[str, int] = {}
        self.postings: dict[str, list[str]] = defaultdict(list)
        for cid, c in self.chunks.items():
            g = grams(body(c["text"]))
            self.size[cid] = len(g)
            for gram in g:
                self.postings[gram].append(cid)
        self.documents = {c["document_id"] for c in chunks}

    @classmethod
    def from_jsonl(cls, path: Path) -> V5Index:
        with path.open(encoding="utf-8") as f:
            return cls([json.loads(line) for line in f if line.strip()])

    def scores(self, passage: str, candidates: list[str] | None = None) -> dict[str, float]:
        """score per chunk sharing at least MIN_SHARED 8-grams with the passage."""
        pg = grams(passage)
        if not pg:
            return {}
        allowed = set(candidates) if candidates is not None else None
        shared: Counter[str] = Counter()
        for gram in pg:
            for cid in self.postings.get(gram, ()):
                if allowed is None or cid in allowed:
                    shared[cid] += 1
        return {
            cid: max(n / len(pg), n / self.size[cid])
            for cid, n in shared.items()
            if n >= MIN_SHARED and self.size[cid]
        }

    def is_valid(self, cid: str) -> bool:
        return self.chunks[cid].get("still_valid", True) is not False


def pick_positives(scores: dict[str, float]) -> tuple[list[str], float | None]:
    """Best chunk plus near-equal ones (other parts of a long article, or a second cited article)."""
    if not scores:
        return [], None
    best = max(scores.values())
    keep = sorted((cid for cid, s in scores.items() if s >= max(TIER_B, 0.6 * best)),
                  key=lambda cid: -scores[cid])[:MAX_POSITIVES]
    return keep, round(best, 4)


def align_record(rec: dict[str, Any], index: V5Index) -> dict[str, Any]:
    exact = [cid for cid in rec.get("exact_chunk_ids") or [] if cid in index.chunks]
    passage = rec.get("passage")
    positives: list[str] = []
    score: float | None = None
    method = "none"

    if passage:
        if exact:
            positives, score = pick_positives(index.scores(passage, exact))
            method = "exact_verified"
        if tier_of(score) == "C":
            global_pos, global_score = pick_positives(index.scores(passage))
            if global_score is not None and (score is None or global_score > score):
                positives, score = global_pos, global_score
                method = "exact_rejected" if exact else "content"
    elif exact:
        positives = exact[:MAX_POSITIVES]
        method = "exact_verified" if rec["source"] in VERIFIED_EXACT else "exact_unverified"

    if method == "exact_verified" and not passage:
        tier = "A"
    elif method == "exact_unverified":
        tier = "B"
    else:
        tier = tier_of(score)
    if tier == "C":
        positives = []

    cited = rec.get("cited_doc")
    if positives and not all(index.is_valid(cid) for cid in positives):
        temporal = "outside"
    elif positives:
        pos_doc = index.chunks[positives[0]]["document_id"]
        temporal = "keep" if not cited or cited == pos_doc or cited in index.documents else "remap"
    else:
        year = doc_year(cited)
        newer = bool(cited and cited not in index.documents and year and year >= PENDING_FROM_YEAR)
        temporal = "pending" if newer else "outside"

    return {
        **rec,
        "positive_chunk_ids": positives,
        "articles": sorted({article_id(cid) for cid in positives}),
        "score": score,
        "tier": tier,
        "temporal": temporal,
        "match": method,
    }

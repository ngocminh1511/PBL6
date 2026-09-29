"""Citation Verification: check every "Dieu N..." citation the LLM's answer
mentions against the ground-truth text actually retrieved (Dieu title +
pGhiChu citation string), flagging anything that doesn't match as
unverified -- a guard against citation hallucination before the answer is
returned to the user.
"""
from __future__ import annotations

import re

from retrieval.hybrid_retrieve import Evidence

CITE_RE = re.compile(r"Điều\s+\d+(?:[.,]\d+)*")


def verify_citations(answer: str, evidences: list[Evidence]) -> dict:
    cited = sorted({m.group(0).strip() for m in CITE_RE.finditer(answer)})
    blob = "\n".join(f"{e.ten or ''} {e.citation or ''}" for e in evidences)

    verified, unverified = [], []
    for cite in cited:
        # require the matched number not be immediately followed by another
        # digit in the evidence blob, so "Điều 1" doesn't false-match "Điều 13"
        pattern = re.escape(cite) + r"(?!\d)"
        (verified if re.search(pattern, blob) else unverified).append(cite)

    return {
        "verified": verified,
        "unverified": unverified,
        "all_verified": not unverified,
    }

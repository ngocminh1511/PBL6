"""Citation Verification: check every "Dieu N ..." citation the LLM's answer
mentions against the Dieu actually retrieved (meta_dieu + source document),
flagging anything that doesn't match as unverified -- a guard against citation
hallucination before the answer is returned to the user.
"""
from __future__ import annotations

import re

from labor_rag.ingest.chunk_schema import make_document_id
from labor_rag.retrieval.hybrid_retrieve import Evidence

CITE_RE = re.compile(r"Điều\s+(\d+[a-zđ]?)(?![\w.])")
# A document number named right after the Dieu: "Điều 35 khoản 2 Nghị định số 145/2020/NĐ-CP".
SO_HIEU_RE = re.compile(r"\d+/\d{4}/[\wĐđ-]+")
SO_HIEU_WINDOW = 120


def verify_citations(answer: str, evidences: list[Evidence]) -> dict:
    retrieved = {(e.document_id, e.meta_dieu) for e in evidences if e.meta_dieu}
    retrieved_dieu = {dieu for _, dieu in retrieved}

    cited: dict[str, bool] = {}
    for match in CITE_RE.finditer(answer):
        dieu = match.group(1)
        # Only look up to the next "Điều" so one citation's document is not
        # attributed to the previous one.
        tail = answer[match.end() : match.end() + SO_HIEU_WINDOW].split("Điều", 1)[0]
        so_hieu = SO_HIEU_RE.search(tail)
        if so_hieu:
            label = f"Điều {dieu} {so_hieu.group(0)}"
            ok = (make_document_id(so_hieu.group(0)), dieu) in retrieved
        else:
            label = f"Điều {dieu}"
            ok = dieu in retrieved_dieu
        cited[label] = cited.get(label, False) or ok

    verified = sorted(label for label, ok in cited.items() if ok)
    unverified = sorted(label for label, ok in cited.items() if not ok)
    return {
        "verified": verified,
        "unverified": unverified,
        "all_verified": not unverified,
    }

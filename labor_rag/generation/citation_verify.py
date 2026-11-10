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
APPENDIX_RE = re.compile(r"Phụ\s*lục\s+(\d+[ab]?|[IVXLCDM]+[ab]?)(?!\w)", re.IGNORECASE)


def verify_citations(answer: str, evidences: list[Evidence]) -> dict:
    evidences = evidences + [amendment for e in evidences for amendment in e.amendments]
    retrieved = {(e.document_id, e.meta_dieu) for e in evidences if e.meta_dieu}
    retrieved_dieu = {dieu for _, dieu in retrieved}

    cited: dict[str, bool] = {}
    from labor_rag.appendices.labels import canonical_label
    retrieved_appendices = {(e.document_id, canonical_label(e.appendix_number)) for e in evidences
                            if e.appendix_id and e.appendix_number and re.fullmatch(r"\d+[ab]?|[IVXLCDM]+[ab]?",e.appendix_number,re.I)}
    for match in APPENDIX_RE.finditer(answer):
        label = match[1]
        tail = re.split(r"Phụ\s*lục|Điều\s+\d",answer[match.end():match.end()+SO_HIEU_WINDOW],maxsplit=1,flags=re.I)[0]
        number = SO_HIEU_RE.search(tail)
        key = canonical_label(label)
        if number:
            title = f"Phụ lục {label} {number[0]}"
            ok = (make_document_id(number[0]),key) in retrieved_appendices
        else:
            title = f"Phụ lục {label}"
            matches = {doc for doc,value in retrieved_appendices if value==key}
            ok = len(matches)==1
        cited[title] = cited.get(title,False) or ok
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

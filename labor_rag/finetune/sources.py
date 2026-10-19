"""Read every fine-tune source into one record shape (docs/FINETUNE_DATA.md).

Each adapter yields dicts:

    {
        "qid": "<source>:<id>",
        "query": "...",
        "source": "<source>",
        "is_synthetic": bool,          # LLM-generated question (phamson02)
        "passage": str | None,         # legal text the source pairs with the query
        "cited_doc": str | None,       # document_id form, e.g. 45-2019-qh14
        "cited_article": str | None,   # article number as written by the source
        "exact_chunk_ids": [...],      # v5 chunk ids when the source already mapped them
    }

`passage` is None when the source's text is not statute wording (VLSP's
"Tiền đề lớn" is a paraphrase), so alignment falls back to the citation.
Large multi-domain sources are pre-filtered with LABOR_QUERY_RE on the
query; the v5 alignment (align.py) is the real domain filter.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from labor_rag.config import finetune_raw_dir, finetune_source_dir
from labor_rag.ingest.chunk_schema import make_document_id

LABOR_QUERY_RE = re.compile(
    r"người lao động|người sử dụng lao động|hợp đồng lao động|lương tối thiểu|tiền lương|trả lương"
    r"|làm thêm giờ|thử việc|sa thải|thôi việc|mất việc|trợ cấp thất nghiệp|bảo hiểm thất nghiệp"
    r"|tai nạn lao động|bệnh nghề nghiệp|nghỉ hằng năm|nghỉ phép|kỷ luật lao động|công đoàn|đình công"
    r"|thỏa ước lao động|thoả ước lao động|vệ sinh lao động|giấy phép lao động|lao động nữ|lao động nước ngoài"
    r"|việc làm|thai sản|thời giờ làm việc|thời giờ nghỉ ngơi|nghỉ hưu|tuổi nghỉ hưu|cho thuê lại lao động"
    r"|đi làm việc ở nước ngoài|lao động chưa thành niên|người học nghề|tập nghề|giáo dục nghề nghiệp"
)
SO_HIEU_RE = re.compile(r"(\d+(?:/\d{4})?/[A-Za-zĐđ0-9\-]+)")
PHAMSON02_DOMAINS = ("Lao động - Tiền lương", "Bảo hiểm")
NOISE_RE = re.compile(r"\(Hình từ Internet\)", re.IGNORECASE)


def is_labor_query(query: str) -> bool:
    return bool(LABOR_QUERY_RE.search(query.lower()))


def doc_id_from_text(text: str | None) -> str | None:
    """First so hieu in free text ("Thông tư 09/2015/TT-BGTVT ...") as a document_id."""
    match = SO_HIEU_RE.search(text or "")
    return make_document_id(match.group(1)) if match else None


def record(source: str, qid: Any, query: str, *, passage: str | None = None, cited_doc: str | None = None,
           cited_article: Any = None, exact_chunk_ids: list[str] | None = None,
           is_synthetic: bool = False) -> dict[str, Any]:
    return {
        "qid": f"{source}:{qid}",
        "query": " ".join(query.split()),
        "source": source,
        "is_synthetic": is_synthetic,
        "passage": passage.strip() if passage and passage.strip() else None,
        "cited_doc": cited_doc or None,
        "cited_article": str(cited_article) if cited_article not in (None, "") else None,
        "exact_chunk_ids": list(exact_chunk_ids or []),
    }


def _jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tvpl() -> Iterator[dict[str, Any]]:
    """TVPL-Retrieval-VN (Kha). The v5 file holds chunk ids matched by a 15-word probe;
    the expanded file holds the TVPL passage itself."""
    folder = finetune_source_dir("tvpl")
    for r in _jsonl(folder / "tvpl_lao_dong_train.jsonl"):
        yield record("tvpl", r["corpus_id"] + ":v5", r["query"], cited_doc=r.get("document_id"),
                     cited_article=r.get("meta_dieu"), exact_chunk_ids=r.get("positive_chunk_ids"))
    for r in _jsonl(folder / "tvpl_lao_dong_expanded.jsonl"):
        if is_labor_query(r["query"]):
            yield record("tvpl", r["corpus_id"], r["query"], passage=r.get("positive_text"),
                         exact_chunk_ids=r.get("positive_chunk_ids"))


def load_vlsp() -> Iterator[dict[str, Any]]:
    """VLSP 2025 QA (Kha). The premise is a paraphrase, so only the citation is used."""
    for r in _jsonl(finetune_source_dir("vlsp") / "vlsp_lao_dong_train.jsonl"):
        if is_labor_query(r["query"]):
            yield record("vlsp", r["id"], r["query"], cited_doc=r.get("document_id"),
                         cited_article=r.get("meta_dieu"), exact_chunk_ids=r.get("positive_chunk_ids"))


def load_vilegal() -> Iterator[dict[str, Any]]:
    """ViLegalExpert mapped by map_vilegal_labor.py; review records carry no article."""
    folder = finetune_source_dir("vilegal")
    for name in ("vilegal_labor_mapped.json", "vilegal_labor_review.json"):
        path = folder / name
        if not path.exists():
            continue
        for r in _json(path):
            ctx = r.get("context") or {}
            answer = NOISE_RE.sub("", r.get("answer") or "")
            yield record("vilegal", r["record_id"], r["question"], passage=answer,
                         cited_doc=ctx.get("document_id"), cited_article=ctx.get("article_id"),
                         exact_chunk_ids=ctx.get("chunk_ids"))


def load_zalo() -> Iterator[dict[str, Any]]:
    """ZaloAI 2021 LTR mapped by map_zaloai_labor.py; text is word-segmented ("trợ_cấp")."""
    for r in _json(finetune_source_dir("zalo") / "zaloai_ltr_lao_dong.json"):
        arts = r.get("relevant_articles") or []
        passage = "\n".join(a.get("text", "") for a in arts).replace("_", " ")
        ids = [cid for a in arts for cid in a.get("chunk_ids", [])]
        first = arts[0] if arts else {}
        yield record("zalo", r["question_id"], r["question"].replace("_", " "), passage=passage,
                     cited_doc=first.get("document_id"), cited_article=first.get("article_id"),
                     exact_chunk_ids=ids)


def load_bkai() -> Iterator[dict[str, Any]]:
    """BKAI legal retrieval (YuITC mirror): real questions + statute passages."""
    import pandas as pd

    for split in ("train", "test"):
        path = finetune_raw_dir("bkai") / f"{split}.parquet"
        if not path.exists():
            continue
        for row in pd.read_parquet(path, columns=["qid", "question", "context_list"]).itertuples(index=False):
            if not is_labor_query(row.question):
                continue
            contexts = json.loads(row.context_list) if isinstance(row.context_list, str) else list(row.context_list)
            passage = "\n".join(str(c) for c in contexts)
            yield record("bkai", row.qid, row.question, passage=passage, cited_doc=doc_id_from_text(passage[:300]))


def load_phamson02() -> Iterator[dict[str, Any]]:
    """Synthetic queries written by an LLM from real statute passages."""
    import pandas as pd

    path = finetune_raw_dir("phamson02") / "large_vi_legal_queries.parquet"
    df = pd.read_parquet(path, columns=["passage_id", "domain", "title", "context", "query"])
    df = df[df["domain"].str.contains("|".join(PHAMSON02_DOMAINS), na=False)]
    for i, row in enumerate(df.itertuples(index=False)):
        if is_labor_query(row.query):
            yield record("phamson02", f"{row.passage_id}:{i}", row.query, passage=row.context,
                         cited_doc=doc_id_from_text(row.title), is_synthetic=True)


def load_alqac() -> Iterator[dict[str, Any]]:
    """ALQAC (VMTEB copy): expert questions with gold article ids like 45/2019/qh14#32."""
    import pandas as pd

    root = finetune_raw_dir("alqac")
    corpus = pd.read_parquet(root / "corpus" / "train-00000-of-00001.parquet").set_index("id")
    queries = pd.read_parquet(root / "queries" / "train-00000-of-00001.parquet").set_index("query_id")
    qrels = pd.read_parquet(root / "data_ir" / "train-00000-of-00001.parquet")
    for qid, rels in qrels.groupby("query_id"):
        question = queries.loc[qid, "question"]
        if not is_labor_query(question):
            continue
        ids = [cid for cid in rels["corpus_id"] if cid in corpus.index]
        passage = "\n".join(f"{corpus.loc[cid, 'title']} {corpus.loc[cid, 'text']}" for cid in ids)
        doc, _, article = (ids[0].partition("#") if ids else ("", "", ""))
        yield record("alqac", qid, question, passage=passage, cited_doc=make_document_id(doc) if doc else None,
                     cited_article=article)


LOADERS = {
    "tvpl": load_tvpl,
    "vlsp": load_vlsp,
    "vilegal": load_vilegal,
    "zalo": load_zalo,
    "bkai": load_bkai,
    "phamson02": load_phamson02,
    "alqac": load_alqac,
}


def load_source(source: str) -> list[dict[str, Any]]:
    return list(LOADERS[source]())

"""OCR revisions of an ingestion task, kept in PostgreSQL.

Revision 1 is the OCR output and is never edited. Review revisions are
copies the user edits: at most one "draft" per task, the one confirmed last
is "indexed", older ones are "locked". Tasks from before this table have
their pages only in data/interim/ingestion/<task>/ocr_pages.jsonl; they are
imported the first time they are read.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.backend.app.models.database import IngestionTask, OcrPage, OcrRevision


class RevisionLocked(Exception):
    """The revision is the OCR output or an indexed/locked review: it cannot be edited."""


class DraftExists(Exception):
    """The task already has a draft revision."""


def _page_entry(page: OcrPage) -> dict:
    return {"page_number": page.page_number, "total_pages": page.total_pages, "method": page.method,
            "confidence": page.confidence, "char_count": page.char_count, "text": page.text}


def revisions(db: Session, task_id: str) -> list[OcrRevision]:
    return db.query(OcrRevision).filter(OcrRevision.task_id == task_id).order_by(OcrRevision.number).all()


def import_pages(db: Session, task_id: str, entries: list[dict], *, indexed: bool = False,
                 document_id: str | None = None) -> list[OcrRevision]:
    """Revision 1 (OCR) and a review copy from page entries; nothing when there are none.

    The copy is a draft, or, for a task that was indexed before revisions
    existed, the indexed revision: its pages
    are what the corpus holds.
    """
    if not entries or revisions(db, task_id):
        return revisions(db, task_id)
    ocr = OcrRevision(task_id=task_id, number=1, kind="ocr", status="locked")
    draft = OcrRevision(task_id=task_id, number=2, kind="review", status="indexed" if indexed else "draft",
                        document_id=document_id, parent_id=None)
    db.add_all([ocr, draft])
    db.flush()
    draft.parent_id = ocr.id
    for entry in entries:
        for revision in (ocr, draft):
            text = str(entry.get("text") or "")
            db.add(OcrPage(revision_id=revision.id, page_number=int(entry["page_number"]),
                           total_pages=int(entry.get("total_pages") or 0), method=str(entry.get("method") or "unknown"),
                           confidence=entry.get("confidence"), text=text, char_count=len(text), edited=False))
    db.flush()
    return [ocr, draft]


def reimport_pages(db: Session, task_id: str, entries: list[dict]) -> list[OcrRevision]:
    """import_pages for an OCR that just finished: revisions made earlier from a partial page file
    (a page opened while OCR ran) are replaced when nobody edited them; edited ones stay."""
    existing = revisions(db, task_id)
    if existing and entries:
        ids = [r.id for r in existing]
        edited = db.query(OcrPage).filter(OcrPage.revision_id.in_(ids), OcrPage.edited.is_(True)).first()
        pages = db.query(func.count()).select_from(OcrPage).filter(OcrPage.revision_id == existing[0].id).scalar()
        if edited is None and pages < len(entries):
            db.query(OcrPage).filter(OcrPage.revision_id.in_(ids)).delete(synchronize_session=False)
            db.query(OcrRevision).filter(OcrRevision.task_id == task_id).delete(synchronize_session=False)
            db.flush()
            db.expire_all()
    return import_pages(db, task_id, entries)


def by_status(db: Session, task_id: str, status: str) -> OcrRevision | None:
    return (db.query(OcrRevision).filter(OcrRevision.task_id == task_id, OcrRevision.status == status)
            .order_by(OcrRevision.number.desc()).first())


def current(db: Session, task_id: str) -> OcrRevision | None:
    """The draft, else the indexed revision, else the latest one."""
    return (by_status(db, task_id, "draft") or by_status(db, task_id, "indexed")
            or db.query(OcrRevision).filter(OcrRevision.task_id == task_id).order_by(OcrRevision.number.desc()).first())


def get(db: Session, task_id: str, revision_id: str | None) -> OcrRevision | None:
    if revision_id is None:
        return current(db, task_id)
    revision = db.get(OcrRevision, revision_id)
    return revision if revision is not None and revision.task_id == task_id else None


def pages(db: Session, revision: OcrRevision) -> list[dict]:
    rows = db.query(OcrPage).filter(OcrPage.revision_id == revision.id).order_by(OcrPage.page_number).all()
    return [_page_entry(row) for row in rows]


def page(db: Session, revision: OcrRevision, page_number: int) -> dict | None:
    row = db.get(OcrPage, (revision.id, page_number))
    return _page_entry(row) if row else None


def set_page_text(db: Session, revision: OcrRevision, page_number: int, text: str) -> dict | None:
    """Edit one page of a draft; "edited" compares with the OCR output."""
    if revision.status != "draft" or revision.kind != "review":
        raise RevisionLocked(revision.id)
    row = db.get(OcrPage, (revision.id, page_number))
    if row is None:
        return None
    ocr = by_number(db, revision.task_id, 1)
    original = db.get(OcrPage, (ocr.id, page_number)) if ocr else None
    row.text, row.char_count = text, len(text)
    row.edited = original is None or original.text != text
    revision.updated_at = datetime.utcnow()
    db.flush()
    return _page_entry(row)


def by_number(db: Session, task_id: str, number: int) -> OcrRevision | None:
    return db.query(OcrRevision).filter(OcrRevision.task_id == task_id, OcrRevision.number == number).first()


def new_draft(db: Session, task_id: str, from_revision_id: str | None = None) -> OcrRevision:
    """A draft copied from the given revision, else from the indexed (or latest) one."""
    if by_status(db, task_id, "draft"):
        raise DraftExists(task_id)
    source = get(db, task_id, from_revision_id)
    if source is None:
        raise LookupError(task_id)
    number = (db.query(func.max(OcrRevision.number)).filter(OcrRevision.task_id == task_id).scalar() or 0) + 1
    draft = OcrRevision(task_id=task_id, number=number, kind="review", status="draft", parent_id=source.id,
                        document_id=source.document_id)
    db.add(draft)
    db.flush()
    for row in db.query(OcrPage).filter(OcrPage.revision_id == source.id).all():
        db.add(OcrPage(revision_id=draft.id, page_number=row.page_number, total_pages=row.total_pages,
                       method=row.method, confidence=row.confidence, text=row.text, char_count=row.char_count,
                       edited=row.edited))
    db.flush()
    return draft


def discard_draft(db: Session, task_id: str) -> bool:
    """Drop the draft of a task that has an indexed revision; False when there is nothing to fall back on."""
    draft, indexed = by_status(db, task_id, "draft"), by_status(db, task_id, "indexed")
    if draft is None or indexed is None:
        return False
    db.query(OcrPage).filter(OcrPage.revision_id == draft.id).delete()
    db.delete(draft)
    db.flush()
    return True


def mark_indexed(db: Session, revision: OcrRevision, document_id: str | None) -> None:
    """The revision now in the corpus; the one indexed before it is locked."""
    for previous in db.query(OcrRevision).filter(OcrRevision.task_id == revision.task_id,
                                                 OcrRevision.status == "indexed").all():
        if previous.id != revision.id:
            previous.status = "locked"
    revision.status, revision.indexed_at, revision.document_id = "indexed", datetime.utcnow(), document_id
    db.flush()


def summary(db: Session, revision: OcrRevision | None) -> dict:
    """Page counts of a revision for the task list."""
    if revision is None:
        return {"total_pages": 0, "edited_pages": 0}
    total = db.query(func.count()).select_from(OcrPage).filter(OcrPage.revision_id == revision.id).scalar() or 0
    edited = (db.query(func.count()).select_from(OcrPage)
              .filter(OcrPage.revision_id == revision.id, OcrPage.edited.is_(True)).scalar() or 0)
    declared = db.query(func.max(OcrPage.total_pages)).filter(OcrPage.revision_id == revision.id).scalar() or 0
    return {"total_pages": max(total, declared), "edited_pages": edited}


def task_state(task: IngestionTask, draft: OcrRevision | None, indexed: OcrRevision | None, in_corpus: bool) -> str:
    """One label for the task list."""
    if task.status in {"pending", "parsing", "chunking", "embedding", "indexing"}:
        return "running"
    if task.status in {"failed", "cancelled"} and indexed is None:
        return task.status
    if indexed is not None or task.status == "completed":
        if not in_corpus:
            return "removed" if draft is None else "editing"
        return "editing" if draft is not None else "indexed"
    return "awaiting_review"

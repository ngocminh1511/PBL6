"""OCR revisions made from a partial page file are replaced when OCR ends."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.backend.app.models.database import Base, IngestionTask
from src.backend.app.services import ocr_revisions


def entries(count):
    return [{"page_number": n, "total_pages": count, "method": "ocr", "text": f"Trang {n}"} for n in range(1, count + 1)]


def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(IngestionTask(id="t", file_name="a.pdf", document_type="pdf", status="awaiting_review"))
    db.commit()
    return db


def page_count(db):
    return len(ocr_revisions.pages(db, ocr_revisions.current(db, "t")))


def test_partial_import_is_replaced_by_the_full_page_file():
    db = session()
    ocr_revisions.import_pages(db, "t", entries(1))  # a page opened while OCR ran
    db.commit()
    ocr_revisions.reimport_pages(db, "t", entries(26))
    db.commit()
    assert page_count(db) == 26
    assert [r.number for r in ocr_revisions.revisions(db, "t")] == [1, 2]


def test_edited_revisions_are_never_replaced():
    db = session()
    ocr_revisions.import_pages(db, "t", entries(1))
    draft = ocr_revisions.current(db, "t")
    ocr_revisions.set_page_text(db, draft, 1, "Đã sửa")
    db.commit()
    ocr_revisions.reimport_pages(db, "t", entries(26))
    db.commit()
    assert page_count(db) == 1


def test_cancel_stops_a_task_whose_worker_is_gone():
    """After a restart a 'parsing' task has no worker; cancelling must end it, not wait forever."""
    import threading
    from types import SimpleNamespace
    from src.backend.app.services.ingestion import IngestionService
    db = session()
    db.query(IngestionTask).filter(IngestionTask.id == "t").update({"status": "parsing"})
    db.commit()
    service = object.__new__(IngestionService)
    service._cancel_lock, service._cancel_events = threading.Lock(), {}
    service.database = SimpleNamespace(session=lambda: Session(db.get_bind()))
    assert service.cancel("t").status == "cancelled"

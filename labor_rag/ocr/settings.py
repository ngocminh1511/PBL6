"""OCR constants and operation-scoped, immutable runtime configuration."""
from contextlib import contextmanager
from contextvars import ContextVar

from labor_rag.settings import Settings

MIN_TEXT_CHARS = 50
SCAN_IMAGE_COVERAGE = 0.3
HEADER_FOOTER_FREQ_THRESHOLD = 0.5
DUPLICATE_PAGE_SIMILARITY = 0.95
CHUNK_MAX_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200
SEMANTIC_SIMILARITY_THRESHOLD = 0.5
SEMANTIC_MIN_CHUNK_CHARS = 100

_current = ContextVar("ocr_settings", default=None)
_FIELDS = {name: name for name in ("OCR_MODEL", "OCR_DEVICE", "OCR_DPI", "OCR_BEAMSEARCH", "HF_TOKEN")}
_FIELDS.update(SEMANTIC_CHUNKING="OCR_SEMANTIC_CHUNKING", SEMANTIC_MODEL="OCR_SEMANTIC_MODEL")


def __getattr__(name):
    if name in _FIELDS:
        return getattr(_current.get() or Settings(), _FIELDS[name])
    raise AttributeError(name)


@contextmanager
def use_settings(config=None):
    token = _current.set(config or _current.get() or Settings())
    try:
        yield
    finally:
        _current.reset(token)

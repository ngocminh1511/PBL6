"""Local, content-addressed file catalog; independent of any cloud credentials."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from labor_rag.config import ROOT_DIR

RAW_DIR = ROOT_DIR / "data/raw/appendix"
PROCESSED_DIR = ROOT_DIR / "data/processed/appendices_v1"
INTERIM_DIR = ROOT_DIR / "data/interim/appendix"
INVENTORY_DIR = ROOT_DIR / "docs/reports/appendix_inventory"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    os.replace(temporary, path)


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT_DIR).as_posix()


def local_path(value: str, roots: tuple[Path, ...] | None = None) -> Path:
    """Resolve catalog paths, never a user-supplied arbitrary filesystem path."""
    path = (ROOT_DIR / value).resolve()
    allowed = roots or (RAW_DIR, PROCESSED_DIR, INTERIM_DIR)
    if not any(path.is_relative_to(root.resolve()) for root in allowed):
        raise ValueError("File is outside the local appendix directories")
    return path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signature(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        return "doc"
    if data.startswith(b"PK\x03\x04"):
        return "zip"
    beginning = data[:500].lstrip().lower()
    if beginning.startswith((b"<html", b"<!doctype html", b"<body", b"<div", b"<table")):
        return "html"
    return None


def load_manifest(raw_dir: Path = RAW_DIR) -> dict:
    return read_json(raw_dir / "manifest.json", {"version": 1, "storage_backend": "local", "documents": {}, "artifacts": {}})


def valid_artifact(artifact: dict) -> bool:
    try:
        path = local_path(artifact["path"])
        return path.is_file() and sha256(path.read_bytes()) == artifact["sha256"]
    except (OSError, KeyError, ValueError):
        return False


def register_bytes(data: bytes, document_id: str, filename: str, source_url: str, *, raw_dir: Path = RAW_DIR) -> dict:
    digest = sha256(data)
    # Windows paths and remote path components are stripped before touching disk.
    name = Path(filename.replace("\\", "/")).name
    name = "".join(ch if ch not in '<>:"/\\|?*' and ord(ch) >= 32 else "_" for ch in name)
    if not name or name in {".", ".."}:
        raise ValueError("Invalid source filename")
    path = raw_dir / document_id / f"{digest[:16]}_{name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(data)
        os.replace(temporary, path)
    return {
        "artifact_id": f"sha256:{digest}", "sha256": digest, "file_name": name,
        "path": relative(path), "bytes": len(data), "format": signature(data) or path.suffix.lstrip("."),
        "source_url": source_url, "downloaded_at": now(), "storage_backend": "local",
    }

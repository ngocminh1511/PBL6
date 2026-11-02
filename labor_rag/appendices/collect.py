"""Collect public vbpl page data and its original attachments, with resumable local output."""
from __future__ import annotations

import argparse
import csv
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from labor_rag.ingest.chunk_schema import ascii_fold, make_document_id
from .catalog import INVENTORY_DIR, RAW_DIR, load_manifest, local_path, now, register_bytes, valid_artifact, write_json

PUBLIC_SITE = "https://vbpl.vn"
DOWNLOAD_API = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/minio/buckets/vbpl"
USER_AGENT = "Mozilla/5.0"


def document_number_id(target: dict) -> str:
    return make_document_id(target["document"])


def decode_flight(page: str) -> dict[str, object]:
    """Decode public Next.js data; T record lengths are UTF-8 BYTES, not characters."""
    decoder = json.JSONDecoder()
    parts = []
    for script in BeautifulSoup(page, "lxml").find_all("script"):
        source = script.get_text()
        for match in re.finditer(r"self\.__next_f\.push\(", source):
            try:
                row, _ = decoder.raw_decode(source[match.end():])
            except json.JSONDecodeError:
                continue
            if len(row) > 1 and row[0] == 1 and isinstance(row[1], str):
                parts.append(row[1])
    data = "".join(parts).encode("utf-8")
    records, cursor = {}, 0
    while cursor < len(data):
        if data[cursor:cursor+1] == b"\n":
            cursor += 1
            continue
        colon = data.find(b":", cursor)
        if colon < 0:
            break
        key = data[cursor:colon].decode("ascii", errors="ignore")
        if not re.fullmatch(r"[0-9a-f]+", key):
            break
        start = colon + 1
        if data[start:start+1] == b"T":
            comma = data.find(b",", start)
            size = int(data[start+1:comma], 16)
            end = comma + 1 + size
            if end > len(data):
                raise ValueError("Truncated public page data")
            records[key] = data[comma+1:end].decode("utf-8")
            cursor = end
        else:
            end = data.find(b"\n", start)
            if end < 0:
                end = len(data)
            line = data[start:end].decode("utf-8")
            try:
                records[key] = json.loads(line)
            except json.JSONDecodeError:
                pass  # import/preload records do not contain document metadata
            cursor = end + 1
    return records


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def public_document(page: str, item_id: str, expected_number: str) -> tuple[dict, str]:
    records = decode_flight(page)
    candidates = [v for record in records.values() for v in walk(record)
                  if isinstance(v, dict) and str(v.get("id")) == str(item_id) and "documentContent" in v]
    if not candidates:
        raise ValueError("Response has no matching document metadata (possibly homepage/challenge)")
    metadata = candidates[0]
    content = (metadata.get("documentContent") or {}).get("content") or ""
    if isinstance(content, str) and re.fullmatch(r"\$[0-9a-f]+", content):
        content = records.get(content[1:], "")
    if not isinstance(content, str):
        content = ""
    # The document header is checked separately from references to other laws.
    if make_document_id(metadata.get("docNum") or "") != make_document_id(expected_number):
        raise ValueError(f"Document number mismatch: expected {expected_number}")
    return metadata, content


def load_targets(inventory_dir: Path = INVENTORY_DIR) -> list[dict]:
    with (inventory_dir / "documents.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        match = re.search(r"ItemID=(\d+)", row.get("source_url", ""), re.I)
        row["item_id"] = match[1] if match else row.get("item_id", "")
        row["document_id"] = make_document_id(row["document"])
    overrides = inventory_dir / "source_overrides.csv"
    if overrides.exists():
        with overrides.open(encoding="utf-8-sig", newline="") as handle:
            by_id = {r["document_id"]: r for r in csv.DictReader(handle)}
        for row in rows:
            row.update({k: v for k, v in by_id.get(row["document_id"], {}).items() if v})
    supplements = inventory_dir / "supplemental_sources.csv"
    if supplements.exists():
        with supplements.open(encoding="utf-8-sig", newline="") as handle:
            rows.extend({**r, "document_id": make_document_id(r["document"]), "supplemental": True} for r in csv.DictReader(handle))
    return rows


class Collector:
    def __init__(self, raw_dir: Path = RAW_DIR, *, interval: float = 1.0, retries: int = 3):
        self.raw_dir, self.interval, self.retries = raw_dir, interval, retries
        self._lock, self._next_request = threading.Lock(), 0.0
        self._sessions = threading.local()
        path=INVENTORY_DIR/"alternative_sources.csv"
        self.alternatives={}
        if path.is_file():
            with path.open(encoding="utf-8-sig",newline="") as handle:
                for row in csv.DictReader(handle):
                    self.alternatives.setdefault(row["document_id"],[]).append(row)

    def get(self, url: str) -> requests.Response:
        if not hasattr(self._sessions, "session"):
            self._sessions.session = requests.Session()
            self._sessions.session.headers.update({"User-Agent": USER_AGENT})
        for attempt in range(self.retries):
            with self._lock:
                delay = max(0.0, self._next_request - time.monotonic())
                if delay:
                    time.sleep(delay)
                self._next_request = time.monotonic() + self.interval
            try:
                response = self._sessions.session.get(url, timeout=(15, 60))
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                if len(response.content) > 100 * 1024 * 1024:
                    raise ValueError("Source file exceeds the 100 MB collection limit")
                return response
            except requests.RequestException as exc:
                status = getattr(exc.response, "status_code", None)
                if status and status < 500 and status != 429:
                    raise
                if attempt + 1 == self.retries:
                    raise
                time.sleep(2 ** attempt)
        raise RuntimeError("Unreachable retry state")

    def one(self, target: dict, old: dict | None = None, *, refresh: bool = False) -> dict:
        old = old or {}
        if (not refresh and old.get("download_status") == "downloaded" and old.get("files")
                and old.get("item_id") == target.get("item_id")
                and make_document_id(old.get("metadata", {}).get("docNum", "")) == document_number_id(target)
                and all(any(f.get("landing_url")==a["landing_url"] for f in old["files"]) for a in self.alternatives.get(target["document_id"],[]))
                and all(valid_artifact(f) for f in old["files"])):
            return {**old, "cache_hit": True}
        number, document_id = target["document"], target["document_id"]
        result = {**target, "files": [], "errors": [], "cache_hit": False,
                  "download_status": "missing", "extraction_status": "pending", "review_status": "pending", "checked_at": now()}
        if not target.get("item_id"):
            result["errors"].append("No ItemID; add a source override")
            return result
        url = target.get("canonical_url") or f"{PUBLIC_SITE}/van-ban/chi-tiet/{target['item_id']}"
        try:
            response = self.get(url)
            metadata, content = public_document(response.text, target["item_id"], number)
            canonical = BeautifulSoup(response.text, "lxml").find("link", rel="canonical")
            result["canonical_url"] = canonical.get("href", response.url) if canonical else response.url
            result["metadata"] = metadata
            if content:
                artifact = register_bytes(content.encode("utf-8"), document_id, "vbpl_content.html", result["canonical_url"], raw_dir=self.raw_dir)
                artifact["role"] = "document_html"
                result["files"].append(artifact)
                result["content_artifact_id"] = artifact["artifact_id"]
            names = [metadata.get("documentContentFileName"), metadata.get("documentContentFileDocName")]
            names += [r.get("fileName") for r in metadata.get("documentRelatedList", [])
                      if r.get("relatedType") not in {"MARKDOWN"}]
            for name in dict.fromkeys(name for name in names if name):
                if not re.search(r"\.(pdf|docx?|html?|zip|txt)$", name, re.I):
                    continue
                old_file = next((f for f in old.get("files", []) if f["file_name"] == name and valid_artifact(f)), None)
                if old_file and not refresh:
                    result["files"].append(old_file)
                    continue
                download = f"{DOWNLOAD_API}/{quote(str(target['item_id']), safe='')}/{quote(name, safe='')}/download"
                try:
                    payload = self.get(download).content
                    from .catalog import signature
                    kind = signature(payload)
                    suffix = Path(name).suffix.lower()
                    if (suffix == ".pdf" and kind != "pdf") or (suffix == ".doc" and kind != "doc") or (suffix == ".docx" and kind != "zip"):
                        raise ValueError("Download is not the expected binary format")
                    if not kind and suffix not in {".txt"}:
                        raise ValueError("Unrecognized attachment format")
                    artifact = register_bytes(payload, document_id, name, download, raw_dir=self.raw_dir)
                    artifact["role"] = "original"
                    result["files"].append(artifact)
                except (requests.RequestException, ValueError) as exc:
                    result["errors"].append(f"{name}: {type(exc).__name__}: {str(exc)[:180]}")
            for source in self.alternatives.get(document_id,[]):
                try:
                    landing=self.get(source["landing_url"])
                    soup=BeautifulSoup(landing.text,"lxml")
                    titles=" ".join(t.get_text(" ",strip=True) for t in soup.find_all(["h1","title"]))
                    normalize=lambda s: re.sub(r"\s+","",ascii_fold(s).lower())
                    if normalize(number) not in normalize(titles):
                        raise ValueError("Alternative landing page has a different document number")
                    links=[(a["data-href"].rsplit("/",1)[-1],a["data-href"]) for a in soup.find_all(attrs={"data-href":True}) if re.search(r"\.(?:pdf|docx?)$",a["data-href"],re.I)]
                    links += [(a.get_text(strip=True),a["href"]) for a in soup.find_all("a",href=True) if re.search(r"\.(?:pdf|docx?)$",a.get_text(strip=True),re.I)]
                    if not links:
                        raise ValueError("Alternative page has no original attachment metadata")
                    for name,href in dict.fromkeys(links):
                        previous=next((f for f in old.get("files",[]) if f["file_name"]==name and valid_artifact(f)),None)
                        if previous and not refresh:
                            result["files"].append(previous)
                            continue
                        download=urljoin(landing.url,href)
                        payload=self.get(download).content
                        from .catalog import signature
                        if signature(payload) not in {"pdf","doc","zip"}:
                            raise ValueError("Alternative file has an invalid binary signature")
                        artifact=register_bytes(payload,document_id,name,download,raw_dir=self.raw_dir)
                        artifact.update(role="alternative_original",landing_url=source["landing_url"])
                        result["files"].append(artifact)
                except (requests.RequestException,ValueError) as exc:
                    result["errors"].append(f"Alternative source: {type(exc).__name__}: {str(exc)[:180]}")
            if result["files"]:
                result["download_status"] = "partial" if result["errors"] else "downloaded"
        except (requests.RequestException, ValueError) as exc:
            result["errors"].append(f"{type(exc).__name__}: {str(exc)[:240]}")
        return result

    def collect(self, targets: list[dict], *, refresh: bool = False, progress=print) -> dict:
        manifest = load_manifest(self.raw_dir)
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = {pool.submit(self.one, t, manifest["documents"].get(t["document_id"]), refresh=refresh): t for t in targets}
            for future in as_completed(jobs):
                result = future.result()
                for file in result.get("files", []):
                    existing = manifest["artifacts"].get(file["artifact_id"])
                    if existing and valid_artifact(existing):
                        file["path"] = existing["path"]
                        if existing.get("r2"):
                            file.update(storage_backend=existing.get("storage_backend","local"),r2=existing["r2"])
                    else:
                        manifest["artifacts"][file["artifact_id"]] = dict(file)
                    stored = manifest["artifacts"][file["artifact_id"]]
                    sources = stored.setdefault("sources", [])
                    origin = {"document_id": result["document_id"], "file_name": file["file_name"], "source_url": file["source_url"], "role": file["role"]}
                    if origin not in sources:
                        sources.append(origin)
                previous = manifest["documents"].get(result["document_id"])
                if previous and previous.get("content_artifact_id") != result.get("content_artifact_id"):
                    result["previous_versions"] = [*previous.get("previous_versions", []), {
                        "content_artifact_id": previous.get("content_artifact_id"), "files": previous.get("files", []),
                        "checked_at": previous.get("checked_at"),
                    }]
                manifest["documents"][result["document_id"]] = result
                backends={a.get("storage_backend","local") for a in manifest["artifacts"].values()}
                manifest["storage_backend"]=next(iter(backends)) if len(backends)==1 else "mixed" if backends else "local"
                manifest["updated_at"] = now()
                write_json(self.raw_dir / "manifest.json", manifest)
                if progress:
                    progress(f"{result['document']}: {result['download_status']} ({len(result['files'])} files, {len(result['errors'])} errors)")
        return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", action="append", help="Document ID or legal number; repeatable")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    targets = load_targets()
    if args.document:
        ids = {make_document_id(v) for v in args.document}
        targets = [t for t in targets if t["document_id"] in ids]
    if args.limit:
        targets = targets[:args.limit]
    if not targets:
        parser.error("No matching documents")
    Collector().collect(targets, refresh=args.refresh)


if __name__ == "__main__":
    main()

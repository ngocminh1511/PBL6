"""Versioned benchmarks: one frozen benchmark per data version (dataset_id).

A benchmark version is a test set frozen against one projection of the
ontology (data/processed/<dataset_id>/).  The manifest records the sha256 of
the files it was frozen on, so a run on changed data stops instead of mixing
results across versions (docs/BENCHMARK.md, section 3).

  labor_rag/evaluation/benchmarks/<dataset_id>/
    manifest.json             data hashes + one entry per frozen test set
    <testset>.jsonl           the questions; gold is keyed by mapc
    <testset>.gold.jsonl      every gold Dieu as it was when frozen (content_hash, ten, ...)
    <testset>.migration.json  only for a test set carried over from another version

Carrying a test set to a new version (--from) compares each gold Dieu's
content_hash: a question whose gold Dieu changed or disappeared is excluded
and listed for re-labelling, never kept silently.

Run from the repository root:

    python -m labor_rag.evaluation.benchmark_version freeze --dataset lao_dong_v5 --testset v1 \
        --questions labor_rag/evaluation/benchmark_questions.jsonl
    python -m labor_rag.evaluation.benchmark_version freeze --dataset lao_dong_v6 --testset v1 --from lao_dong_v5
    python -m labor_rag.evaluation.benchmark_version check --dataset lao_dong_v5
    python -m labor_rag.evaluation.benchmark_version list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from labor_rag.config import BENCHMARKS_DIR, PROCESSED_DIR, ROOT_DIR
from labor_rag.ingest.chunk_schema import content_hash

MANIFEST = "manifest.json"
# Files of data/processed/<dataset_id>/ a benchmark depends on.  Retrieval
# reads only chunks.jsonl, so only a change there (or in the questions) stops
# a run; the KG and ontology files are reported as warnings.
DATA_FILES = {"chunks": "chunks.jsonl", "kg_nodes": "kg_nodes.jsonl", "kg_edges": "kg_edges.jsonl"}
BLOCKING = {"chunks"}


class BenchmarkError(Exception):
    pass


def file_sha256(path: Path) -> str:
    """sha256 with CRLF read as LF, so a Windows checkout (autocrlf) hashes the same."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(path)


def default_collection_prefix(dataset_id: str) -> str:
    """lao_dong_v5 -> legal_ld_v5, the prefix embed_and_index uses for that projection."""
    if dataset_id.startswith("lao_dong_"):
        return "legal_ld_" + dataset_id.removeprefix("lao_dong_")
    return "legal_" + dataset_id


def data_fingerprint(dataset_dir: Path) -> dict[str, dict[str, str]]:
    """sha256 of the projection files, plus the TBox/ABox named in its ontology_manifest.json."""
    files: dict[str, dict[str, str]] = {}
    for key, name in DATA_FILES.items():
        path = dataset_dir / name
        if path.exists():
            files[key] = {"path": repo_relative(path), "sha256": file_sha256(path)}
    if "chunks" not in files:
        raise BenchmarkError(f"{dataset_dir / DATA_FILES['chunks']} not found")
    ontology_manifest = dataset_dir / "ontology_manifest.json"
    if ontology_manifest.exists():
        recorded = json.loads(ontology_manifest.read_text(encoding="utf-8"))
        for key in ("schema", "abox"):
            if recorded.get(key):
                path = ROOT_DIR / recorded[key]
                files[key] = {"path": recorded[key], "sha256": file_sha256(path) if path.exists() else "missing"}
    return files


def article_snapshot(chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One record per Dieu (mapc); the parts of a split Dieu share it.

    content_hash covers the Dieu body without the chunk header (chunk schema
    v5).  Chunks without it (v4) fall back to a hash of the joined text, so a
    v4 -> v5 carry-over reports every Dieu as changed: review it by hand.
    """
    articles: dict[str, dict[str, Any]] = {}
    texts: dict[str, list[str]] = {}
    for chunk in chunks:
        mapc = str(chunk.get("mapc") or "")
        if not mapc:
            continue
        texts.setdefault(mapc, []).append(str(chunk.get("text") or ""))
        record = articles.setdefault(
            mapc,
            {
                "mapc": mapc,
                "content_hash": chunk.get("content_hash"),
                "ten": chunk.get("ten"),
                "document_id": chunk.get("document_id"),
                "meta_dieu": chunk.get("meta_dieu"),
                "parts": 0,
            },
        )
        record["parts"] += 1
    for mapc, record in articles.items():
        if not record["content_hash"]:
            record["content_hash"] = content_hash("\n".join(texts[mapc]))
    return articles


def gold_mapcs(questions: list[dict[str, Any]]) -> list[str]:
    return sorted({str(mapc) for question in questions for mapc in question.get("relevance", {})})


def load_manifest(dataset_id: str, benchmarks_dir: Path = BENCHMARKS_DIR) -> dict[str, Any] | None:
    path = benchmarks_dir / dataset_id / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_manifest(manifest: dict[str, Any], benchmarks_dir: Path) -> None:
    folder = benchmarks_dir / manifest["dataset_id"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def carry_over(
    questions: list[dict[str, Any]],
    source_gold: dict[str, dict[str, Any]],
    target_articles: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep the questions whose every gold Dieu is unchanged in the target version."""
    status: dict[str, str] = {}
    for mapc, old in source_gold.items():
        new = target_articles.get(mapc)
        if new is None:
            status[mapc] = "missing"
        elif new["content_hash"] != old.get("content_hash"):
            status[mapc] = "changed"
        else:
            status[mapc] = "unchanged"
    kept, excluded = [], []
    for question in questions:
        bad = {mapc: status.get(mapc, "missing") for mapc in question["relevance"] if status.get(mapc) != "unchanged"}
        if bad:
            excluded.append({"id": question["id"], "gold": bad})
        else:
            kept.append(question)
    report = {
        "gold_status": {key: sum(1 for value in status.values() if value == key) for key in ("unchanged", "changed", "missing")},
        "changed_or_missing": {mapc: value for mapc, value in sorted(status.items()) if value != "unchanged"},
        "excluded_questions": excluded,
    }
    return kept, report


def freeze(
    dataset_id: str,
    testset: str,
    questions_path: Path | None = None,
    from_dataset: str | None = None,
    collection_prefix: str | None = None,
    force: bool = False,
    processed_dir: Path = PROCESSED_DIR,
    benchmarks_dir: Path = BENCHMARKS_DIR,
) -> dict[str, Any]:
    """Freeze one test set against data/processed/<dataset_id>; returns its manifest entry."""
    from labor_rag.evaluation.embedding_benchmark import validate_questions

    if (questions_path is None) == (from_dataset is None):
        raise BenchmarkError("Give exactly one of --questions or --from")
    dataset_dir = processed_dir / dataset_id
    fingerprint = data_fingerprint(dataset_dir)
    manifest = load_manifest(dataset_id, benchmarks_dir)
    if manifest is not None and manifest["data"]["chunks"]["sha256"] != fingerprint["chunks"]["sha256"]:
        if not force:
            raise BenchmarkError(
                f"{dataset_dir / DATA_FILES['chunks']} changed since benchmark {dataset_id} was frozen. "
                "Changed data is a new version: project it under a new dataset_id and freeze there "
                "(--from to carry the test sets over). --force re-freezes and drops every test set of this version."
            )
        manifest = None
    if manifest is None:
        manifest = {
            "dataset_id": dataset_id,
            "collection_prefix": collection_prefix or default_collection_prefix(dataset_id),
            "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data": fingerprint,
            "testsets": {},
        }
    elif testset in manifest["testsets"] and not force:
        raise BenchmarkError(f"Test set {testset!r} is already frozen for {dataset_id}; --force replaces it")

    chunks = read_jsonl(dataset_dir / DATA_FILES["chunks"])
    articles = article_snapshot(chunks)
    entry: dict[str, Any] = {"file": f"{testset}.jsonl", "gold_file": f"{testset}.gold.jsonl"}
    migration: dict[str, Any] | None = None
    if questions_path is not None:
        questions = read_jsonl(questions_path)
        entry["source"] = repo_relative(questions_path)
    else:
        source_manifest = load_manifest(from_dataset, benchmarks_dir)
        if source_manifest is None or testset not in source_manifest["testsets"]:
            raise BenchmarkError(f"No frozen test set {testset!r} in benchmark {from_dataset}")
        source_entry = source_manifest["testsets"][testset]
        source_folder = benchmarks_dir / from_dataset
        questions = read_jsonl(source_folder / source_entry["file"])
        source_gold = {row["mapc"]: row for row in read_jsonl(source_folder / source_entry["gold_file"])}
        questions, migration = carry_over(questions, source_gold, articles)
        source_chunks = processed_dir / from_dataset / DATA_FILES["chunks"]
        if source_chunks.exists():
            old_mapcs = {str(chunk.get("mapc")) for chunk in read_jsonl(source_chunks)}
            # Dieu that were never in the pools: a carried-over question may now
            # have an unlabelled relevant Dieu among them.
            migration["new_articles"] = sorted(set(articles) - old_mapcs)
        entry["source"] = f"{from_dataset}/{testset}"
        entry["migration_file"] = f"{testset}.migration.json"
        entry["excluded"] = [row["id"] for row in migration["excluded_questions"]]
        if not questions:
            raise BenchmarkError(f"Every question of {from_dataset}/{testset} has a changed gold Dieu; re-label them")

    errors = validate_questions(chunks, questions)
    if errors:
        raise BenchmarkError("Gold-label validation failed:\n- " + "\n- ".join(errors))

    folder = benchmarks_dir / dataset_id
    folder.mkdir(parents=True, exist_ok=True)
    write_jsonl(folder / entry["file"], questions)
    write_jsonl(folder / entry["gold_file"], [articles[mapc] for mapc in gold_mapcs(questions)])
    if migration is not None:
        migration = {"from": from_dataset, "to": dataset_id, "testset": testset, **migration}
        (folder / entry["migration_file"]).write_text(
            json.dumps(migration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    entry.update(
        {
            "sha256": file_sha256(folder / entry["file"]),
            "questions": len(questions),
            "gold_dieu": len(gold_mapcs(questions)),
            "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    manifest["testsets"][testset] = entry
    save_manifest(manifest, benchmarks_dir)
    return entry


def check(
    dataset_id: str,
    processed_dir: Path = PROCESSED_DIR,
    benchmarks_dir: Path = BENCHMARKS_DIR,
) -> tuple[list[str], list[str]]:
    """(errors, warnings) of a frozen benchmark against the files on disk."""
    manifest = load_manifest(dataset_id, benchmarks_dir)
    if manifest is None:
        return [f"No frozen benchmark for {dataset_id} in {benchmarks_dir}"], []
    errors: list[str] = []
    warnings: list[str] = []
    try:
        current = data_fingerprint(processed_dir / dataset_id)
    except BenchmarkError as exc:
        return [str(exc)], []
    for key, frozen in manifest["data"].items():
        now = current.get(key, {}).get("sha256", "missing")
        if now != frozen["sha256"]:
            message = f"{frozen['path']} changed since {dataset_id} was frozen"
            (errors if key in BLOCKING else warnings).append(message)
    folder = benchmarks_dir / dataset_id
    for name, entry in manifest["testsets"].items():
        path = folder / entry["file"]
        if not path.exists() or file_sha256(path) != entry["sha256"]:
            errors.append(f"{repo_relative(path)} was edited after freezing (test set {name!r})")
    return errors, warnings


def resolve(
    dataset_id: str,
    testset: str,
    processed_dir: Path = PROCESSED_DIR,
    benchmarks_dir: Path = BENCHMARKS_DIR,
) -> dict[str, Any]:
    """Paths and settings of one benchmark version; raises if it no longer matches the data."""
    errors, warnings = check(dataset_id, processed_dir, benchmarks_dir)
    if errors:
        raise BenchmarkError(f"Benchmark {dataset_id} does not match the data:\n- " + "\n- ".join(errors))
    manifest = load_manifest(dataset_id, benchmarks_dir)
    if testset not in manifest["testsets"]:
        known = ", ".join(sorted(manifest["testsets"])) or "none"
        raise BenchmarkError(f"No test set {testset!r} in benchmark {dataset_id} (frozen: {known})")
    entry = manifest["testsets"][testset]
    return {
        "dataset_id": dataset_id,
        "testset": testset,
        "chunks_path": processed_dir / dataset_id / DATA_FILES["chunks"],
        "questions_path": benchmarks_dir / dataset_id / entry["file"],
        "collection_prefix": manifest["collection_prefix"],
        "data": manifest["data"],
        "testset_entry": entry,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_freeze = sub.add_parser("freeze", help="freeze a test set against data/processed/<dataset>")
    p_freeze.add_argument("--dataset", required=True)
    p_freeze.add_argument("--testset", required=True, help="name of the test set, e.g. v1, v2")
    p_freeze.add_argument("--questions", type=Path, help="questions JSONL with relevance {mapc: grade}")
    p_freeze.add_argument("--from", dest="from_dataset", help="carry the same test set over from this benchmark")
    p_freeze.add_argument("--collection-prefix", help="Qdrant prefix; default legal_ld_<version> for lao_dong_<version>")
    p_freeze.add_argument("--force", action="store_true", help="replace a frozen test set (or re-freeze changed data)")
    p_check = sub.add_parser("check", help="compare a frozen benchmark with the files on disk")
    p_check.add_argument("--dataset", required=True)
    sub.add_parser("list", help="list frozen benchmarks")
    args = parser.parse_args(argv)

    try:
        if args.command == "freeze":
            entry = freeze(
                args.dataset, args.testset, args.questions, args.from_dataset, args.collection_prefix, args.force
            )
            print(f"Froze {args.dataset}/{args.testset}: {entry['questions']} questions, {entry['gold_dieu']} gold Dieu")
            if entry.get("excluded"):
                print(f"  {len(entry['excluded'])} questions excluded (gold Dieu changed): see {entry['migration_file']}")
            return 0
        if args.command == "check":
            errors, warnings = check(args.dataset)
            for message in warnings:
                print(f"WARN  {message}")
            for message in errors:
                print(f"ERROR {message}")
            if not errors:
                print(f"{args.dataset}: matches the data")
            return 1 if errors else 0
        for folder in sorted(path for path in BENCHMARKS_DIR.glob("*") if (path / MANIFEST).exists()):
            manifest = load_manifest(folder.name)
            sets = ", ".join(f"{name} ({entry['questions']} q)" for name, entry in manifest["testsets"].items())
            print(f"{folder.name}: {sets or 'no test set'}")
        return 0
    except BenchmarkError as exc:
        print(f"ERROR {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

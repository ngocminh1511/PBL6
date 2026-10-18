"""Unit tests for the retrieval metrics (embedding_benchmark) and the frozen
benchmark versions (benchmark_version).  No model, Qdrant or network: the
versions are built in a temporary folder.

Run from the repository root:
  python tests/test_benchmark.py
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from labor_rag.evaluation import benchmark_version as bv
from labor_rag.evaluation.embedding_benchmark import aggregate_metrics, calculate_query_metrics, validate_questions


def ranked(*mapcs: str) -> list[dict]:
    return [{"rank": rank, "mapc": mapc} for rank, mapc in enumerate(mapcs, start=1)]


def chunk(mapc: str, body: str, part: int | None = None) -> dict:
    chunk_id = f"doc:d{mapc}" + (f":p{part}" if part else "")
    return {"chunk_id": chunk_id, "mapc": mapc, "text": f"Điều {mapc}.\n{body}", "content_hash": bv.content_hash(body)}


def question(qid: str, relevance: dict) -> dict:
    return {"id": qid, "question": f"câu hỏi {qid}", "relevance": relevance}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


# ------------------------------------------------------------------ metrics


def test_hit_recall_multi_hit():
    row = calculate_query_metrics(ranked("x", "a", "y", "z", "w", "b"), {"a": 3, "b": 2})
    assert row["hit_at_1"] == 0 and row["hit_at_5"] == 1
    assert row["found_at_5"] == 1 and row["found_at_10"] == 2
    assert row["multi_hit_at_5"] == 0 and row["multi_hit_at_10"] == 1
    assert row["mrr_at_10"] == 0.5


def test_grade_one_is_context_not_relevant():
    # Grade 1 only gives context (GUIDELINES.md): it is not a hit at min_grade 2 ...
    row = calculate_query_metrics(ranked("c", "a"), {"a": 3, "c": 1})
    assert row["hit_at_1"] == 0 and row["n_relevant"] == 1 and row["mrr_at_10"] == 0.5
    # ... but it still earns nDCG gain.
    assert 0 < row["ndcg_at_10"] < 1
    assert calculate_query_metrics(ranked("c", "a"), {"a": 3, "c": 1}, min_grade=1)["hit_at_1"] == 1


def test_ndcg_perfect_and_miss():
    assert math.isclose(calculate_query_metrics(ranked("a", "b"), {"a": 3, "b": 2})["ndcg_at_10"], 1.0)
    assert calculate_query_metrics(ranked("x", "y"), {"a": 3})["ndcg_at_10"] == 0.0


def test_recall_is_micro_averaged():
    rows = [
        calculate_query_metrics(ranked("a"), {"a": 3}),  # 1 of 1
        calculate_query_metrics(ranked("b"), {"b": 3, "c": 3, "d": 3}),  # 1 of 3
    ]
    metrics = aggregate_metrics(rows, samples=0)
    assert metrics["Recall@5"]["value"] == 0.5  # (1 + 1) / (1 + 3), not mean(1, 1/3)
    assert metrics["HitRate@5"]["value"] == 1.0 and metrics["MultiHit@5"]["value"] == 0.5


def test_bootstrap_ci_brackets_value_and_is_reproducible():
    rows = [calculate_query_metrics(ranked("a" if i % 3 else "x"), {"a": 3}) for i in range(60)]
    first = aggregate_metrics(rows, samples=500)
    assert first == aggregate_metrics(rows, samples=500)
    hit = first["HitRate@1"]
    assert hit["ci_low"] < hit["value"] < hit["ci_high"]


def test_validation_rejects_unstable_and_weak_gold():
    chunks = [chunk("20.5.LQ.1", "a"), chunk("https://example.org/x#Article_dup2", "b")]
    errors = validate_questions(chunks, [question("q1", {"https://example.org/x#Article_dup2": 3})])
    assert any("no stable mapc" in error for error in errors)
    errors = validate_questions(chunks, [question("q2", {"20.5.LQ.1": 1})])
    assert any("grade >= 2" in error for error in errors)
    assert validate_questions(chunks, [question("q3", {"20.5.LQ.1": 2})]) == []


# ------------------------------------------------------------------ versions


def make_version(root: Path, dataset_id: str, chunks: list[dict]) -> None:
    write_jsonl(root / "processed" / dataset_id / "chunks.jsonl", chunks)


def test_freeze_check_and_resolve():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        processed, benchmarks = root / "processed", root / "benchmarks"
        make_version(root, "lao_dong_v5", [chunk("1", "a", 1), chunk("1", "a", 2), chunk("2", "b")])
        write_jsonl(root / "q.jsonl", [question("q1", {"1": 3}), question("q2", {"2": 2, "1": 1})])
        entry = bv.freeze("lao_dong_v5", "v1", root / "q.jsonl", processed_dir=processed, benchmarks_dir=benchmarks)
        assert entry["questions"] == 2 and entry["gold_dieu"] == 2
        gold = {row["mapc"]: row for row in bv.read_jsonl(benchmarks / "lao_dong_v5" / "v1.gold.jsonl")}
        assert gold["1"]["parts"] == 2
        resolved = bv.resolve("lao_dong_v5", "v1", processed, benchmarks)
        assert resolved["collection_prefix"] == "legal_ld_v5"
        assert bv.check("lao_dong_v5", processed, benchmarks) == ([], [])

        # A frozen test set is not overwritten by accident.
        try:
            bv.freeze("lao_dong_v5", "v1", root / "q.jsonl", processed_dir=processed, benchmarks_dir=benchmarks)
            raise AssertionError("re-freezing should need --force")
        except bv.BenchmarkError:
            pass

        # Editing the frozen questions or the chunks stops a run.
        questions_file = benchmarks / "lao_dong_v5" / "v1.jsonl"
        questions_file.write_text(questions_file.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        assert any("edited after freezing" in error for error in bv.check("lao_dong_v5", processed, benchmarks)[0])
        make_version(root, "lao_dong_v5", [chunk("1", "a changed"), chunk("2", "b")])
        errors, _ = bv.check("lao_dong_v5", processed, benchmarks)
        assert any("chunks.jsonl changed" in error for error in errors)
        try:
            bv.resolve("lao_dong_v5", "v1", processed, benchmarks)
            raise AssertionError("resolve should refuse changed data")
        except bv.BenchmarkError:
            pass


def test_crlf_checkout_hashes_the_same():
    with tempfile.TemporaryDirectory() as tmp:
        lf, crlf = Path(tmp) / "lf", Path(tmp) / "crlf"
        lf.write_bytes(b'{"a": 1}\n{"b": 2}\n')
        crlf.write_bytes(b'{"a": 1}\r\n{"b": 2}\r\n')
        assert bv.file_sha256(lf) == bv.file_sha256(crlf)


def test_carry_over_excludes_changed_gold():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        processed, benchmarks = root / "processed", root / "benchmarks"
        make_version(root, "lao_dong_v5", [chunk("1", "a"), chunk("2", "b"), chunk("3", "c")])
        write_jsonl(
            root / "q.jsonl",
            [question("q1", {"1": 3}), question("q2", {"2": 3}), question("q3", {"3": 3, "1": 1})],
        )
        bv.freeze("lao_dong_v5", "v1", root / "q.jsonl", processed_dir=processed, benchmarks_dir=benchmarks)
        # v6: Dieu 2 amended, Dieu 3 repealed, Dieu 4 new; Dieu 1 only gets a new header.
        v6 = [chunk("1", "a"), chunk("2", "b amended"), chunk("4", "d")]
        v6[0]["text"] = "Lao động > Luật số 1\nĐiều 1.\na"
        make_version(root, "lao_dong_v6", v6)
        entry = bv.freeze("lao_dong_v6", "v1", from_dataset="lao_dong_v5", processed_dir=processed, benchmarks_dir=benchmarks)
        assert entry["questions"] == 1 and sorted(entry["excluded"]) == ["q2", "q3"]
        migration = json.loads((benchmarks / "lao_dong_v6" / "v1.migration.json").read_text(encoding="utf-8"))
        assert migration["changed_or_missing"] == {"2": "changed", "3": "missing"}
        assert migration["new_articles"] == ["4"]
        assert bv.load_manifest("lao_dong_v6", benchmarks)["collection_prefix"] == "legal_ld_v6"


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)

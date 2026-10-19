"""Mine hard negatives and fine-tune BGE-M3 on a Modal (modal.com) GPU.

The local machine builds the data (notebooks/finetune/02 or
labor_rag.finetune.build_dataset); Modal only runs the GPU steps. Inputs are
uploaded to the Modal Volume "labor-rag-finetune", results are written there
and downloaded back:

    mine   queries_train.jsonl + chunks.jsonl + kg_edges.jsonl
           -> data/processed/finetune/merged/hard_negatives.jsonl
           (then run labor_rag.finetune.assemble_dataset locally)
    train  train.jsonl + val.jsonl + chunks.jsonl + benchmark_questions_v3.jsonl
           -> data/models/<run>/ and val / benchmark v3 scores, baseline vs fine-tuned

Like scripts/modal_embed.py this file sits outside the labor_rag package. The
image copies labor_rag/ without its venv, so the remote code is exactly
labor_rag.finetune.mine_negatives / train.py.

One-time setup (from the repo root, inside the venv):

    pip install modal
    modal setup                     # log in, writes ~/.modal.toml

Run (each command uploads the current local files first):

    modal run scripts/modal_finetune.py::mine
    python -m labor_rag.finetune.assemble_dataset
    modal run scripts/modal_finetune.py::train --epochs 3 --batch-size 32
    modal run scripts/modal_finetune.py::train --phase contrastive --run-name bge-m3-legal-c

Nothing runs between calls: you pay only for the GPU seconds of a run.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal

APP_NAME = "labor-rag-finetune"
GPU = "A10G"  # 24 GB: batch 32 / seq 512 with fp16. "L4" (24 GB) is similar, "A100" faster, "T4" (16 GB) needs batch 16
HF_CACHE = "/cache/huggingface"
DATA = "/data"

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "data" / "processed" / "finetune" / "merged"
LAO_DONG = ROOT / "data" / "processed" / "lao_dong_v5"
TEST_V3 = ROOT / "labor_rag" / "evaluation" / "benchmark_questions_v3.jsonl"
MODELS = ROOT / "data" / "models"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch>=2.4", "sentence-transformers>=3.1", "accelerate>=0.26", "datasets", "numpy")
    .env({"HF_HOME": HF_CACHE, "PYTHONPATH": "/root"})
    .add_local_dir(
        ROOT / "labor_rag",
        "/root/labor_rag",
        ignore=["venv", "venv/**", "**/__pycache__/**", "**/*.pyc", "evaluation/results/**", "app/**"],
    )
)
hf_cache = modal.Volume.from_name("labor-rag-hf-cache", create_if_missing=True)
data_vol = modal.Volume.from_name("labor-rag-finetune", create_if_missing=True)

app = modal.App(APP_NAME, image=image)
VOLUMES = {"/cache": hf_cache, DATA: data_vol}


@app.function(gpu=GPU, volumes=VOLUMES, timeout=60 * 60)
def mine_remote(model_name: str, top_k: int, neg_k: int, batch_size: int) -> int:
    from labor_rag.finetune.mine_negatives import (
        load_chunks,
        load_queries,
        load_reference_neighbours,
        mine_hard_negatives,
    )

    out = Path(DATA) / "output" / "hard_negatives.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)  # mine_hard_negatives resumes from an existing file
    chunks = load_chunks(Path(DATA) / "input" / "chunks.jsonl")
    mine_hard_negatives(
        queries=load_queries(Path(DATA) / "input" / "queries_train.jsonl"),
        chunks=chunks,
        model_name=model_name,
        output_path=out,
        top_k=top_k,
        neg_k=neg_k,
        batch_size=batch_size,
        device="cuda",
        neighbours=load_reference_neighbours(Path(DATA) / "input" / "kg_edges.jsonl", chunks),
    )
    hf_cache.commit()
    data_vol.commit()
    return sum(1 for _ in out.open(encoding="utf-8"))


def _ir_scores(model, records: list[dict], chunks: list[dict], name: str) -> dict[str, float]:
    import re

    from labor_rag.finetune.train import build_ir_evaluator

    evaluator = build_ir_evaluator(records, chunks)
    evaluator.name = name
    result = evaluator(model)
    keep = re.compile(r"cosine_(accuracy@(?:1|5|10)|mrr@10|ndcg@10)$")
    return {f"{name}/{m.group(1)}": round(float(v), 4) for k, v in result.items() if (m := keep.search(k))}


@app.function(gpu=GPU, volumes=VOLUMES, timeout=6 * 60 * 60)
def train_remote(cfg: dict) -> dict:
    from sentence_transformers import SentenceTransformer

    from labor_rag.finetune.train import load_chunks, load_val_records, train_model

    inp = Path(DATA) / "input"
    out = Path(DATA) / "models" / cfg["run_name"]
    chunks = load_chunks(inp / "chunks.jsonl")
    val = load_val_records(inp / "val.jsonl")
    test = load_val_records(inp / "test_v3.jsonl")

    def scores(model_path: str) -> dict[str, float]:
        model = SentenceTransformer(model_path, device="cuda")
        model.max_seq_length = cfg["max_seq_length"]
        return {**_ir_scores(model, val, chunks, "val"), **_ir_scores(model, test, chunks, "test_v3")}

    report: dict = {"config": cfg}
    if cfg["baseline"]:
        report["baseline"] = scores(cfg["model_name"])
    train_model(
        model_name=cfg["model_name"],
        output_dir=out,
        train_path=inp / "train.jsonl",
        val_path=inp / "val.jsonl",
        chunks_path=inp / "chunks.jsonl",
        epochs=cfg["epochs"],
        lr=cfg["lr"],
        batch_size=cfg["batch_size"],
        max_seq_length=cfg["max_seq_length"],
        phase=cfg["phase"],
        device="cuda",
        use_amp=True,
    )
    final = out if (out / "modules.json").exists() else out / "phase1"
    report["model_dir"] = str(final.relative_to(DATA))
    report["finetuned"] = scores(str(final))
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    hf_cache.commit()
    data_vol.commit()
    return report


def _upload(files: dict[str, Path]) -> None:
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise SystemExit(f"Thiếu file: {missing}. Chạy notebooks/finetune/02 (build_dataset, assemble_dataset) trước.")
    with data_vol.batch_upload(force=True) as batch:
        for remote, local in files.items():
            batch.put_file(str(local), f"/input/{remote}")
            print(f"  upload {local.relative_to(ROOT)} -> {APP_NAME}:/input/{remote}")


def _download(remote_dir: str, local_dir: Path) -> None:
    root = remote_dir.strip("/")
    for entry in data_vol.listdir(root, recursive=True):
        if entry.type != modal.volume.FileEntryType.FILE:
            continue
        target = local_dir / Path(entry.path.lstrip("/")).relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as f:
            for chunk in data_vol.read_file(entry.path):
                f.write(chunk)
    print(f"  download {remote_dir} -> {local_dir.relative_to(ROOT)}")


@app.local_entrypoint()
def mine(model: str = "BAAI/bge-m3", top_k: int = 30, neg_k: int = 5, batch_size: int = 64) -> None:
    _upload({
        "queries_train.jsonl": MERGED / "queries_train.jsonl",
        "chunks.jsonl": LAO_DONG / "chunks.jsonl",
        "kg_edges.jsonl": LAO_DONG / "kg_edges.jsonl",
    })
    n = mine_remote.remote(model, top_k, neg_k, batch_size)
    target = MERGED / "hard_negatives.jsonl"
    with target.open("wb") as f:
        for chunk in data_vol.read_file("/output/hard_negatives.jsonl"):
            f.write(chunk)
    print(f"{n} queries mined -> {target.relative_to(ROOT)}")
    print("Tiếp theo: python -m labor_rag.finetune.assemble_dataset, rồi modal run scripts/modal_finetune.py::train")


@app.local_entrypoint()
def train(
    model: str = "BAAI/bge-m3",
    run_name: str = "bge-m3-legal",
    epochs: int = 3,
    lr: float = 2e-5,
    batch_size: int = 32,
    max_seq_length: int = 512,
    phase: str = "both",
    baseline: bool = True,
    download: bool = True,
) -> None:
    train_path = MERGED / "train.jsonl"
    _upload({
        "train.jsonl": train_path,
        "val.jsonl": MERGED / "val.jsonl",
        "chunks.jsonl": LAO_DONG / "chunks.jsonl",
        "test_v3.jsonl": TEST_V3,
    })
    with train_path.open(encoding="utf-8") as f:
        with_negatives = sum(1 for line in f if json.loads(line).get("negatives"))
    if phase in ("both", "hard_neg") and with_negatives == 0:
        print("train.jsonl chưa có hard negative -> phase='contrastive' (chạy ::mine rồi assemble_dataset để có giai đoạn 2)")
        phase = "contrastive"

    cfg = {"model_name": model, "run_name": run_name, "epochs": epochs, "lr": lr, "batch_size": batch_size,
           "max_seq_length": max_seq_length, "phase": phase, "baseline": baseline}
    report = train_remote.remote(cfg)

    rows = sorted(set(report.get("baseline", {})) | set(report["finetuned"]))
    print(f"\n{'metric':28s} {'baseline':>9s} {'fine-tune':>9s}")
    for key in rows:
        base = report.get("baseline", {}).get(key)
        print(f"{key:28s} {base if base is not None else '-':>9} {report['finetuned'][key]:>9}")
    if download:
        local = MODELS / run_name
        _download(f"/{report['model_dir']}", local)
        (local / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Model: {local.relative_to(ROOT)}  (embedding lại: python -m labor_rag.ingest.embed_and_index "
              f"--model {local.relative_to(ROOT).as_posix()} --collection legal_ld_v5_bge_ft --recreate)")

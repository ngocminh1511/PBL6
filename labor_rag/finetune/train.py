"""Stage 5: Two-Phase Fine-Tuning for BGE-M3 on Vietnamese Labor Law Data.

Fine-tunes BAAI/bge-m3 using sentence-transformers:
- Phase 1 (Contrastive): MultipleNegativesRankingLoss with in-batch negatives on
  all positive pairs (synthetic queries + KG relations). Teaches legal semantic alignment.
- Phase 2 (Hard Negatives): MultipleNegativesRankingLoss or TripletLoss using mined hard negatives.
  Teaches the model to differentiate near-miss legal provisions.

Validation:
  InformationRetrievalEvaluator evaluates on the 30 validation benchmark questions
  against the full 1,481 chunks corpus during training.

Usage:
    python -m labor_rag.finetune.train --dry-run
    python -m labor_rag.finetune.train --epochs 3 --lr 2e-5 --batch-size 16
    python -m labor_rag.finetune.train --phase contrastive
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

import torch
from sentence_transformers import InputExample, SentenceTransformer

try:
    from sentence_transformers.sentence_transformer.evaluation import InformationRetrievalEvaluator
    from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss, TripletLoss
except ImportError:
    from sentence_transformers.evaluation import InformationRetrievalEvaluator
    from sentence_transformers.losses import MultipleNegativesRankingLoss, TripletLoss

from torch.utils.data import DataLoader

from labor_rag.config import DATA_DIR, FINETUNE_DIR, FINETUNE_MODELS_DIR, LAO_DONG_DIR

DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_TRAIN = FINETUNE_DIR / "train.jsonl"
DEFAULT_VAL = FINETUNE_DIR / "val.jsonl"
DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_OUTPUT = FINETUNE_MODELS_DIR


def load_train_samples(train_path: Path) -> list[dict[str, Any]]:
    samples = []
    with train_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def load_val_records(val_path: Path) -> list[dict[str, Any]]:
    records = []
    with val_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_chunks(chunks_path: Path) -> list[dict[str, Any]]:
    chunks = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def build_phase1_examples(train_samples: list[dict[str, Any]]) -> list[InputExample]:
    """Phase 1: (anchor, positive) pairs for in-batch negative contrastive learning."""
    examples = []
    for s in train_samples:
        anchor = s["anchor"].strip()
        positive = s["positive"].strip()
        if anchor and positive:
            examples.append(InputExample(guid=s.get("id"), texts=[anchor, positive]))
    return examples


def build_phase2_examples(train_samples: list[dict[str, Any]], mode: str = "mnrl") -> list[InputExample]:
    """Phase 2: samples with hard negatives.

    - For 'mnrl': InputExample(texts=[anchor, positive, neg_1, neg_2, ...])
    - For 'triplet': InputExample(texts=[anchor, positive, neg_1])
    """
    examples = []
    for s in train_samples:
        anchor = s["anchor"].strip()
        positive = s["positive"].strip()
        negs = [n.strip() for n in s.get("negatives", []) if n.strip()]

        if not anchor or not positive:
            continue

        if negs:
            if mode == "mnrl":
                # MNRL with hard negatives takes texts=[anchor, positive, *negs]
                examples.append(InputExample(guid=s.get("id"), texts=[anchor, positive] + negs[:4]))
            else:
                for neg in negs[:2]:
                    examples.append(InputExample(guid=s.get("id"), texts=[anchor, positive, neg]))
        else:
            # KG pairs or samples without hard negatives still contribute positive pairs
            if mode == "mnrl":
                examples.append(InputExample(guid=s.get("id"), texts=[anchor, positive]))

    return examples


def build_ir_evaluator(val_records: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> InformationRetrievalEvaluator:
    """Build sentence-transformers IR evaluator for validation set."""
    queries: dict[str, str] = {}
    for r in val_records:
        queries[r["id"]] = r["question"]

    corpus: dict[str, str] = {}
    mapc_to_chunks: dict[str, list[str]] = defaultdict(list)
    for c in chunks:
        cid = c["chunk_id"]
        corpus[cid] = c["text"]
        mapc = c.get("mapc")
        if mapc:
            mapc_to_chunks[mapc].append(cid)

    relevant_docs: dict[str, set[str]] = defaultdict(set)
    for r in val_records:
        qid = r["id"]
        # Prefer exact chunk_relevance if available
        if "chunk_relevance" in r and r["chunk_relevance"]:
            for cid, grade in r["chunk_relevance"].items():
                if float(grade) >= 1.0:
                    relevant_docs[qid].add(cid)
        else:
            for mapc, grade in r.get("relevance", {}).items():
                if float(grade) >= 1.0:
                    for cid in mapc_to_chunks.get(mapc, []):
                        relevant_docs[qid].add(cid)

    eval_name = "labor_benchmark_v2" if len(val_records) > 30 else "labor_benchmark_v1"
    return InformationRetrievalEvaluator(
        queries=queries,
        corpus=corpus,
        relevant_docs=relevant_docs,
        name=eval_name,
        main_score_function="cosine",
        mrr_at_k=[5, 10],
        ndcg_at_k=[5, 10],
        accuracy_at_k=[1, 5, 10],
        show_progress_bar=False,
    )

def extract_primary_score(result: Any) -> float:
    if isinstance(result, (int, float)):
        return float(result)
    if isinstance(result, dict):
        for key in ["cosine_ndcg@10", "cos_sim_ndcg@10", "ndcg@10", "cosine_mrr@10"]:
            if key in result:
                return float(result[key])
        for v in result.values():
            if isinstance(v, (int, float)):
                return float(v)
    return 0.0


def train_model(
    model_name: str = DEFAULT_MODEL,
    output_dir: Path = DEFAULT_OUTPUT,
    train_path: Path = DEFAULT_TRAIN,
    val_path: Path = DEFAULT_VAL,
    chunks_path: Path = DEFAULT_CHUNKS,
    epochs: int = 3,
    lr: float = 2e-5,
    batch_size: int = 16,
    warmup_ratio: float = 0.1,
    max_seq_length: int = 1024,
    phase: str = "both",
    phase2_loss_mode: str = "mnrl",
    device: str | None = None,
    dry_run: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading base model '{model_name}' on device '{device}'...")
    model = SentenceTransformer(model_name, device=device)
    model.max_seq_length = max_seq_length

    print(f"Loading training data from {train_path}...")
    train_samples = load_train_samples(train_path)
    print(f"Loaded {len(train_samples)} training samples.")

    print(f"Loading validation data from {val_path}...")
    val_records = load_val_records(val_path)
    chunks = load_chunks(chunks_path)
    print(f"Loaded {len(val_records)} validation questions and {len(chunks)} chunks.")

    evaluator = build_ir_evaluator(val_records, chunks)

    # Pre-training baseline evaluation
    print("\nRunning initial baseline evaluation on validation set...")
    baseline_raw = evaluator(model, output_path=str(output_dir))
    baseline_score = extract_primary_score(baseline_raw)
    print(f"Baseline validation score (nDCG@10): {baseline_score:.4f}\n")

    if dry_run:
        print("[DRY-RUN] Verification complete! Data loaded, model loaded, evaluator ran successfully.")
        return

    # PHASE 1: Contrastive Learning with in-batch negatives
    if phase in ("contrastive", "both"):
        print("=" * 60)
        print("STARTING PHASE 1: Contrastive Learning (MNRL with in-batch negatives)")
        print("=" * 60)
        phase1_examples = build_phase1_examples(train_samples)
        phase1_loader = DataLoader(phase1_examples, shuffle=True, batch_size=batch_size)
        phase1_loss = MultipleNegativesRankingLoss(model)

        total_steps = len(phase1_loader) * epochs
        warmup_steps = int(total_steps * warmup_ratio)
        eval_steps = max(10, len(phase1_loader) // 2)

        phase1_out = output_dir / "phase1"
        phase1_out.mkdir(parents=True, exist_ok=True)

        model.fit(
            train_objectives=[(phase1_loader, phase1_loss)],
            epochs=epochs,
            warmup_steps=warmup_steps,
            evaluator=evaluator,
            evaluation_steps=eval_steps,
            output_path=str(phase1_out),
            optimizer_params={"lr": lr},
            show_progress_bar=True,
        )
        print(f"Phase 1 complete! Saved to {phase1_out}")

    # PHASE 2: Hard Negative Fine-Tuning
    if phase in ("hard_neg", "both"):
        print("=" * 60)
        print(f"STARTING PHASE 2: Hard Negative Training (mode: {phase2_loss_mode})")
        print("=" * 60)

        # Load best checkpoint from Phase 1 if both was selected
        if phase == "both" and (output_dir / "phase1").exists():
            print(f"Loading Phase 1 model checkpoint from {output_dir / 'phase1'}...")
            model = SentenceTransformer(str(output_dir / "phase1"), device=device)
            model.max_seq_length = max_seq_length

        phase2_examples = build_phase2_examples(train_samples, mode=phase2_loss_mode)
        has_negs_count = sum(1 for s in train_samples if s.get("negatives"))

        if has_negs_count == 0:
            print("[WARN] No hard negatives found in training data. Skipping Phase 2 or running with positive pairs.")
            if phase == "hard_neg":
                print("Aborting Phase 2 because no hard negatives are present.")
                return

        phase2_loader = DataLoader(phase2_examples, shuffle=True, batch_size=batch_size)
        if phase2_loss_mode == "triplet":
            phase2_loss = TripletLoss(model)
        else:
            phase2_loss = MultipleNegativesRankingLoss(model)

        phase2_epochs = max(1, epochs // 2)
        total_steps = len(phase2_loader) * phase2_epochs
        warmup_steps = int(total_steps * warmup_ratio)
        eval_steps = max(10, len(phase2_loader) // 2)

        model.fit(
            train_objectives=[(phase2_loader, phase2_loss)],
            epochs=phase2_epochs,
            warmup_steps=warmup_steps,
            evaluator=evaluator,
            evaluation_steps=eval_steps,
            output_path=str(output_dir),
            optimizer_params={"lr": lr / 2},  # lower learning rate for fine adjustments
            show_progress_bar=True,
        )
        print(f"Phase 2 complete! Final fine-tuned model saved to {output_dir}")

    # Final evaluation
    print("\n" + "=" * 60)
    print("FINAL EVALUATION:")
    final_raw = evaluator(model)
    final_score = extract_primary_score(final_raw)
    print(f"Baseline validation score (nDCG@10): {baseline_score:.4f}")
    print(f"Final validation score (nDCG@10):    {final_score:.4f}")
    diff = final_score - baseline_score
    print(f"Delta:                              {'+' if diff >= 0 else ''}{diff:.4f}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 5: Fine-tune BGE-M3 model on Vietnamese labor law")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Base model name or path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output directory for fine-tuned model")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN, help="Path to train.jsonl")
    parser.add_argument("--val", type=Path, default=DEFAULT_VAL, help="Path to val.jsonl")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Path to chunks.jsonl")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=16, help="Training batch size")
    parser.add_argument("--warmup-ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument("--max-seq-length", type=int, default=1024, help="Maximum sequence length")
    parser.add_argument("--phase", choices=["contrastive", "hard_neg", "both"], default="both", help="Training phase")
    parser.add_argument("--loss-phase2", choices=["mnrl", "triplet"], default="mnrl", help="Loss for Phase 2")
    parser.add_argument("--device", type=str, default=None, help="Device (cpu or cuda)")
    parser.add_argument("--dry-run", action="store_true", help="Validate setup and test evaluator without full training")
    args = parser.parse_args()

    train_model(
        model_name=args.model,
        output_dir=args.output,
        train_path=args.train,
        val_path=args.val,
        chunks_path=args.chunks,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        warmup_ratio=args.warmup_ratio,
        max_seq_length=args.max_seq_length,
        phase=args.phase,
        phase2_loss_mode=args.loss_phase2,
        device=args.device,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

"""Embed texts on a Modal (modal.com) GPU instead of the local machine.

Modal only computes the vectors and sends them back; the caller
(labor_rag.ingest.embed_and_index --backend modal) upserts them into whatever
Qdrant QDRANT_URL points to, local docker or Qdrant Cloud. No Qdrant/Neo4j
credentials ever go to Modal.

This file sits outside the labor_rag package on purpose: Modal uploads the
package that contains the app, and labor_rag/ holds a full venv.

One-time setup (from the repo root, inside the venv):

    pip install modal
    modal setup                         # log in, writes ~/.modal.toml
    modal deploy scripts/modal_embed.py # redeploy after editing this file

Smoke test (embeds two sentences on the GPU, prints the dimension):

    modal run scripts/modal_embed.py --model BAAI/bge-m3

A deployed app scales to zero: you pay only for the seconds a GPU runs.
Model weights are cached in the Modal Volume "labor-rag-hf-cache".
"""
from pathlib import Path

import modal

APP_NAME = "labor-rag-embed"
GPU = "T4"  # 16 GB; "L4" or "A10G" are faster, "T4" is the cheapest
HF_CACHE = "/cache/huggingface"

BATCHING_PY = Path(__file__).resolve().parents[1] / "labor_rag" / "ingest" / "batching.py"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch>=2.4", "sentence-transformers>=3.1", "numpy")
    .env({"HF_HOME": HF_CACHE})
    # batching.py has no labor_rag imports, so it is shipped as a top-level module.
    .add_local_file(BATCHING_PY, "/root/batching.py")
)
hf_cache = modal.Volume.from_name("labor-rag-hf-cache", create_if_missing=True)

app = modal.App(APP_NAME, image=image)


@app.cls(gpu=GPU, volumes={"/cache": hf_cache}, timeout=30 * 60, scaledown_window=120)
class Embedder:
    model_name: str = modal.parameter()

    @modal.enter()
    def load(self) -> None:
        import os
        from sentence_transformers import SentenceTransformer

        model_path = self.model_name
        if "bge-m3-legal-vietnamese" in self.model_name or self.model_name in ("finetuned", "custom"):
            model_path = "/cache/bge-m3-finetuned"
        elif not os.path.exists(model_path) and os.path.exists(f"/cache/{model_path}"):
            model_path = f"/cache/{model_path}"

        print(f"Loading SentenceTransformer from: {model_path} on cuda...")
        self.model = SentenceTransformer(model_path, device="cuda")
        hf_cache.commit()  # keep downloaded weights for the next cold start

    @modal.method()
    def embed(self, texts: list[str], max_batch_tokens: int, batch_size: int) -> dict:
        """Return {"dim": int, "vectors": float32 bytes, row i = texts[i]}."""
        import numpy as np
        from batching import length_batches

        model = self.model
        dim = model.get_sentence_embedding_dimension()
        out = np.zeros((len(texts), dim), dtype=np.float32)
        batches = length_batches(texts, model.tokenizer, model.max_seq_length, max_batch_tokens, batch_size)
        done = 0
        for batch_ids in batches:
            out[batch_ids] = model.encode(
                [texts[idx] for idx in batch_ids],
                batch_size=len(batch_ids),
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            done += len(batch_ids)
            print(f"  embedded {done}/{len(texts)} (batch of {len(batch_ids)})")
        return {"dim": dim, "vectors": out.tobytes()}


@app.local_entrypoint()
def smoke_test(model: str = "bkai-foundation-models/vietnamese-bi-encoder") -> None:
    result = Embedder(model_name=model).embed.remote(
        ["Người lao động được nghỉ phép năm.", "Hợp đồng lao động"], 8192, 64
    )
    print(f"{model}: dim={result['dim']}, {len(result['vectors'])} bytes")

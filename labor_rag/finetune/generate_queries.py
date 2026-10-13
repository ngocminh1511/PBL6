"""Stage 1: Synthetic Query Generation for BGE-M3 Fine-tuning.

Generates realistic Vietnamese legal queries for each text chunk using Gemini Flash (or
configured LLM provider). Queries simulate various real-world user intent styles:
- tinh_huong: Real-life scenario / situation faced by employee or employer
- doi_thuong: Conversational, everyday wording without complex legal jargon
- truc_tiep: Direct inquiry about legal rules, conditions, deadlines, rights
- tu_khoa: Short keyword query style

Includes:
- Robust rate-limiting & exponential/header-based backoff for Gemini Free Tier (5 RPM).
- Multi-chunk prompt batching (--batch-chunks) to generate 2-3x more data per API call.
- Automatic resumption: skips previously processed chunks.
- Validation mode (--validate-only).

Output JSONL schema:
    {
        "query_id": "sq_<safe_chunk_id>_<idx>",
        "query": "...",
        "chunk_id": "...",
        "mapc": "...",
        "style": "...",
        "source": "synthetic"
    }

Usage:
    python -m labor_rag.finetune.generate_queries
    python -m labor_rag.finetune.generate_queries --batch-chunks 3 --delay 12.5
    python -m labor_rag.finetune.generate_queries --validate-only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

from dotenv import load_dotenv

from labor_rag.config import FINETUNE_DIR, LAO_DONG_DIR
from labor_rag.generation.llm_client import complete

load_dotenv()

DEFAULT_CHUNKS = LAO_DONG_DIR / "chunks.jsonl"
DEFAULT_OUTPUT = FINETUNE_DIR / "synthetic_queries.jsonl"

QUERY_STYLES = {
    "tinh_huong": "Tình huống thực tế ở ngôi thứ nhất ('Tôi...', 'Công ty tôi...'), 1-2 câu ngắn mô tả hoàn cảnh cụ thể cần giải quyết.",
    "doi_thuong": "Cách hỏi đời thường, dân dã, tự nhiên, không dùng từ ngữ pháp lý hàn lâm.",
    "truc_tiep": "Hỏi thẳng vào quy định, điều kiện, quyền hạn, thời hạn, mức hưởng hoặc nghĩa vụ.",
    "tu_khoa": "Tìm kiếm ngắn gọn theo dạng từ khóa hoặc cụm từ tìm kiếm (3-7 từ).",
}

SYSTEM_PROMPT = """Bạn là chuyên gia pháp luật lao động Việt Nam.
Nhiệm vụ: từ nội dung của điều khoản pháp luật, hãy tạo ra các câu hỏi tìm kiếm bằng tiếng Việt mà người dùng (người lao động hoặc doanh nghiệp) có thể hỏi, và đoạn văn bản đó là căn cứ trả lời đúng.

Yêu cầu nghiêm ngặt:
1. Câu hỏi phải hoàn toàn tự nhiên, đa dạng phong cách.
2. KHÔNG chép lại nguyên văn tiêu đề Điều luật.
3. Câu hỏi phải trả lời được dựa trên thông tin trong văn bản đã cho.
4. Trả về DUY NHẤT một mảng JSON (không kèm văn bản giải thích nào khác), mỗi phần tử có định dạng:
[
  {"chunk_id": "id của chunk", "query": "câu hỏi", "style": "tinh_huong | doi_thuong | truc_tiep | tu_khoa"}
]
"""

SINGLE_PROMPT_TEMPLATE = """Văn bản pháp luật [ID: {chunk_id}]:
---
{text}
---

Hãy tạo {num_queries} câu hỏi tìm kiếm cho văn bản trên với các phong cách sau:
{styles_desc}

Trả về mảng JSON theo format:
[
  {{"chunk_id": "{chunk_id}", "query": "...", "style": "..."}}
]"""

BATCH_PROMPT_TEMPLATE = """Hãy tạo các câu hỏi tìm kiếm cho từng đoạn văn bản pháp luật sau (mỗi văn bản tạo {num_queries} câu hỏi đa dạng phong cách):
{chunks_formatted}

Phong cách yêu cầu:
{styles_desc}

Trả về DUY NHẤT một mảng JSON với đầy đủ "chunk_id", "query", "style" cho tất cả các đoạn văn bản:
[
  {{"chunk_id": "...", "query": "...", "style": "..."}}
]"""


def format_styles_desc(styles: list[str]) -> str:
    lines = []
    for s in styles:
        desc = QUERY_STYLES.get(s, "")
        lines.append(f"- {s}: {desc}")
    return "\n".join(lines)


def parse_llm_json(raw_text: str) -> list[dict[str, Any]]:
    """Extract and parse JSON array from LLM response."""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*(\[\s*\{.*?\}\s*\])\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            text = text[bracket_start : bracket_end + 1]

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict) and item.get("query")]
    except Exception:
        pass
    return []


def extract_retry_delay(error_msg: str, default_delay: float = 14.0) -> float:
    """Extract recommended retry delay from API error message."""
    m = re.search(r"retry in (\d+(?:\.\d+)?)s", error_msg, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 1.5
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", error_msg, re.IGNORECASE)
    if m:
        return float(m.group(1)) + 1.5
    return default_delay


def generate_queries_for_chunks_batch(
    chunks: list[dict[str, Any]],
    num_queries: int = 4,
    max_retries: int = 6,
) -> list[dict[str, Any]]:
    """Call LLM for a batch of chunks with intelligent rate-limit backoff."""
    styles = list(QUERY_STYLES.keys())[:num_queries]
    styles_desc = format_styles_desc(styles)

    if len(chunks) == 1:
        c = chunks[0]
        user_prompt = SINGLE_PROMPT_TEMPLATE.format(
            chunk_id=c["chunk_id"],
            text=c["text"],
            num_queries=num_queries,
            styles_desc=styles_desc,
        )
    else:
        chunk_blocks = []
        for i, c in enumerate(chunks, 1):
            chunk_blocks.append(f"\n--- Đoạn {i} [ID: {c['chunk_id']}] ---\n{c['text']}")
        user_prompt = BATCH_PROMPT_TEMPLATE.format(
            chunks_formatted="\n".join(chunk_blocks),
            num_queries=num_queries,
            styles_desc=styles_desc,
        )

    chunk_map = {c["chunk_id"]: c for c in chunks}
    default_cid = chunks[0]["chunk_id"]

    for attempt in range(max_retries):
        try:
            resp_text = complete(system=SYSTEM_PROMPT, user=user_prompt, max_tokens=2048)
            parsed = parse_llm_json(resp_text)
            if parsed:
                results = []
                # Group by chunk_id
                idx_by_chunk: dict[str, int] = Counter()
                for item in parsed:
                    query_text = item.get("query", "").strip()
                    style = item.get("style", "truc_tiep").strip()
                    cid = item.get("chunk_id", default_cid).strip()
                    if cid not in chunk_map:
                        cid = default_cid
                    matched_chunk = chunk_map[cid]

                    if query_text:
                        idx_by_chunk[cid] += 1
                        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", cid)
                        results.append(
                            {
                                "query_id": f"sq_{safe_id}_{idx_by_chunk[cid]}",
                                "query": query_text,
                                "chunk_id": cid,
                                "mapc": matched_chunk.get("mapc", ""),
                                "style": style,
                                "source": "synthetic",
                            }
                        )
                return results
        except Exception as e:
            err_str = str(e)
            is_rate_limit = any(code in err_str for code in ("429", "RESOURCE_EXHAUSTED", "quota", "503", "UNAVAILABLE"))
            if is_rate_limit:
                wait_sec = extract_retry_delay(err_str, default_delay=14.0 * (1.2**attempt))
                print(f"  [429 Quota] Rate limited. Waiting {wait_sec:.1f}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait_sec)
            else:
                if attempt < max_retries - 1:
                    wait_sec = 2.0 * (2**attempt)
                    print(f"  [Error] {err_str[:80]}... Waiting {wait_sec:.1f}s ({attempt + 1}/{max_retries})...")
                    time.sleep(wait_sec)
                else:
                    cids = [c["chunk_id"] for c in chunks]
                    print(f"[WARN] Failed generating queries for {cids}: {err_str}", file=sys.stderr)
    return []


def run_generate_queries(
    chunks_path: Path = DEFAULT_CHUNKS,
    output_path: Path = DEFAULT_OUTPUT,
    num_queries: int = 4,
    batch_chunks: int = 1,
    max_chunks: int | None = None,
    delay: float = 12.5,
) -> None:
    """Run generation pipeline with resumption support and rate limiting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing progress
    seen_chunk_ids: set[str] = set()
    existing_count = 0
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        record = json.loads(line)
                        seen_chunk_ids.add(record["chunk_id"])
                        existing_count += 1
                    except Exception:
                        pass
        print(f"Resuming: found {existing_count} existing queries for {len(seen_chunk_ids)} chunks.")

    # Read chunks
    chunks: list[dict[str, Any]] = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    to_process = [c for c in chunks if c["chunk_id"] not in seen_chunk_ids]
    if max_chunks is not None:
        to_process = to_process[:max_chunks]

    print(
        f"Total chunks: {len(chunks)} | Done: {len(seen_chunk_ids)} | "
        f"To process: {len(to_process)} | Batch size: {batch_chunks} | Delay: {delay}s"
    )
    if not to_process:
        print("All chunks already processed.")
        return

    new_queries_count = 0
    start_time = time.time()

    with output_path.open("a", encoding="utf-8") as out_f:
        # Group into batches of batch_chunks
        for b_start in range(0, len(to_process), batch_chunks):
            batch = to_process[b_start : b_start + batch_chunks]

            t_req = time.time()
            generated = generate_queries_for_chunks_batch(
                chunks=batch,
                num_queries=num_queries,
            )

            for q in generated:
                out_f.write(json.dumps(q, ensure_ascii=False) + "\n")
                new_queries_count += 1
            out_f.flush()

            done_chunks = min(b_start + len(batch), len(to_process))
            cids_str = ", ".join(c["chunk_id"] for c in batch)
            elapsed = time.time() - start_time
            chunks_per_sec = done_chunks / elapsed if elapsed > 0 else 0.01
            remaining_chunks = len(to_process) - done_chunks
            eta_min = (remaining_chunks / chunks_per_sec) / 60 if chunks_per_sec > 0 else 0

            print(
                f"[{done_chunks}/{len(to_process)}] Processed ({cids_str}) -> "
                f"+{len(generated)} queries (total new: {new_queries_count}, ETA: {eta_min:.1f}m)"
            )

            # Enforce delay between requests to stay within rate limits (e.g. 5 RPM = 12s)
            req_duration = time.time() - t_req
            if delay > 0 and b_start + batch_chunks < len(to_process):
                sleep_need = max(0.0, delay - req_duration)
                if sleep_need > 0:
                    time.sleep(sleep_need)

    print(f"Generation complete! Total new queries written: {new_queries_count}. Output: {output_path}")


def validate_queries(output_path: Path = DEFAULT_OUTPUT) -> bool:
    """Validate generated synthetic queries file."""
    if not output_path.exists():
        print(f"[FAIL] Output file does not exist: {output_path}")
        return False

    records: list[dict[str, Any]] = []
    with output_path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                records.append(rec)
            except Exception as e:
                print(f"[FAIL] Line {idx} invalid JSON: {e}")
                return False

    if not records:
        print(f"[FAIL] Output file is empty: {output_path}")
        return False

    required_fields = {"query_id", "query", "chunk_id", "style"}
    styles_counter = Counter()
    chunk_counter = Counter()

    for idx, rec in enumerate(records, 1):
        missing = required_fields - set(rec.keys())
        if missing:
            print(f"[FAIL] Record #{idx} missing fields: {missing}")
            return False
        if not rec["query"].strip():
            print(f"[FAIL] Record #{idx} has empty query")
            return False
        styles_counter[rec["style"]] += 1
        chunk_counter[rec["chunk_id"]] += 1

    print("\n--- Synthetic Queries Validation ---")
    print(f"Total queries: {len(records)}")
    print(f"Unique chunks covered: {len(chunk_counter)}")
    print(f"Avg queries per chunk: {len(records) / len(chunk_counter):.2f}")
    print("Style distribution:")
    for style, count in styles_counter.most_common():
        pct = (count / len(records)) * 100
        print(f"  - {style}: {count} ({pct:.1f}%)")
    print("Sample query:")
    print(json.dumps(records[0], ensure_ascii=False, indent=2))
    print("[PASS] Synthetic queries file is valid!")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1: Generate synthetic queries via LLM")
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS, help="Path to chunks.jsonl")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to output synthetic_queries.jsonl")
    parser.add_argument("--num-queries", type=int, default=4, help="Number of queries per chunk")
    parser.add_argument(
        "--batch-chunks",
        type=int,
        default=2,
        help="Number of chunks grouped into each LLM prompt (e.g. 2 or 3 to multiply speed under RPM limit)",
    )
    parser.add_argument("--max-chunks", type=int, default=None, help="Limit number of chunks to process")
    parser.add_argument(
        "--delay",
        type=float,
        default=12.5,
        help="Minimum seconds between requests (default 12.5s for Free Tier 5 RPM; set 0.5s on paid tier)",
    )
    parser.add_argument("--validate-only", action="store_true", help="Validate output file only")
    args = parser.parse_args()

    if args.validate_only:
        valid = validate_queries(args.output)
        sys.exit(0 if valid else 1)

    run_generate_queries(
        chunks_path=args.chunks,
        output_path=args.output,
        num_queries=args.num_queries,
        batch_chunks=args.batch_chunks,
        max_chunks=args.max_chunks,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()

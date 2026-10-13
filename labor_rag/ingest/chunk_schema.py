"""Chunk schema v5 (docs/structural_jsonl.md): ids, text and splitting.

Shared by every chunk producer (Phap dien via ontology_to_jsonl, PDF/OCR later)
so the same Dieu of the same document always gets the same chunk_id.
Pure Python; only TokenCounter pulls in transformers, and only when built.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
import uuid
from typing import Callable

EMBEDDING_TOKENIZER = "BAAI/bge-m3"
MAX_TOKENS = 1024
OVERLAP_TOKENS = 64
# Joining pieces with "\n" and the special tokens make the real count a few
# tokens above the sum of the parts.
JOIN_MARGIN = 8

SO_HIEU_RE = re.compile(r"^\d+[a-z]?/\d{4}/[\w-]+$", re.IGNORECASE)
HEADING_NUMBER_RE = re.compile(r"^(?:Phần|Chương|Mục|Tiểu mục)\s+([^.\s]+)", re.IGNORECASE)
KHOAN_RE = re.compile(r"^(\d+[a-zđ]?)\.\s")
DIEM_RE = re.compile(r"^([a-zđ]\d*)\)\s")
SENTENCE_RE = re.compile(r"(?<=[.;:!?])\s+")

Counter = Callable[[str], int]


# ----------------------------------------------------------------------- ids


def ascii_fold(value: str) -> str:
    # "Ð" (U+00D0, Icelandic eth) is a common OCR stand-in for "Đ".
    value = value.replace("Ð", "Đ").replace("ð", "đ").replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def is_so_hieu(so_hieu: str) -> bool:
    """'45/2019/QH14', '145/2020/NĐ-CP', '40/2021/QĐ-TTg'."""
    return bool(SO_HIEU_RE.match(re.sub(r"\s+", "", unicodedata.normalize("NFC", so_hieu or "").replace("Ð", "Đ"))))


def make_document_id(so_hieu: str) -> str:
    """'45/2019/QH14' -> '45-2019-qh14'; '145/2020/NĐ-CP' -> '145-2020-nd-cp'."""
    s = ascii_fold(unicodedata.normalize("NFC", so_hieu.strip()).lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def article_key(meta_dieu: str) -> str:
    """'1' -> 'd1', '4a' -> 'd4a', '35đ' -> 'd35dd' ('35đ' follows '35d', so it must not fold to 'd')."""
    value = unicodedata.normalize("NFC", str(meta_dieu)).strip().lower().replace("đ", "dd")
    return "d" + re.sub(r"[^a-z0-9]+", "", ascii_fold(value))


def make_chunk_id(document_id: str, meta_dieu: str, part: int | None = None) -> str:
    chunk_id = f"{document_id}:{article_key(meta_dieu)}"
    return f"{chunk_id}:p{part}" if part else chunk_id


def point_id(chunk_id: str) -> str:
    """Qdrant point id: stable across runs and independent of row order."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def article_id(chunk_id: str) -> str:
    """Key shared by every part of one Dieu: '45-2019-qh14:d35:p2' -> '45-2019-qh14:d35'."""
    return chunk_id.split(":p", 1)[0]


def part_number(chunk_id: str) -> int:
    """'...:d35:p2' -> 2; 0 for a Dieu that was not split."""
    _, _, part = chunk_id.partition(":p")
    return int(part) if part.isdigit() else 0


def join_parts(texts: list[str]) -> str:
    """Rebuild a split Dieu from its parts in order: every part after the first
    repeats the header and lead lines (drop the lines it shares with the start
    of the first part) and, when a khoan was cut by diem, that khoan's lead line."""
    first = texts[0].split("\n")
    joined = list(first)
    for text in texts[1:]:
        lines = text.split("\n")
        shared = 0
        while shared < min(len(lines), len(first)) and lines[shared] == first[shared]:
            shared += 1
        rest = lines[shared:]
        last_khoan = next((line for line in reversed(joined) if KHOAN_RE.match(line.strip())), None)
        if rest and rest[0] == last_khoan:
            rest = rest[1:]
        # Sentence-split parts start with the overlap from the previous part.
        overlap = next((k for k in range(min(len(rest), len(joined)), 0, -1) if rest[:k] == joined[-k:]), 0)
        joined += rest[overlap:]
    return "\n".join(joined)


def content_hash(body: str) -> str:
    """Detects a changed Dieu between two loads without comparing whole texts."""
    normalized = " ".join(unicodedata.normalize("NFC", body or "").split())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def heading_number(heading: str | None) -> str | None:
    """'Chương I. NHỮNG QUY ĐỊNH CHUNG' -> 'I'; 'Mục 4. ...' -> '4'."""
    match = HEADING_NUMBER_RE.match((heading or "").strip())
    return match.group(1) if match else None


def citation(chunk: dict) -> str:
    """'Điều 35 khoản 4-5 Nghị định số 145/2020/NĐ-CP'."""
    parts = [f"Điều {chunk.get('meta_dieu')}" if chunk.get("meta_dieu") else None]
    if chunk.get("meta_khoan"):
        parts.append(f"khoản {chunk['meta_khoan']}")
    parts.append(chunk.get("meta_de_muc"))
    return " ".join(part for part in parts if part)


# ---------------------------------------------------------------------- text


def build_header(
    context: str | None,
    meta_dieu: str | None,
    ten: str | None,
    variant: str = "full",
) -> str:
    """Build the chunk header.

    Variants:
      - "full" / "B" (default): {context}\\nĐiều {meta_dieu}. {ten} (TH2: Đầy đủ ngữ cảnh)
      - "minimal" / "A": Điều {meta_dieu}. {ten} (TH1: Chỉ Điều n. Tên + nội dung)
    """
    title = f"Điều {meta_dieu}. {ten}" if meta_dieu else (ten or "")
    if variant in ("minimal", "A", "th1", "TH1"):
        return nfc(title)
    return nfc("\n".join(part for part in [context, title] if part))


def nfc(text: str) -> str:
    # OCR can return combining diacritics, which bge-m3 tokenizes differently.
    return unicodedata.normalize("NFC", text or "")


class TokenCounter:
    """Counts tokens with the embedding model's tokenizer (bge-m3)."""

    def __init__(self, model: str = EMBEDDING_TOKENIZER) -> None:
        from transformers import AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model)

    def __call__(self, text: str) -> int:
        return len(self.tokenizer(text, add_special_tokens=True, verbose=False)["input_ids"])


# ----------------------------------------------------------------- splitting


def split_article(header: str, body: str, count: Counter, max_tokens: int = MAX_TOKENS) -> list[tuple[str, str | None]]:
    """[(text, meta_khoan)] for one Dieu; a single element with meta_khoan None
    when the whole Dieu fits (spec section 5)."""
    header, body = nfc(header).strip(), nfc(body).strip()
    whole = "\n".join(part for part in [header, body] if part)
    if count(whole) <= max_tokens:
        return [(whole, None)]

    lead, clauses = split_clauses(body)
    budget = max_tokens - count(header) - (count(lead) if lead else 0) - JOIN_MARGIN
    if budget <= OVERLAP_TOKENS:
        raise ValueError(f"header + lead leave only {budget} tokens: {header[:80]!r}")

    units: list[tuple[str | None, str]] = []
    for label, text in clauses:
        if count(text) <= budget:
            units.append((label, text))
        else:
            units += [(label, piece) for piece in split_clause(text, budget, count)]

    parts = balanced_pack(units, budget, count)
    if len(parts) == 1:
        return [("\n".join(part for part in [header, lead, join_units(parts[0])] if part), None)]
    return [
        ("\n".join(part for part in [header, lead, join_units(part_units)] if part), khoan_range(part_units))
        for part_units in parts
    ]


def join_units(units: list[tuple[str | None, str]]) -> str:
    """Pieces of one khoan that land in the same part keep its lead line once."""
    lines: list[str] = []
    previous_label, khoan_lead = None, None
    for label, text in units:
        unit_lines = text.split("\n")
        if label is not None and label == previous_label and unit_lines[0] == khoan_lead:
            unit_lines = unit_lines[1:]
        else:
            khoan_lead = unit_lines[0]
        previous_label = label
        lines += unit_lines
    return "\n".join(lines)


def split_clauses(body: str) -> tuple[str, list[tuple[str | None, str]]]:
    """(lead, [(khoan number, khoan text)]). Without numbered khoan the whole
    body becomes one unlabeled unit and the lead is empty."""
    lead_lines: list[str] = []
    clauses: list[tuple[str | None, list[str]]] = []
    for line in body.split("\n"):
        match = KHOAN_RE.match(line.strip())
        if match:
            clauses.append((match.group(1), [line]))
        elif clauses:
            clauses[-1][1].append(line)
        else:
            lead_lines.append(line)
    if not clauses:
        return "", [(None, body)]
    return "\n".join(lead_lines).strip(), [(label, "\n".join(lines).strip()) for label, lines in clauses]


def split_clause(text: str, budget: int, count: Counter) -> list[str]:
    """A khoan longer than the budget: cut by diem, repeating the khoan's own
    lead line in every piece; diem (or a khoan without diem) still too long
    are cut by sentence."""
    lines = text.split("\n")
    intro_lines: list[str] = []
    points: list[list[str]] = []
    for line in lines:
        if DIEM_RE.match(line.strip()):
            points.append([line])
        elif points:
            points[-1].append(line)
        else:
            intro_lines.append(line)
    if not points:
        return split_sentences(text, budget, count)

    intro = "\n".join(intro_lines).strip()
    point_budget = budget - (count(intro) if intro else 0) - JOIN_MARGIN
    if point_budget <= OVERLAP_TOKENS:
        return split_sentences(text, budget, count)
    pieces: list[str] = []
    for point in ("\n".join(p).strip() for p in points):
        pieces += [point] if count(point) <= point_budget else split_sentences(point, point_budget, count)
    packed = balanced_pack([(None, piece) for piece in pieces], point_budget, count)
    return ["\n".join(part for part in [intro, *(piece for _, piece in group)] if part) for group in packed]


def split_sentences(text: str, budget: int, count: Counter) -> list[str]:
    """Last resort (appendices, tables, one huge diem): pack sentences up to
    the budget, starting each piece with ~OVERLAP_TOKENS of the previous one."""
    # (sentence, separator after it): line breaks survive, which keeps tables
    # in appendices readable.
    sentences: list[tuple[str, str]] = []
    for line in text.strip().split("\n"):
        parts = [piece for s in SENTENCE_RE.split(line) if s for piece in split_words(s, budget, count)]
        sentences += [(part, " ") for part in parts[:-1]] + [(part, "\n") for part in parts[-1:]]

    def render(group: list[tuple[str, str]]) -> str:
        return "".join(sentence + separator for sentence, separator in group).strip()

    pieces: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for sentence in sentences:
        if current and count(render([*current, sentence])) > budget:
            pieces.append(current)
            overlap: list[tuple[str, str]] = []
            for previous in reversed(current):
                if count(render([previous, *overlap])) > OVERLAP_TOKENS:
                    break
                overlap.insert(0, previous)
            current = overlap if count(render([*overlap, sentence])) <= budget else []
        current.append(sentence)
    if current:
        pieces.append(current)
    return [render(piece) for piece in pieces]


def split_words(sentence: str, budget: int, count: Counter) -> list[str]:
    if count(sentence) <= budget:
        return [sentence]
    words, pieces, current = sentence.split(), [], []
    for word in words:
        if current and count(" ".join([*current, word])) > budget:
            pieces.append(" ".join(current))
            current = []
        current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def balanced_pack(units: list[tuple[str | None, str]], budget: int, count: Counter) -> list[list[tuple[str | None, str]]]:
    """Group consecutive units into k = ceil(total / budget) parts of about
    total / k tokens each, so the last part is not a few dozen tokens; a part
    never exceeds the budget, so k can grow by one or two."""
    sizes = [count(text) + 1 for _, text in units]
    total = sum(sizes)
    target = total / max(1, math.ceil(total / budget))
    parts: list[list[tuple[str | None, str]]] = []
    current: list[tuple[str | None, str]] = []
    used = 0
    for unit, size in zip(units, sizes):
        # Start a new part when this unit does not fit, or when the current part
        # is already closer to the target without it than with it.
        if current and (used + size > budget or abs(used - target) < abs(used + size - target)):
            parts.append(current)
            current, used = [], 0
        current.append(unit)
        used += size
    if current:
        parts.append(current)
    return parts


def khoan_range(units: list[tuple[str | None, str]]) -> str | None:
    labels = [label for label, _ in units if label]
    if not labels:
        return None
    return labels[0] if labels[0] == labels[-1] else f"{labels[0]}-{labels[-1]}"

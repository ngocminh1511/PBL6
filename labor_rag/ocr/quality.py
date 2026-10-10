"""OCR quality metrics.

Heuristic (no ground truth): share of valid Vietnamese words, garbage
consonant runs, mojibake, sentence endings and punctuation noise, combined
into a 0-100 score. Useful to warn a user that a photo is too blurry.
With a reference text: character and word error rates (CER / WER).
"""
from __future__ import annotations

import re

_VN_LOWER = (
    "aăâbcdđeêfghijklmnoôơpqrstuưvwxyz"
    "áàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩị"
    "óòỏõọốồổỗộớờởỡợúùủũụứừửữự"
    "ýỳỷỹỵ"
)
_VN_CHARS = set(_VN_LOWER) | set(_VN_LOWER.upper()) | set("0123456789")
_WORD_STRIP = ".,;:!?()[]{}\"'-–—…/\\"

# Four or more consonants in a row never occur in Vietnamese.
_GARBAGE = re.compile(r"[bcdfghjklmnpqrstvwxz]{4,}", re.IGNORECASE)
_MOJIBAKE = [
    re.compile(r"[\x80-\x9f]"),  # C1 control characters
    re.compile(r"Ã[\x80-\xbf]"),  # UTF-8 decoded as Latin-1
    re.compile(r"â€[™œ\x9c\x9d]"),  # Windows-1252 mojibake
    re.compile("�"),  # replacement character
    re.compile(r"Ä[\x83\x91\x90\x82\xa3]"),  # Vietnamese mojibake
]
_STRUCTURE_LINE = re.compile(r"^(Điều|Chương|Mục|Phần)\s+")


def vietnamese_word_ratio(text: str) -> float:
    words = text.split()
    if not words:
        return 0.0
    valid = sum(1 for w in words if all(ch in _VN_CHARS for ch in w.strip(_WORD_STRIP)))
    return valid / len(words)


def sentence_completeness(text: str) -> float:
    """Share of lines that end like a sentence, or are a heading."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return 0.0
    complete = sum(
        1 for line in lines
        if line[-1] in '.;:!?)"]' or line.isupper() or _STRUCTURE_LINE.match(line)
    )
    return complete / len(lines)


def punctuation_noise(text: str) -> int:
    orphan = len(re.findall(r"(?<!\S)[.,:;!?](?!\S)", text))
    repeated = len(re.findall(r"([.,:;!?])\1{2,}", text))
    mid_word_dots = len(re.findall(r"[a-zà-ỹ]\.[a-zà-ỹ]", text.replace("...", " "), re.IGNORECASE))
    return orphan + repeated + mid_word_dots


def _edit_distance(ref: list, hyp: list) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = prev[j - 1] if r == h else 1 + min(prev[j], cur[j - 1], prev[j - 1])
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    if not reference:
        return 1.0 if hypothesis else 0.0
    return _edit_distance(list(reference), list(hypothesis)) / len(reference)


def wer(reference: str, hypothesis: str) -> float:
    ref = reference.split()
    if not ref:
        return 1.0 if hypothesis.split() else 0.0
    return _edit_distance(ref, hypothesis.split()) / len(ref)


def quality_report(text: str, ground_truth: str | None = None) -> dict:
    vwr = vietnamese_word_ratio(text)
    garbage = len(_GARBAGE.findall(text))
    mojibake = sum(len(p.findall(text)) for p in _MOJIBAKE)
    completeness = sentence_completeness(text)
    noise = punctuation_noise(text)

    score = (
        min(100.0, vwr * 100)
        - min(30, garbage * 5)
        - min(30, mojibake * 10)
        + completeness * 20
        - min(10, noise)
    )
    report = {
        "chars": len(text),
        "words": len(text.split()),
        "vietnamese_word_ratio": round(vwr, 4),
        "garbage_sequences": garbage,
        "mojibake": mojibake,
        "sentence_completeness": round(completeness, 4),
        "punctuation_noise": noise,
        "heuristic_score": round(max(0.0, min(100.0, score)), 1),
    }
    if ground_truth is not None:
        report["cer"] = round(cer(ground_truth, text), 4)
        report["wer"] = round(wer(ground_truth, text), 4)
    return report

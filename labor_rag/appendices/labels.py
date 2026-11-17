"""Appendix identifiers shared by ingestion, citation checks and inventory CLI."""
import re


def canonical_label(value: str) -> str:
    """Unify Arabic/Roman numbering (01 / I), retaining a suffix such as Ib."""
    value = value.strip()
    if value[0].isdigit():
        match = re.fullmatch(r"(\d+)([abAB]?)", value)
        return str(int(match[1])) + match[2].lower()
    suffix = value[-1].lower() if value[-1].lower() in "ab" else ""
    roman = value[:-1] if suffix else value
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total, previous = 0, 0
    for ch in reversed(roman.upper()):
        current = values[ch]
        total += -current if current < previous else current
        previous = max(previous, current)
    return str(total) + suffix

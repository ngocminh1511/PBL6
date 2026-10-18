"""Read what an amending document changes (docs/structural_jsonl.md, section 10).

An amending Dieu ("Điều 1. Sửa đổi, bổ sung một số điều của Nghị định số
145/2020/NĐ-CP") lists one change per khoan:

    1. Sửa đổi, bổ sung khoản 2 Điều 35 như sau: ...
    2. Bổ sung Điều 35a vào sau Điều 35 như sau: ...
    3. Bãi bỏ điểm b khoản 3 Điều 10.
    4. Thay thế cụm từ "..." bằng cụm từ "..." tại khoản 1 Điều 5.

parse_targets() turns the lead of each khoan (the part before "như sau",
since the quoted new text cites other Dieu) into Target records; the target
document is the one named there, else the one in the Dieu title.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from labor_rag.ingest.chunk_schema import article_id, make_chunk_id, make_document_id, nfc

# Phrase -> action, in the order entries are written.
ACTIONS = {
    "sửa đổi": "sua_doi",
    "bổ sung": "bo_sung",
    "bãi bỏ": "bai_bo",
    "thay thế cụm từ": "thay_cum_tu",
    "thay cụm từ": "thay_cum_tu",
}
ACTION_ORDER = ["sua_doi", "bo_sung", "bai_bo", "thay_cum_tu"]

AMENDING_TITLE_RE = re.compile(r"^\s*(?:sửa đổi|bổ sung|bãi bỏ|thay thế cụm từ|thay cụm từ)", re.IGNORECASE)
KINDS = r"Bộ luật|Luật|Pháp lệnh|Nghị quyết|Nghị định|Thông tư liên tịch|Thông tư|Quyết định"
DOCUMENT_RE = re.compile(rf"(?:{KINDS})\s+(?:số\s+)?(\d+[a-z]?/\d{{4}}/[\w-]*\w)", re.IGNORECASE)
# "điểm a khoản 2 Điều 35", "khoản 1, khoản 2 Điều 5", "các khoản 1, 2 và 3 Điều 5", "Điều 35a".
TARGET_RE = re.compile(
    r"(?P<scope>(?:(?:các\s+)?(?:điểm|khoản)\s+[\wđ]+(?:\s*(?:,|và)\s*(?:(?:điểm|khoản)\s+)?[\wđ]+)*\s+)*)"
    r"Điều\s+(?P<dieu>\d+[a-zđ]?)\b"
)
INSERTED_AFTER_RE = re.compile(r"vào\s+(?:sau|trước)\s+Điều\s+(\d+[a-zđ]?)\b")
QUOTE_RE = re.compile(r"[\"“”].*?[\"“”]", re.DOTALL)


class Target(NamedTuple):
    article: str  # '<document_id>:d<N>' as in amends / amended_by
    document_id: str
    dieu: str
    scope: str | None  # "khoản 2", "điểm b khoản 3"; None for the whole Dieu
    actions: list[str]


def actions_in(text: str) -> list[str]:
    """'Sửa đổi, bổ sung ...' -> ['sua_doi', 'bo_sung']."""
    lowered = nfc(text).lower()
    found = {action for phrase, action in ACTIONS.items() if phrase in lowered}
    return [action for action in ACTION_ORDER if action in found]


def is_amending(title: str) -> bool:
    return bool(AMENDING_TITLE_RE.match(nfc(title)))


def document_in(text: str) -> str | None:
    """document_id of the first document number named in the text."""
    match = DOCUMENT_RE.search(nfc(text))
    return make_document_id(match.group(1)) if match else None


def lead(text: str) -> str:
    """The instruction, without the new text: up to "như sau", and with
    quoted phrases dropped ("thay cụm từ "Điều 5" bằng ...")."""
    text = re.split(r"\bnhư\s+sau\b", nfc(text), maxsplit=1)[0]
    return QUOTE_RE.sub(" ", text)


def parse_targets(text: str, default_document_id: str | None) -> list[Target]:
    """The Dieu changed by one khoan of an amending Dieu."""
    instruction = lead(text)
    actions = actions_in(instruction)
    if not actions:
        return []
    document_id = document_in(instruction) or default_document_id
    if not document_id:
        return []
    inserted_after = INSERTED_AFTER_RE.search(instruction)
    if inserted_after and "bo_sung" in actions:
        # "Bổ sung Điều 35a vào sau Điều 35": no chunk has Dieu 35a yet, so
        # the new Dieu hangs off the one it follows.
        new = TARGET_RE.search(instruction[: inserted_after.start()])
        scope = f"Điều {new['dieu']}" if new else None
        dieu = inserted_after.group(1)
        return [Target(make_chunk_id(document_id, dieu), document_id, dieu, scope, actions)]
    targets = []
    for match in TARGET_RE.finditer(instruction):
        scope = re.sub(r"\s+", " ", match["scope"]).strip() or None
        target = Target(make_chunk_id(document_id, match["dieu"]), document_id, match["dieu"], scope, actions)
        if target not in targets:
            targets.append(target)
    return targets


def amends_entries(targets: list[Target], date: str | None) -> list[dict]:
    """Payload entries of the amending chunk, one per (target, action)."""
    return [
        {"target": t.article, "scope": t.scope, "action": action, "date": date} for t in targets for action in t.actions
    ]


def amended_by_updates(chunks: list[dict]) -> dict[str, list[dict]]:
    """{amended Dieu: amended_by entries} from the amends of amending chunks."""
    updates: dict[str, list[dict]] = {}
    for chunk in chunks:
        for entry in chunk.get("amends") or []:
            by = {"by": article_id(chunk["chunk_id"]), "scope": entry["scope"], "action": entry["action"], "date": entry["date"]}
            updates.setdefault(entry["target"], [])
            if by not in updates[entry["target"]]:
                updates[entry["target"]].append(by)
    return updates


def merge_amended_by(existing: list[dict], new: list[dict]) -> list[dict]:
    """existing + new, one entry per (by, scope, action): a reload of the
    amending document replaces its own entries."""
    keys = {(entry["by"], entry["scope"], entry["action"]) for entry in new}
    kept = [entry for entry in existing if (entry["by"], entry["scope"], entry["action"]) not in keys]
    return kept + new

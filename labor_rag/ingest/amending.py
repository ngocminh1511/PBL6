"""Read what a newly loaded document changes in the others (docs/structural_jsonl.md, section 10).

An amending Dieu ("Điều 1. Sửa đổi, bổ sung một số điều của Nghị định số
145/2020/NĐ-CP") lists one change per khoan:

    1. Sửa đổi, bổ sung khoản 2 Điều 35 như sau: ...
    2. Bổ sung Điều 35a vào sau Điều 35 như sau: ...
    3. Bãi bỏ điểm b khoản 3 Điều 10.
    4. Thay thế cụm từ "..." bằng cụm từ "..." tại khoản 1 Điều 5.

parse_targets() turns the lead of each khoan (the part before "như sau",
since the quoted new text cites other Dieu) into Target records; the target
document is the one named there, else the one in the Dieu title.
replaced_documents() reads "... thay thế / hết hiệu lực ..." in the effect
Dieu. pdf_abox writes both into the PDF's ABox; the graph, not the chunk
payload, holds them.
"""
from __future__ import annotations

import re
from typing import NamedTuple

from labor_rag.ingest.chunk_schema import make_chunk_id, make_document_id, nfc

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
DOCUMENT_RE = re.compile(rf"(?P<kind>{KINDS})\s+(?:số\s+)?(?P<number>\d+[a-z]?/\d{{4}}/[\w-]*\w)", re.IGNORECASE)
# "điểm a khoản 2 Điều 35", "khoản 1, khoản 2 Điều 5", "các khoản 1, 2 và 3 Điều 5", "Điều 35a".
TARGET_RE = re.compile(
    r"(?P<scope>(?:(?:các\s+)?(?:điểm|khoản)\s+[\wđ]+(?:\s*(?:,|và)\s*(?:(?:điểm|khoản)\s+)?[\wđ]+)*\s+)*)"
    r"Điều\s+(?P<dieu>\d+[a-zđ]?)\b"
)
INSERTED_AFTER_RE = re.compile(r"vào\s+(?:sau|trước)\s+Điều\s+(\d+[a-zđ]?)\b")
QUOTE_RE = re.compile(r"[\"“”].*?[\"“”]", re.DOTALL)


class DocumentRef(NamedTuple):
    """A document named in the text: 'Nghị định' + '145/2020/NĐ-CP'."""

    kind: str
    number: str

    @property
    def document_id(self) -> str:
        return make_document_id(self.number)


class Target(NamedTuple):
    document: DocumentRef
    dieu: str
    scope: str | None  # "khoản 2", "điểm b khoản 3"; None for the whole Dieu
    actions: list[str]

    @property
    def article(self) -> str:
        """'<document_id>:d<N>', the chunk key of the amended Dieu."""
        return make_chunk_id(self.document.document_id, self.dieu)


def actions_in(text: str) -> list[str]:
    """'Sửa đổi, bổ sung ...' -> ['sua_doi', 'bo_sung']."""
    lowered = nfc(text).lower()
    found = {action for phrase, action in ACTIONS.items() if phrase in lowered}
    return [action for action in ACTION_ORDER if action in found]


def is_amending(title: str) -> bool:
    return bool(AMENDING_TITLE_RE.match(nfc(title)))


def document_in(text: str) -> DocumentRef | None:
    """The first document named in the text."""
    match = DOCUMENT_RE.search(nfc(text))
    return DocumentRef(match["kind"].capitalize(), match["number"]) if match else None


def lead(text: str) -> str:
    """The instruction, without the new text: up to "như sau", and with
    quoted phrases dropped ("thay cụm từ "Điều 5" bằng ...")."""
    text = re.split(r"\bnhư\s+sau\b", nfc(text), maxsplit=1)[0]
    return QUOTE_RE.sub(" ", text)


def parse_targets(text: str, default_document: DocumentRef | None) -> list[Target]:
    """The Dieu changed by one khoan of an amending Dieu."""
    instruction = lead(text)
    actions = actions_in(instruction)
    if not actions:
        return []
    document = document_in(instruction) or default_document
    if not document:
        return []
    inserted_after = INSERTED_AFTER_RE.search(instruction)
    if inserted_after and "bo_sung" in actions:
        # "Bổ sung Điều 35a vào sau Điều 35": no chunk has Dieu 35a yet, so
        # the new Dieu hangs off the one it follows.
        new = TARGET_RE.search(instruction[: inserted_after.start()])
        scope = f"Điều {new['dieu']}" if new else None
        return [Target(document, inserted_after.group(1), scope, actions)]
    targets = []
    for match in TARGET_RE.finditer(instruction):
        scope = re.sub(r"\s+", " ", match["scope"]).strip() or None
        target = Target(document, match["dieu"], scope, actions)
        if target not in targets:
            targets.append(target)
    return targets


# The Dieu that can retire other documents: "Hiệu lực thi hành", "Điều khoản thi hành", ...
EFFECT_TITLE_RE = re.compile(r"hiệu lực|thi hành|chuyển tiếp", re.IGNORECASE)
REPLACING_RE = re.compile(r"thay thế|hết hiệu lực", re.IGNORECASE)


def replaced_documents(title: str, text: str, own_document_id: str | None = None) -> list[DocumentRef]:
    """Every document this Dieu replaces or ends, read from its sentences with
    "thay thế" / "hết hiệu lực" ("Nghị định này thay thế Nghị định số
    05/2015/NĐ-CP"; "Thông tư số 10/2020/TT-BLĐTBXH hết hiệu lực kể từ ngày
    Thông tư này có hiệu lực"). Only in an effect Dieu, since "thay thế" is
    common in provisions too."""
    if not EFFECT_TITLE_RE.search(nfc(title)):
        return []
    found: list[DocumentRef] = []
    for sentence in re.split(r"(?<=[.;])\s+|\n", nfc(text)):
        if not REPLACING_RE.search(sentence):
            continue
        for match in DOCUMENT_RE.finditer(sentence):
            ref = DocumentRef(match["kind"].capitalize(), match["number"])
            if ref.document_id != own_document_id and ref.document_id not in {r.document_id for r in found}:
                found.append(ref)
    return found

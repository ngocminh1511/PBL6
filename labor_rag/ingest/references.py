"""Read the cross-references written in the text of a Dieu, down to the khoan.

Phap dien links some references (pChiDan, at Dieu level only); most are only
in the text: "theo quy định tại khoản 3 Điều 147", "điểm a, b khoản 2 Điều 5
của Luật này", "Điều 46 của Bộ luật Lao động", "khoản 1 Điều 5 Nghị định số
145/2020/NĐ-CP", or "tại khoản 2" (this Dieu).

The target document is, in order: the one named after the reference
("của Luật này", a document number, a law name); else, inside the khoan of a
Dieu whose lead introduces a list ("... một số điều, khoản sau đây của Bộ luật
Lao động:"), the document named in that lead; else the citing document itself.
A lead with "quy định chi tiết" / "hướng dẫn" marks the references below it
as implementing the target (vlr:implementsComponent) rather than citing it.
"""
from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple

from labor_rag.ingest.amending import NUMBER, QUOTE_RE
from labor_rag.ingest.chunk_schema import KHOAN_RE, make_document_id

KINDS = r"Bộ luật|Luật|Pháp lệnh|Nghị quyết liên tịch|Nghị quyết|Nghị định|Thông tư liên tịch|Thông tư|Quyết định"
SEP = r"\s*(?:,|và|hoặc)\s*"
NUM = r"\d+[a-zđ]?"
DIEM = r"[a-zđ]"
# "các điểm a, b khoản 2 và khoản 3 Điều 35, 36": diem, khoan, Dieu lists.
REF_RE = re.compile(
    rf"(?:(?i:các\s+)?(?i:điểm)\s+(?P<diem>{DIEM}(?:{SEP}(?:(?i:điểm)\s+)?{DIEM})*)\s+(?:của\s+)?)?"
    rf"(?:(?i:các\s+)?(?i:khoản)\s+(?P<khoan>{NUM}(?:{SEP}(?:(?i:khoản)\s+)?{NUM})*)\s+(?:của\s+)?)?"
    rf"(?:các\s+)?(?:Điều|(?i:điều)(?=\s+\d))\s+(?P<dieu>này|{NUM}(?:{SEP}(?:(?i:điều)\s+)?{NUM})*)\b"
)
# "tại khoản 2", "theo điểm a khoản 1": a khoan of this Dieu. Only where no
# REF_RE match overlaps ("tại khoản 1, khoản 2 Điều 123" is one reference).
BARE_KHOAN_RE = re.compile(
    rf"(?:tại|theo|ở|của)\s+(?:các\s+)?(?:(?i:điểm)\s+(?P<diem>{DIEM}(?:{SEP}(?:(?i:điểm)\s+)?{DIEM})*)\s+)?"
    rf"(?i:khoản)\s+(?P<khoan>{NUM}(?:{SEP}(?:(?i:khoản)\s+)?{NUM})*)\b(?!\s+(?:của\s+)?(?:các\s+)?Điều)"
)
DOCUMENT_TAIL_RE = re.compile(
    rf"\s*(?:của\s+|tại\s+)?(?P<kind>{KINDS})\s+(?:(?P<this>này)\b|(?:số\s+)?(?P<number>{NUMBER})|(?P<rest>[^;:()\n]*))",
    re.IGNORECASE,
)
CHAIN_GAP_RE = re.compile(r"\s*[,;]?\s*(?:và|hoặc)?\s*(?:theo|tại)?\s*")
LIST_LEAD_RE = re.compile(r"sau\s+đây|như\s+sau|gồm|bao\s+gồm", re.IGNORECASE)
IMPLEMENTS_RE = re.compile(r"quy\s+định\s+chi\s+tiết|hướng\s+dẫn", re.IGNORECASE)


def fold(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip().lower()


class Target(NamedTuple):
    document_id: str | None  # None: a law named by title that is not in the data
    dieu: str
    khoan: str | None  # None: the whole Dieu
    diem: str | None  # "a, b" within the khoan, kept as text


class Reference(NamedTuple):
    text: str  # the reference as written
    targets: list[Target]
    document_name: str | None  # the title when the document could not be resolved
    implements: bool
    line: str = ""  # the line it was read from


class DocumentIndex:
    """What is known about the documents: law titles -> document number, from
    the Phap dien citations ("Bộ luật số 45/2019/QH14 Bộ Luật lao động ngày
    ..."; newer wins when two documents share a title), and the Dieu each
    document has, to tell which document an unnamed reference points to."""

    def __init__(self) -> None:
        self.by_name: dict[str, tuple[str, str]] = {}  # folded title -> (effective date, document_id)
        self.articles: set[tuple[str, str]] = set()  # (document_id, Dieu number)
        self.numbers: dict[str, tuple[str, str]] = {}  # document_id -> (kind, document number)

    def register(self, kind: str, number: str) -> str:
        document_id = make_document_id(number)
        self.numbers.setdefault(document_id, (kind, number))
        return document_id

    def has(self, document_id: str | None, dieu: str) -> bool:
        return (document_id, dieu) in self.articles

    def knows(self, document_id: str | None) -> bool:
        return any(doc == document_id for doc, _ in self.articles)

    def add(self, kind: str, number: str, summary: str | None, effective: str | None) -> str | None:
        """Register a cited document; returns its short title for a law ("Bộ luật Lao động")."""
        self.register(kind, number)
        if not summary or kind.lower() not in {"bộ luật", "luật", "pháp lệnh"}:
            return None
        title = re.split(r"\s+ngày\s+\d", summary)[0].strip()
        short_title = title if fold(title).startswith(fold(kind)) else f"{kind} {title}"
        name = fold(short_title)
        current = self.by_name.get(name)
        if current is None or (effective or "") > current[0]:
            self.by_name[name] = (effective or "", make_document_id(number))
        return short_title

    def find(self, text: str) -> tuple[str | None, str]:
        """(document_id, matched title) for the longest known title starting the text."""
        folded = fold(text)
        for name in sorted(self.by_name, key=len, reverse=True):
            if folded.startswith(name):
                return self.by_name[name][1], name
        return None, ""


def split_list(value: str | None, unit: str) -> list[str]:
    """'47, Điều 48 và 49' -> ['47', '48', '49']."""
    if not value:
        return []
    items = [re.sub(rf"^{unit}\s+", "", item.strip(), flags=re.IGNORECASE) for item in re.split(SEP, value)]
    return [item for item in items if item]


def document_after(text: str, own_document_id: str, names: DocumentIndex) -> tuple[str | None, str | None, bool]:
    """(document_id, unresolved title, named) for the words after a reference."""
    match = DOCUMENT_TAIL_RE.match(text)
    if not match:
        return own_document_id, None, False
    if match["this"]:
        return own_document_id, None, True
    if match["number"]:
        return names.register(match["kind"].capitalize(), match["number"]), None, True
    document_id, _ = names.find(f"{match['kind']} {match['rest']}")
    if document_id:
        return document_id, None, True
    # "Luật bảo hiểm xã hội số 58/2014/QH13": a title, then the number.
    number = re.match(rf"[^,;.]{{0,80}}?\bsố\s+({NUMBER})", match["rest"] or "")
    if number:
        return names.register(match["kind"].capitalize(), number.group(1)), None, True
    title = f"{match['kind']} {match['rest']}".strip()
    # "Luật này" handled above; a bare kind ("theo Luật") is not a reference to a document.
    return (None, title, True) if match["kind"].lower() in {"bộ luật", "luật", "pháp lệnh"} and match["rest"].strip() else (own_document_id, None, False)


def read_line(
    line: str,
    own_document_id: str,
    own_dieu: str,
    own_khoan: str | None,
    names: DocumentIndex,
    default_document_id: str | None = None,
    implements: bool = False,
) -> list[Reference]:
    """References in one line (a lead or a khoan) of a Dieu."""
    text = QUOTE_RE.sub(lambda m: " " * len(m.group()), line)  # quoted new text of an amendment
    found: list[Reference] = []
    matches = list(REF_RE.finditer(text))
    taken = [match.span() for match in matches]
    # "Điều này" points at this Dieu; it names no document for the others.
    this_dieu = [split_list(match["dieu"], "Điều") == ["này"] for match in matches]
    documents = []  # (document_id, unresolved title, named) per match
    for match, this in zip(matches, this_dieu):
        documents.append((own_document_id, None, True) if this else document_after(text[match.end():], own_document_id, names))
    # "khoản 1 Điều 35 và khoản 2 Điều 36 của Bộ luật Lao động": the document
    # named after the last reference of a chain applies to the whole chain.
    for index in range(len(matches) - 2, -1, -1):
        gap = text[matches[index].end():matches[index + 1].start()]
        if not documents[index][2] and documents[index + 1][2] and not this_dieu[index + 1] and CHAIN_GAP_RE.fullmatch(gap):
            documents[index] = documents[index + 1]
    # "... theo Điều 111, ... theo Điều 112, Điều 113; ... của Bộ luật Lao động":
    # in a line that never names its own document, an unnamed reference
    # belongs to the next document named after it.
    named_documents = [(d, this) for d, this in zip(documents, this_dieu) if d[2] and not this]
    if not any(d[0] == own_document_id for d, _ in named_documents):
        for index in range(len(matches)):
            if not documents[index][2]:
                later = [d for d, this in zip(documents[index + 1:], this_dieu[index + 1:]) if d[2] and not this]
                documents[index] = later[0] if later else documents[index]
    named_in_line = [document_id for document_id, _, named in documents if named and document_id]
    for match, (document_id, unresolved, named) in zip(matches, documents):
        dieus = split_list(match["dieu"], "Điều")
        if dieus == ["này"]:
            dieus = [own_dieu]
        elif not named:
            if default_document_id:
                document_id = default_document_id
            # "theo Điều 162; ... Điều 16 của Bộ luật Lao động" in a Nghị định
            # without a Dieu 162: the document named in the line has it.
            if names.knows(document_id) and not names.has(document_id, dieus[0]):
                document_id = next((doc for doc in named_in_line if names.has(doc, dieus[0])), document_id)
        khoans = split_list(match["khoan"], "khoản")
        diem = ", ".join(split_list(match["diem"], "điểm")) or None
        targets = []
        for index, dieu in enumerate(dieus):
            if index == 0 and khoans:
                targets += [Target(document_id, dieu, khoan, diem if len(khoans) == 1 else None) for khoan in khoans]
            else:
                targets.append(Target(document_id, dieu, None, None))
        found.append(Reference(match.group().strip(), targets, unresolved, implements, line))
    for match in BARE_KHOAN_RE.finditer(text):
        if any(match.start() < end and start < match.end() for start, end in taken):
            continue
        khoans = split_list(match["khoan"], "khoản")
        diem = ", ".join(split_list(match["diem"], "điểm")) or None
        # "điểm b khoản 1 và điểm b khoản 2 Điều 8": the Dieu of the reference
        # that ends the chain; otherwise a khoan of this Dieu.
        document_id, dieu = own_document_id, own_dieu
        following = next((ref for ref, m in zip(found, matches) if m.start() >= match.end()), None)
        next_match = next((m for m in matches if m.start() >= match.end()), None)
        if following and CHAIN_GAP_RE.fullmatch(text[match.end():next_match.start()]):
            document_id, dieu = following.targets[0].document_id, following.targets[0].dieu
        targets = [Target(document_id, dieu, khoan, diem if len(khoans) == 1 else None) for khoan in khoans]
        if dieu == own_dieu and document_id == own_document_id:
            targets = [t for t in targets if t.khoan != own_khoan or t.diem]  # "khoản này" style self-mentions
        if targets:
            found.append(Reference(match.group().split(None, 1)[1].strip(), targets, None, False, line))
    return found


def list_context(lead: str, own_document_id: str, names: DocumentIndex) -> tuple[str | None, bool]:
    """(document the list items refer to, implements) for a lead that
    introduces a list: "... một số điều, khoản sau đây của Bộ luật Lao động:",
    "Sửa đổi, bổ sung một số điều của Luật Bảo hiểm xã hội như sau:"."""
    if not (LIST_LEAD_RE.search(lead) or lead.rstrip().endswith(":")):
        return None, False
    document_id = None
    tail = re.search(rf"(?:của\s+)?(?:{KINDS})\s+(?!này)\S", lead, re.IGNORECASE)
    if tail:
        found, _, named = document_after(lead[tail.start():], own_document_id, names)
        document_id = found if named else None
    return document_id, bool(IMPLEMENTS_RE.search(lead))


def split_clauses(paragraphs: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """(lead lines, [(khoan number, its lines incl. its diem)]) of a Dieu."""
    lead: list[str] = []
    clauses: list[tuple[str, list[str]]] = []
    for paragraph in paragraphs:
        match = KHOAN_RE.match(paragraph.strip())
        if match:
            clauses.append((match.group(1), [paragraph]))
        elif clauses:
            clauses[-1][1].append(paragraph)
        else:
            lead.append(paragraph)
    return lead, clauses


def read_article(
    paragraphs: list[str], own_document_id: str, own_dieu: str, names: DocumentIndex
) -> list[tuple[str | None, Reference]]:
    """[(khoan of the citing Dieu or None for its lead, reference)] for one Dieu."""
    lead, clauses = split_clauses(paragraphs)
    # A lead that introduces a list names the document its items refer to:
    # the Dieu lead for its khoan, a khoan's first line for its diem.
    default_document_id, implements = list_context(" ".join(lead), own_document_id, names) if clauses else (None, False)
    found = [(None, ref) for line in lead for ref in read_line(line, own_document_id, own_dieu, None, names)]
    for khoan, lines in clauses:
        found += [
            (khoan, ref)
            for ref in read_line(lines[0], own_document_id, own_dieu, khoan, names, default_document_id, implements)
        ]
        clause_document_id, clause_implements = list_context(lines[0], own_document_id, names) if len(lines) > 1 else (None, False)
        for line in lines[1:]:
            found += [
                (khoan, ref)
                for ref in read_line(
                    line,
                    own_document_id,
                    own_dieu,
                    khoan,
                    names,
                    clause_document_id or default_document_id,
                    clause_implements or implements,
                )
            ]
    return found

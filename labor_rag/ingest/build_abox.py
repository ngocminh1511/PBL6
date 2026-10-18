r"""Build a v4 ABox (Turtle) for any de muc of the Bo Phap Dien.

The HTML is read in memory by parse_demuc_html.parse_demuc_nodes(), so every
de muc in data/raw/bophapdien goes through one code path. Topic/item numbers and names come from
data/interim/chu_de.json and de_muc.json (run parse_jsondata first); source
documents, their issuing authorities and validity dates are derived from the
pGhiChu citation of each Dieu, and its amendments (which article of which
document, sửa đổi / bổ sung / bãi bỏ, from when) from the
"... được sửa đổi ... bởi Điều X <văn bản>" tail. Each Dieu is split into its
khoan (vld:Clause, with their text), and the references written in its text
("theo quy định tại khoản 3 Điều 147 của Bộ luật Lao động") become
vlr:citesComponent / vlr:implementsComponent between source Dieu, khoan and
diem (labor_rag/ingest/references.py). Citations are read in a first pass over
every selected de muc, so a reference can name any document of the run.

Usage (from the repository root):
    python -m labor_rag.ingest.build_abox --chu-de 20 --output ontology/abox/abox_lao_dong.ttl
    python -m labor_rag.ingest.build_abox --de-muc 20.5     # one de muc -> abox_<de muc>.ttl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD

from labor_rag.config import ABOX_DIR, BOPHAPDIEN_DIR, INTERIM_DIR
from labor_rag.ingest.amending import actions_in
from labor_rag.ingest.chunk_schema import make_document_id
from labor_rag.ingest.references import DocumentIndex, read_article, split_clauses
from labor_rag.ingest.parse_demuc_html import iter_dieu, load_linh_vuc_index, parse_demuc_nodes

sys.stdout.reconfigure(encoding="utf-8")

VLC = Namespace("https://example.org/vn-legal/core#")
VLD = Namespace("https://example.org/vn-legal/document#")
VLA = Namespace("https://example.org/vn-legal/authority#")
VLR = Namespace("https://example.org/vn-legal/relation#")
VLT = Namespace("https://example.org/vn-legal/time#")
VLPD = Namespace("https://example.org/vn-legal/phapdien#")
VLP = Namespace("https://example.org/vn-legal/provenance#")
INST = Namespace("https://example.org/vn-legal/instance#")

# Issuer codes as they appear in document numbers (after stripping the
# legislature term digits, e.g. QH13 -> QH, UBTVQH14 -> UBTVQH).
AUTHORITIES: dict[str, tuple[str, URIRef, str]] = {
    "QH": ("Auth_QuocHoi", VLA.NationalAssembly, "Quốc hội"),
    "UBTVQH": ("Auth_UBTVQH", VLA.LegislativeBody, "Ủy ban Thường vụ Quốc hội"),
    "CTN": ("Auth_ChuTichNuoc", VLA.President, "Chủ tịch nước"),
    "CP": ("Auth_ChinhPhu", VLA.Government, "Chính phủ"),
    "TTG": ("Auth_ThuTuong", VLA.PrimeMinister, "Thủ tướng Chính phủ"),
    "TANDTC": ("Auth_TANDTC", VLA.SupremePeopleCourt, "Tòa án nhân dân tối cao"),
    "HĐTP": ("Auth_HDTP", VLA.SupremePeopleCourt, "Hội đồng Thẩm phán Tòa án nhân dân tối cao"),
    "VKSNDTC": ("Auth_VKSNDTC", VLA.SupremePeopleProcuracy, "Viện kiểm sát nhân dân tối cao"),
    "KTNN": ("Auth_KTNN", VLA.Authority, "Kiểm toán nhà nước"),
    "ĐCTUBTWMTTQVN": ("Auth_MTTQ", VLA.Authority, "Đoàn Chủ tịch Ủy ban Trung ương Mặt trận Tổ quốc Việt Nam"),
    "TLĐLĐVN": ("Auth_TLDLD", VLA.Authority, "Tổng Liên đoàn Lao động Việt Nam"),
    "TTCP": ("Auth_TTCP", VLA.Ministry, "Thanh tra Chính phủ"),
    "NHNN": ("Auth_NHNN", VLA.Ministry, "Ngân hàng Nhà nước Việt Nam"),
    "UBDT": ("Auth_UBDT", VLA.Ministry, "Ủy ban Dân tộc"),
    "BLĐTBXH": ("Auth_BLD", VLA.Ministry, "Bộ Lao động - Thương binh và Xã hội"),
    "BQP": ("Auth_BQP", VLA.Ministry, "Bộ Quốc phòng"),
    "BCA": ("Auth_BCA", VLA.Ministry, "Bộ Công an"),
    "BNG": ("Auth_BNG", VLA.Ministry, "Bộ Ngoại giao"),
    "BNV": ("Auth_BNV", VLA.Ministry, "Bộ Nội vụ"),
    "BTP": ("Auth_BTP", VLA.Ministry, "Bộ Tư pháp"),
    "BTC": ("Auth_BTC", VLA.Ministry, "Bộ Tài chính"),
    "BCT": ("Auth_BCT", VLA.Ministry, "Bộ Công Thương"),
    "BKHĐT": ("Auth_BKHDT", VLA.Ministry, "Bộ Kế hoạch và Đầu tư"),
    "BNNPTNT": ("Auth_BNNPTNT", VLA.Ministry, "Bộ Nông nghiệp và Phát triển nông thôn"),
    "BNNMT": ("Auth_BNNMT", VLA.Ministry, "Bộ Nông nghiệp và Môi trường"),
    "BNN": ("Auth_BNN", VLA.Ministry, "Bộ Nông nghiệp"),
    "BTNMT": ("Auth_BTNMT", VLA.Ministry, "Bộ Tài nguyên và Môi trường"),
    "BGTVT": ("Auth_BGTVT", VLA.Ministry, "Bộ Giao thông vận tải"),
    "BXD": ("Auth_BXD", VLA.Ministry, "Bộ Xây dựng"),
    "BTTTT": ("Auth_BTTTT", VLA.Ministry, "Bộ Thông tin và Truyền thông"),
    "BGDĐT": ("Auth_BGDDT", VLA.Ministry, "Bộ Giáo dục và Đào tạo"),
    "BVHTTDL": ("Auth_BVHTTDL", VLA.Ministry, "Bộ Văn hóa, Thể thao và Du lịch"),
    "BKHCN": ("Auth_BKHCN", VLA.Ministry, "Bộ Khoa học và Công nghệ"),
    "BYT": ("Auth_BYT", VLA.Ministry, "Bộ Y tế"),
    "BDTTG": ("Auth_BDTTG", VLA.Ministry, "Bộ Dân tộc và Tôn giáo"),
    # Bodies that were renamed or merged; kept so pre-2010 documents resolve.
    "HĐNN": ("Auth_HoiDongNhaNuoc", VLA.LegislativeBody, "Hội đồng Nhà nước"),
    "VPCP": ("Auth_VPCP", VLA.Ministry, "Văn phòng Chính phủ"),
    "BTCCBCP": ("Auth_BTCCBCP", VLA.Ministry, "Ban Tổ chức - Cán bộ Chính phủ"),
    "BVHTT": ("Auth_BVHTT", VLA.Ministry, "Bộ Văn hóa - Thông tin"),
    "BTM": ("Auth_BTM", VLA.Ministry, "Bộ Thương mại"),
    "BCN": ("Auth_BCN", VLA.Ministry, "Bộ Công nghiệp"),
    "BTS": ("Auth_BTS", VLA.Ministry, "Bộ Thủy sản"),
    "BBCVT": ("Auth_BBCVT", VLA.Ministry, "Bộ Bưu chính, Viễn thông"),
    "BKHCNMT": ("Auth_BKHCNMT", VLA.Ministry, "Bộ Khoa học, Công nghệ và Môi trường"),
    "UBTDTT": ("Auth_UBTDTT", VLA.Ministry, "Ủy ban Thể dục Thể thao"),
    "TCT": ("Auth_TCT", VLA.Authority, "Tổng cục Thuế"),
    "TCĐC": ("Auth_TCDC", VLA.Authority, "Tổng cục Địa chính"),
    "HCCBVN": ("Auth_HCCBVN", VLA.Authority, "Hội Cựu chiến binh Việt Nam"),
}
AUTHORITY_ALIASES = {
    "BNNPTTN": "BNNPTNT", "BNNPTN": "BNNPTNT", "NNPTNT": "BNNPTNT",
    "BKH": "BKHĐT", "TC": "BTC", "NH": "NHNN", "NHNNVN": "NHNN",
    "TATC": "TANDTC", "VKSTC": "VKSNDTC", "VKSNDT": "VKSNDTC",
    "UBTUMTTQVN": "ĐCTUBTWMTTQVN", "UBTƯMTTQVN": "ĐCTUBTWMTTQVN", "MTTW": "ĐCTUBTWMTTQVN",
    "TWHCCBVN": "HCCBVN", "CCBVN": "HCCBVN", "CCB": "HCCBVN", "TCCP": "BTCCBCP",
    "HDNN": "HĐNN", "HĐTPTANDTC": "HĐTP",
}
# Tokens in a document number that name the document type, not the issuer.
DOCUMENT_TYPE_TOKENS = {
    "NĐ", "ND", "TT", "TTLT", "TTLB", "TTLN", "LB", "QĐ", "QD", "NQ", "NQLT", "CT", "PL", "L", "LCT",
    "HD", "HDLT", "SL", "QĐLB", "TB",
}

# Ordered longest-first so "Thông tư liên tịch" wins over "Thông tư".
DOCUMENT_KINDS: list[tuple[str, URIRef, str]] = [
    ("Thông tư liên tịch", VLD.JointCircular, "JointCircular"),
    ("Nghị quyết liên tịch", VLD.Resolution, "Resolution"),
    ("Hiến pháp", VLD.Law, "Law"),
    ("Bộ luật", VLD.Law, "Law"),
    ("Luật", VLD.Law, "Law"),
    ("Pháp lệnh", VLD.Ordinance, "Ordinance"),
    ("Nghị quyết", VLD.Resolution, "Resolution"),
    ("Nghị định", VLD.Decree, "Decree"),
    ("Thông tư", VLD.Circular, "Circular"),
    ("Quyết định", VLD.Decision, "Decision"),
]
DEFAULT_ISSUER_BY_TYPE = {"Law": "QH", "Ordinance": "UBTVQH", "Decree": "CP"}

_KIND_ALT = "|".join(re.escape(kind) for kind, _, _ in DOCUMENT_KINDS) + r"|[A-ZĐÂ][\wÀ-ỹ]*(?:\s+[\wÀ-ỹ]+)?"
SOURCE_RE = re.compile(
    r"Điều\s+(?P<article>[\w.]+?)\s+(?P<kind>" + _KIND_ALT + r")\s+"
    # The first citation of a document usually adds its summary and
    # signing date: "... số 84/2015/QH13 An toàn, ... ngày 25/06/2015 của Quốc hội, có hiệu lực ..."
    r"(?:số\s+(?P<number>[^\s,]*\d[^\s,]*)(?:\s+(?P<summary>.+?))?|(?P<name>.+?))\s*,?\s*"
    r"có\s+hiệu\s+lực\s+thi\s+hành\s+kể\s+từ\s+ngày\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)
ISSUED_RE = re.compile(r"ngày\s+(\d{1,2}/\d{1,2}/\d{4})\s+của\s", re.IGNORECASE)
# "03/2017/TT- BVHTTDL" -> "03/2017/TT-BVHTTDL"
BROKEN_NUMBER_RE = re.compile(r"(?<=[A-ZĐ])-\s+(?=[A-ZĐ])")


class Source(NamedTuple):
    """One "Điều X <văn bản> ..., có hiệu lực ... ngày D" in a citation."""

    document: URIRef
    article: str
    effective: str | None
    actions: list[str]  # for an amending source: what it did to the Dieu


def clean_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def slug(value: str) -> str:
    """Create a stable ASCII local identifier without changing display text."""
    value = value.replace("Đ", "D").replace("đ", "d")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return value or "unknown"


def local_name(uri: URIRef) -> str:
    """'https://example.org/vn-legal/instance#Doc_Decree_145_2020_ND_CP' -> 'Doc_Decree_145_2020_ND_CP'."""
    return str(uri).rsplit("#", 1)[-1]


def number_slug(number: str) -> str:
    """Article/clause number for a local name; 'đ' stays distinct from 'd' ('35đ' follows '35d')."""
    return slug(number.replace("đ", "dd"))


def article_local(code: str) -> str:
    """Local name for a Dieu code. A lowercase 'đ' suffix is a distinct
    article ('3.3.NĐ.4.35đ' follows '...35d'), so it must not fold to 'd'."""
    return f"Article_{slug(code.replace('đ', 'dd'))}"


def parse_vn_date(text: str) -> str | None:
    match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", text)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def normalize_number(number: str) -> str:
    """'45/2019/QH14.' -> '45/2019/QH14'; 'NQ.HĐTP' -> 'NQ-HĐTP'."""
    number = number.replace("Ð", "Đ").rstrip(".\"”")
    return re.sub(r"(?<=[A-ZĐ])\.(?=[A-ZĐ])", "-", number)


def document_kind(kind_text: str) -> tuple[URIRef, str, str]:
    for kind, cls, local in DOCUMENT_KINDS:
        if kind_text.lower() == kind.lower():
            return cls, local, kind
    return VLD.OtherLegalDocument, "Other", kind_text


def issuer_codes(number: str | None) -> list[str]:
    """'39/2016/NĐ-CP' -> ['CP']; '12/2017/TTLT-BTC-BKHCN' -> ['BTC', 'BKHCN']."""
    if not number:
        return []
    # Normalise typing variants seen in the source: "BGDÐT" (U+00D0),
    # "BNN&PTNT", "NĐ_CP", "QĐ-TTg.", "NQ.HĐTP", "TT-BCA(X13)".
    suffix = number.upper().replace("Ð", "Đ").replace("&", "").rstrip(".\"”").rsplit("/", 1)[-1]
    suffix = re.sub(r"\(.*?\)", "", suffix)
    codes = []
    for token in re.split(r"[-_.]", suffix):
        token = re.sub(r"\d+$", "", token.strip())
        token = AUTHORITY_ALIASES.get(token, token)
        if token and not token.isdigit() and token not in DOCUMENT_TYPE_TOKENS and token not in codes:
            codes.append(token)
    return codes


class AboxBuilder:
    def __init__(self) -> None:
        self.graph = Graph()
        for prefix, namespace in {
            "vlc": VLC, "vld": VLD, "vla": VLA, "vlr": VLR, "vlt": VLT, "vlpd": VLPD, "vlp": VLP, "inst": INST,
        }.items():
            self.graph.bind(prefix, namespace)
        self.effective_dates: dict[URIRef, set[str]] = {}
        self.valid_to: dict[URIRef, str] = {}
        self.index = DocumentIndex()  # law titles and Dieu of every document, for references
        self.doc_by_id: dict[str, URIRef] = {}
        self.id_by_doc: dict[URIRef, str] = {}
        self.article_uris: Counter[str] = Counter()
        self.unparsed_citations: list[str] = []
        self.unknown_issuers: Counter[str] = Counter()

    def add(self, s, p, o) -> None:
        self.graph.add((s, p, o))

    # --- source documents -------------------------------------------------

    def authority(self, code: str) -> URIRef:
        if code in AUTHORITIES:
            local, cls, label = AUTHORITIES[code]
        else:
            self.unknown_issuers[code] += 1
            local, cls, label = f"Auth_{slug(code)}", VLA.Authority, code
        uri = INST[local]
        self.add(uri, RDF.type, cls)
        self.add(uri, RDFS.label, Literal(label, lang="vi"))
        return uri

    def document(
        self, kind_text: str, number: str | None, name: str | None, effective: str | None, issued: str | None = None
    ) -> URIRef:
        cls, local, kind = document_kind(kind_text)
        if number:
            number = normalize_number(number)
        # Some older documents (e.g. "Pháp lệnh Về Hàm, cấp ngoại giao", 1995)
        # are cited by title only; the title then serves as their identifier.
        identifier = number or f"{kind} {clean_text(name)}"
        uri = INST[f"Doc_{local}_{slug(identifier.replace('/', '_'))}"]
        if number:
            self.doc_by_id.setdefault(make_document_id(number), uri)
            self.id_by_doc.setdefault(uri, make_document_id(number))
        self.add(uri, RDF.type, cls)
        self.add(uri, VLD.documentNumber, Literal(identifier, datatype=XSD.string))
        self.add(uri, VLD.title, Literal(f"{kind} số {number}" if number else identifier, lang="vi"))
        codes = issuer_codes(number) or ([DEFAULT_ISSUER_BY_TYPE[local]] if local in DEFAULT_ISSUER_BY_TYPE else [])
        for code in codes:
            self.add(uri, VLR.promulgatedBy, self.authority(code))
        if effective:
            self.effective_dates.setdefault(uri, set()).add(effective)
        if issued and (uri, VLD.issuedDate, None) not in self.graph:
            self.add(uri, VLD.issuedDate, Literal(issued, datatype=XSD.date))
        return uri

    def validity_interval(self, doc_uri: URIRef) -> URIRef:
        # One interval per document, so an ABox that only ends a document
        # (a replacing PDF) adds validTo to the same node as the Phap dien ABox.
        interval = INST[f"Validity_{local_name(doc_uri).removeprefix('Doc_')}"]
        self.add(interval, RDF.type, VLT.LegalValidityInterval)
        self.add(doc_uri, VLT.hasValidityInterval, interval)
        return interval

    def finish_documents(self) -> None:
        """One validity interval per document, starting at the earliest
        effective date cited for it (articles of one law can take effect on
        different dates; vlt:validFrom is single-valued), and ending when a
        replacing document takes effect."""
        for doc_uri, dates in self.effective_dates.items():
            valid_from = min(dates)
            self.add(self.validity_interval(doc_uri), VLT.validFrom, Literal(valid_from, datatype=XSD.date))
            self.add(doc_uri, VLD.effectiveDate, Literal(valid_from, datatype=XSD.date))
        for doc_uri, valid_to in self.valid_to.items():
            self.add(self.validity_interval(doc_uri), VLT.validTo, Literal(valid_to, datatype=XSD.date))

    def sources(self, citation: str | None) -> list[Source]:
        """The codified source first, then the articles that amended it, each
        with the actions named between the previous citation and its own."""
        found = []
        text = BROKEN_NUMBER_RE.sub("-", citation or "")
        previous_end = 0
        for m in SOURCE_RE.finditer(text):
            issued = ISSUED_RE.search(m["summary"] or "")
            effective = parse_vn_date(m["date"])
            doc = self.document(
                m["kind"], m["number"], m["name"], effective, parse_vn_date(issued.group(1)) if issued else None
            )
            if m["number"]:
                short_title = self.index.add(m["kind"], normalize_number(m["number"]), m["summary"], effective)
                if short_title:
                    self.add(doc, VLD.shortTitle, Literal(short_title, lang="vi"))
            # ", có nội dung được sửa đổi, có nội dung được bổ sung bởi " -> vlr:amendmentAction
            actions = actions_in(text[previous_end:m.start()]) if found else []
            found.append(Source(doc, m["article"], effective, actions))
            previous_end = m.end()
        if citation and not found:
            self.unparsed_citations.append(citation)
        return found

    # --- codification structure ------------------------------------------

    def source_article(self, doc_uri: URIRef, number: str) -> URIRef:
        """Dieu `number` of a source document: SourceArticle_Decree_145_2020_ND_CP_D35."""
        source_uri = INST[f"SourceArticle_{local_name(doc_uri).removeprefix('Doc_')}_D{number_slug(number)}"]
        self.add(source_uri, RDF.type, VLD.Article)
        self.add(source_uri, VLD.locatedInDocument, doc_uri)
        # The article number in the source document ("35", "4a"): with the
        # document number it identifies the Dieu across Phap dien and PDF.
        self.add(source_uri, VLD.itemNumber, Literal(number, datatype=XSD.string))
        return source_uri

    def add_source_mapping(self, article_uri: URIRef, doc_uri: URIRef, source_article: str, quote: str) -> URIRef:
        source_uri = self.source_article(doc_uri, source_article)
        self.add(article_uri, VLPD.codificationOf, source_uri)

        mapping_uri = INST[f"SourceMapping_{local_name(article_uri).removeprefix('Article_')}"]
        self.add(mapping_uri, RDF.type, VLPD.SourceMapping)
        self.add(article_uri, VLPD.hasSourceMapping, mapping_uri)
        self.add(mapping_uri, VLPD.mapsToSourceComponent, source_uri)
        self.add(mapping_uri, VLPD.mapsToSourceDocument, doc_uri)

        statement_uri = INST[f"Statement_{hashlib.sha1(f'{article_uri}|{doc_uri}'.encode('utf-8')).hexdigest()[:12]}"]
        self.add(statement_uri, RDF.type, VLP.ExtractedStatement)
        self.add(statement_uri, VLP.sourceDocument, doc_uri)
        self.add(statement_uri, VLP.sourceComponent, source_uri)
        self.add(statement_uri, VLP.sourceQuote, Literal(quote, lang="vi"))
        return source_uri

    def source_clause(self, article_uri: URIRef, doc_uri: URIRef, number: str) -> URIRef:
        """Khoan `number` of a source Dieu: SourceClause_Decree_70_2023_ND_CP_D1_K2."""
        clause_uri = INST[f"SourceClause_{local_name(article_uri).removeprefix('SourceArticle_')}_K{number_slug(number)}"]
        self.add(clause_uri, RDF.type, VLD.Clause)
        self.add(clause_uri, VLD.locatedInDocument, doc_uri)
        self.add(clause_uri, VLD.itemNumber, Literal(number, datatype=XSD.string))
        self.add(article_uri, VLD.hasClause, clause_uri)
        return clause_uri

    def index_de_muc(self, tree: dict) -> None:
        """First pass: law titles and the Dieu of each source document, so a
        reference in any de muc can be resolved."""
        for dieu, _ in iter_dieu(tree):
            text = BROKEN_NUMBER_RE.sub("-", dieu["citation"] or "")
            for position, m in enumerate(SOURCE_RE.finditer(text)):
                if not m["number"]:
                    continue
                number = normalize_number(m["number"])
                self.index.add(m["kind"], number, m["summary"], parse_vn_date(m["date"]))
                if position == 0:
                    self.index.articles.add((make_document_id(number), m["article"]))

    def source_point(self, clause_uri: URIRef, doc_uri: URIRef, letter: str) -> URIRef:
        """Diem `letter` of a source khoan: SourcePoint_Decree_145_2020_ND_CP_D35_K2_Pa."""
        point_uri = INST[f"SourcePoint_{local_name(clause_uri).removeprefix('SourceClause_')}_P{number_slug(letter)}"]
        self.add(point_uri, RDF.type, VLD.Point)
        self.add(point_uri, VLD.locatedInDocument, doc_uri)
        self.add(point_uri, VLD.itemNumber, Literal(letter, datatype=XSD.string))
        self.add(clause_uri, VLD.hasPoint, point_uri)
        return point_uri

    def document_uri(self, document_id: str) -> URIRef | None:
        """The document node for a document_id met in a reference."""
        if document_id not in self.doc_by_id and document_id in self.index.numbers:
            kind, number = self.index.numbers[document_id]
            self.document(kind, number, None, None)
        return self.doc_by_id.get(document_id)

    def add_clauses_and_references(self, source_uri: URIRef, doc_uri: URIRef, dieu_number: str, paragraphs: list[str]) -> Counter:
        """The khoan of a source Dieu (vld:Clause + text) and the references in its text."""
        stats: Counter = Counter()
        _, clauses = split_clauses(paragraphs)
        clause_uris: dict[str, URIRef] = {}
        for khoan, lines in clauses:
            if khoan in clause_uris:
                continue  # numbering restarts (a quoted list): keep the first
            clause_uris[khoan] = self.source_clause(source_uri, doc_uri, khoan)
            self.add(clause_uris[khoan], VLD.contentText, Literal("\n".join(lines), lang="vi"))
            stats["clauses"] += 1
        own_id = self.id_by_doc.get(doc_uri)
        if not own_id:
            return stats
        for khoan, reference in read_article(paragraphs, own_id, dieu_number, self.index):
            citing = clause_uris.get(khoan, source_uri) if khoan else source_uri
            predicate = VLR.implementsComponent if reference.implements else VLR.citesComponent
            for target in reference.targets:
                target_doc = self.document_uri(target.document_id) if target.document_id else None
                if target_doc is None:
                    stats["references_unresolved"] += 1
                    continue
                target_uri = self.source_article(target_doc, target.dieu)
                target_uris = [target_uri]
                if target.khoan:
                    target_uri = self.source_clause(target_uri, target_doc, target.khoan)
                    target_uris = [target_uri]
                    if target.diem:
                        target_uris = [self.source_point(target_uri, target_doc, letter) for letter in target.diem.split(", ")]
                for uri in target_uris:
                    if uri != citing:
                        self.add(citing, predicate, uri)
                        stats["references"] += 1
        return stats

    def add_amendment(
        self,
        amended_uri: URIRef,
        amended_doc: URIRef,
        amending_uri: URIRef,
        amending_doc: URIRef,
        actions: list[str],
        effective: str | None,
        scope: str | None = None,
        consolidated: bool = False,
    ) -> None:
        """Article-level amendment: amended_uri (a source Dieu) is changed by
        amending_uri (a Dieu or khoan of amending_doc) from `effective`.
        Phap dien gives it in the citation tail "được sửa đổi ... bởi Điều X
        <văn bản>"; an amending PDF in each khoan ("Sửa đổi khoản 2 Điều 3 ...")."""
        event_uri = INST[
            f"Amendment_{local_name(amended_uri).removeprefix('SourceArticle_')}"
            f"_by_{local_name(amending_uri).split('_', 1)[1]}"
        ]
        self.add(event_uri, RDF.type, VLT.AmendmentEvent)
        self.add(amended_uri, VLR.hasAmendment, event_uri)
        self.add(event_uri, VLR.amendingComponent, amending_uri)
        for action in actions:
            self.add(event_uri, VLR.amendmentAction, Literal(action, datatype=XSD.string))
        if effective:
            self.add(event_uri, VLT.amendsAt, Literal(effective, datatype=XSD.date))
        if scope:
            self.add(event_uri, VLR.amendmentScope, Literal(scope, datatype=XSD.string))
        if consolidated:
            # The Phap dien text of the amended Dieu already includes it.
            self.add(event_uri, VLPD.consolidatedInCodification, Literal(True))
        self.add(amending_doc, VLR.partiallyAmends, amended_doc)
        self.add(amending_doc, VLR.amendsComponent, amended_uri)

    def add_replacement(self, new_doc: URIRef, old_doc: URIRef, effective: str | None) -> None:
        """new_doc replaces old_doc, which stays in force until new_doc takes effect."""
        self.add(new_doc, VLR.replaces, old_doc)
        self.add(old_doc, VLR.replacedBy, new_doc)
        if effective:
            self.valid_to[old_doc] = min(effective, self.valid_to.get(old_doc, effective))

    def add_references(self, owner_uri: URIRef, owner_code: str | None, references: list[dict]) -> None:
        for ref in references:
            m = re.match(r"Điều\s+(\S+?)\.?(?:\s|$)", ref["display_text"])
            if not m or m.group(1).rstrip(".") == owner_code:
                continue
            target_uri = INST[article_local(m.group(1).rstrip('.'))]
            key = hashlib.sha1(f"{owner_uri}|{target_uri}|{ref['display_text']}".encode("utf-8")).hexdigest()[:12]
            reference_uri = INST[f"CrossReference_{key}"]
            self.add(reference_uri, RDF.type, VLPD.CrossReference)
            self.add(reference_uri, VLPD.referenceText, Literal(ref["display_text"], lang="vi"))
            self.add(reference_uri, VLPD.refersToCodificationComponent, target_uri)
            self.add(owner_uri, VLPD.hasCrossReference, reference_uri)
            self.add(owner_uri, VLR.cites, target_uri)

    def add_de_muc(
        self,
        html_path: Path,
        topic_number: int,
        topic_name: str,
        item_number: int,
        item_name: str,
        tree: dict | None = None,
    ) -> Counter:
        tree = tree or parse_demuc_nodes(html_path)
        stats: Counter = Counter()
        if next(iter_dieu(tree), None) is None:
            return stats  # de muc not codified yet

        topic_uri = INST[f"Topic_{topic_number}"]
        self.add(topic_uri, RDF.type, VLPD.Topic)
        self.add(topic_uri, VLPD.topicNumber, Literal(topic_number, datatype=XSD.integer))
        self.add(topic_uri, VLPD.topicName, Literal(topic_name, lang="vi"))
        self.add(topic_uri, RDFS.label, Literal(f"{topic_number}. {topic_name}", lang="vi"))

        item_uri = INST[f"Item_{topic_number}_{item_number}"]
        self.add(item_uri, RDF.type, VLPD.CodificationItem)
        self.add(item_uri, VLPD.itemNumber, Literal(item_number, datatype=XSD.integer))
        self.add(item_uri, VLPD.itemName, Literal(item_name, lang="vi"))
        self.add(item_uri, RDFS.label, Literal(f"{topic_number}.{item_number} {item_name}", lang="vi"))
        self.add(topic_uri, VLPD.hasItem, item_uri)
        self.add(item_uri, VLPD.partOfTopic, topic_uri)

        heading_types = {
            "phan": (VLPD.CodificationPart, VLPD.hasPart, "Part"),
            "chuong": (VLPD.CodificationChapter, VLPD.hasChapter, "Chapter"),
            "muc": (VLPD.CodificationSection, VLPD.hasSection, "Section"),
            "tieu_muc": (VLPD.CodificationSubsection, VLPD.hasSubsection, "Subsection"),
        }
        heading_counts: Counter = Counter()

        def walk(node: dict, parent_uri: URIRef) -> None:
            for child in node["children"]:
                if child["kind"] == "dieu":
                    add_article(child, parent_uri)
                    continue
                cls, link, local = heading_types[child["kind"]]
                heading_counts[local] += 1
                stats[local] += 1
                uri = INST[f"Topic{topic_number}_{item_number}_{local}_{heading_counts[local]}"]
                heading = f"{child['so_hieu']}. {child['ten']}" if child["ten"] else child["so_hieu"]
                self.add(uri, RDF.type, cls)
                self.add(uri, VLPD.heading, Literal(heading, lang="vi"))
                self.add(uri, RDFS.label, Literal(heading, lang="vi"))
                self.add(uri, VLPD.belongsToItem, item_uri)
                self.add(parent_uri, link, uri)
                self.add_references(uri, None, child["references"])
                walk(child, uri)

        def add_article(dieu: dict, parent_uri: URIRef) -> None:
            code = dieu["so_hieu"]
            self.article_uris[code] += 1
            local = article_local(code)
            if self.article_uris[code] > 1:
                # The source data repeats some codes (e.g. 20.5.TT.74.1);
                # keep both Dieu as separate nodes with the same code.
                local += f"_dup{self.article_uris[code]}"
                stats["duplicate_codes"] += 1
            uri = INST[local]
            title = dieu["tieu_de"] or dieu["ten"]
            # 429 Dieu carry their whole provision in the heading line.
            body = "\n".join(dieu["paragraphs"]) or title
            self.add(uri, RDF.type, VLPD.CodificationArticle)
            self.add(uri, VLPD.codificationNumber, Literal(code, datatype=XSD.string))
            self.add(uri, VLPD.heading, Literal(title, lang="vi"))
            self.add(uri, RDFS.label, Literal(f"Điều {code}: {title}", lang="vi"))
            self.add(uri, VLPD.contentText, Literal(body, lang="vi"))
            self.add(uri, VLPD.belongsToItem, item_uri)
            self.add(parent_uri, VLPD.hasArticle, uri)
            sources = self.sources(dieu["citation"])
            if sources:
                codified = sources[0]
                source_uri = self.add_source_mapping(uri, codified.document, codified.article, body)
                for amending in sources[1:]:
                    amending_uri = self.source_article(amending.document, amending.article)
                    self.add_amendment(
                        source_uri,
                        codified.document,
                        amending_uri,
                        amending.document,
                        amending.actions,
                        amending.effective,
                        consolidated=True,
                    )
                    stats["amendments"] += 1
                # 429 Dieu carry their whole provision in the heading line.
                stats.update(
                    self.add_clauses_and_references(
                        source_uri, codified.document, codified.article, dieu["paragraphs"] or [title]
                    )
                )
            self.add_references(uri, code, dieu["references"])
            stats["articles"] += 1

        walk(tree, item_uri)
        return stats

    def serialize(self, output: Path) -> None:
        self.finish_documents()
        output.parent.mkdir(parents=True, exist_ok=True)
        self.graph.serialize(destination=output, format="turtle", encoding="utf-8")


def resolve_de_muc(args: argparse.Namespace) -> list[dict]:
    """Rows {id, topic_number, topic_name, item_number, item_name, path} for the selection."""
    chu_de = json.loads((INTERIM_DIR / "chu_de.json").read_text(encoding="utf-8"))
    de_muc = json.loads((INTERIM_DIR / "de_muc.json").read_text(encoding="utf-8"))
    index = load_linh_vuc_index()
    rows = []
    for de_muc_id, meta in de_muc.items():
        topic = chu_de.get(meta["ChuDe"])
        if topic is None or de_muc_id not in index:
            continue
        rows.append(
            {
                "id": de_muc_id,
                "code": f"{topic['STT']}.{meta['STT']}",
                "topic_number": int(topic["STT"]),
                "topic_name": topic["Text"],
                "item_number": int(meta["STT"]),
                "item_name": meta["Text"],
                "path": BOPHAPDIEN_DIR / index[de_muc_id]["path"],
            }
        )
    if args.de_muc:
        wanted = set(args.de_muc)
        selected = [r for r in rows if r["code"] in wanted or r["id"] in wanted]
        missing = wanted - {r["code"] for r in selected} - {r["id"] for r in selected}
        if missing:
            raise SystemExit(f"Khong tim thay de muc: {sorted(missing)}")
    else:
        selected = [r for r in rows if r["topic_number"] in set(args.chu_de)]
    return sorted(selected, key=lambda r: (r["topic_number"], r["item_number"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--de-muc", nargs="+", help="De muc codes (20.5) or ids")
    selection.add_argument("--chu-de", nargs="+", type=int, help="Every de muc of these chu de numbers")
    parser.add_argument("--output", type=Path, help="Default: ontology/abox/abox_<de muc>.ttl for one de muc")
    args = parser.parse_args()

    selected = resolve_de_muc(args)
    if args.output is None:
        if len(selected) != 1:
            raise SystemExit("--output is required when building more than one de muc")
        args.output = ABOX_DIR / f"abox_{selected[0]['path'].stem}.ttl"

    builder = AboxBuilder()
    trees = {row["code"]: parse_demuc_nodes(row["path"]) for row in selected}
    for tree in trees.values():
        builder.index_de_muc(tree)
    for row in selected:
        stats = builder.add_de_muc(
            row["path"], row["topic_number"], row["topic_name"], row["item_number"], row["item_name"], trees[row["code"]]
        )
        if stats["articles"] == 0:
            print(f"{row['code']} {row['item_name']}: khong co Dieu nao (chua phap dien hoa), bo qua.")
            continue
        print(f"{row['code']} {row['item_name']}: {dict(stats)}")

    builder.serialize(args.output)
    print(f"Created ABox: {args.output} ({len(builder.graph)} triples)")
    if builder.unparsed_citations:
        print(f"CANH BAO: {len(builder.unparsed_citations)} ghi chu nguon khong tach duoc, vd: {builder.unparsed_citations[:2]}")
    if builder.unknown_issuers:
        print(f"CANH BAO: co quan ban hanh chua co ten day du: {dict(builder.unknown_issuers.most_common(10))}")


if __name__ == "__main__":
    main()

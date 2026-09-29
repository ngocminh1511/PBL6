r"""Build the v4 ABox for the occupational-safety codification sample.

The parser produces the semantic vocabulary from
``vn_legal_ontology_schema_v4.ttl``. JSONL files used by ``labor_rag`` are
generated later by ``labor_rag/ingest/ontology_to_jsonl.py``.

Usage:
    python parse_an_toan_ve_sinh_lao_dong_abox.py \
        --input ..\BoPhapDienDienTu\linh_vuc\lao_dong\an_toan_ve_sinh_lao_dong.html \
        --output abox_an_toan_ve_sinh_lao_dong.ttl
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD

sys.stdout.reconfigure(encoding="utf-8")

VLC = Namespace("https://example.org/vn-legal/core#")
VLD = Namespace("https://example.org/vn-legal/document#")
VLA = Namespace("https://example.org/vn-legal/authority#")
VLR = Namespace("https://example.org/vn-legal/relation#")
VLT = Namespace("https://example.org/vn-legal/time#")
VLPD = Namespace("https://example.org/vn-legal/phapdien#")
VLP = Namespace("https://example.org/vn-legal/provenance#")
INST = Namespace("https://example.org/vn-legal/instance#")

AUTHORITY_MAP = {
    "QuocHoi": ("Auth_QuocHoi", VLA.NationalAssembly, "Quốc hội"),
    "ChinhPhu": ("Auth_ChinhPhu", VLA.Government, "Chính phủ"),
    "ThuTuong": ("Auth_ThuTuong", VLA.PrimeMinister, "Thủ tướng Chính phủ"),
    "BLDTBXH": ("Auth_BLD", VLA.Ministry, "Bộ Lao động - Thương binh và Xã hội"),
    "BQP": ("Auth_BQP", VLA.Ministry, "Bộ Quốc phòng"),
    "BTC": ("Auth_BTC", VLA.Ministry, "Bộ Tài chính"),
    "BCA": ("Auth_BCA", VLA.Ministry, "Bộ Công an"),
    "BYT": ("Auth_BYT", VLA.Ministry, "Bộ Y tế"),
    "BCT": ("Auth_BCT", VLA.Ministry, "Bộ Công Thương"),
    "BGTVT": ("Auth_BGTVT", VLA.Ministry, "Bộ Giao thông vận tải"),
    "BVHTTDL": ("Auth_BVHTTDL", VLA.Ministry, "Bộ Văn hóa, Thể thao và Du lịch"),
}


def clean_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def slug(value: str) -> str:
    """Create a stable ASCII local identifier without changing display text."""
    value = value.replace("Đ", "D").replace("đ", "d")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return value or "unknown"


def parse_vn_date(text: str) -> str | None:
    match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", text)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def authority_keys(number: str) -> list[str]:
    upper = number.upper().replace("Đ", "D")
    aliases = {
        "BLDTBXH": "BLDTBXH",
        "BQP": "BQP",
        "BTC": "BTC",
        "BCA": "BCA",
        "BYT": "BYT",
        "BCT": "BCT",
        "BGTVT": "BGTVT",
        "BVHTTDL": "BVHTTDL",
    }
    return [key for alias, key in aliases.items() if alias in upper]


def get_auth_uri(graph: Graph, key: str) -> URIRef:
    auth_id, auth_type, label = AUTHORITY_MAP[key]
    uri = INST[auth_id]
    graph.add((uri, RDF.type, auth_type))
    graph.add((uri, RDFS.label, Literal(label, lang="vi")))
    return uri


def document_kind(number: str) -> tuple[URIRef, URIRef, str]:
    normalized = number.replace("/", "_")
    upper = number.upper().replace("Đ", "D")
    if "QH" in upper:
        return INST[f"Doc_Law_{slug(normalized)}"], VLD.Law, f"Luật số {number}"
    if "ND" in upper:
        return INST[f"Doc_Decree_{slug(normalized)}"], VLD.Decree, f"Nghị định số {number}"
    if "QD" in upper or "QĐ" in number.upper():
        return INST[f"Doc_Decision_{slug(normalized)}"], VLD.Decision, f"Quyết định số {number}"
    if "TTLT" in upper:
        return INST[f"Doc_JointCircular_{slug(normalized)}"], VLD.JointCircular, f"Thông tư liên tịch số {number}"
    if "TT" in upper:
        return INST[f"Doc_Circular_{slug(normalized)}"], VLD.Circular, f"Thông tư số {number}"
    return INST[f"Doc_Other_{slug(normalized)}"], VLD.OtherLegalDocument, f"Văn bản số {number}"


def assign_authorities(graph: Graph, doc_uri: URIRef, number: str, doc_type: URIRef) -> None:
    upper = number.upper().replace("Đ", "D")
    if doc_type == VLD.Law or "QH" in upper:
        graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, "QuocHoi")))
    elif doc_type == VLD.Decree or "ND-CP" in upper:
        graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, "ChinhPhu")))
    elif doc_type == VLD.Decision or "TTG" in upper:
        graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, "ThuTuong")))
    else:
        for key in authority_keys(number):
            graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, key)))


def ensure_document(graph: Graph, number: str, source_text: str) -> URIRef:
    doc_uri, doc_type, title = document_kind(number)
    graph.add((doc_uri, RDF.type, doc_type))
    graph.add((doc_uri, VLD.documentNumber, Literal(number, datatype=XSD.string)))
    graph.add((doc_uri, VLD.title, Literal(title, lang="vi")))
    assign_authorities(graph, doc_uri, number, doc_type)

    issue_date = parse_vn_date(source_text)
    if issue_date and (doc_uri, VLD.issuedDate, None) not in graph:
        graph.add((doc_uri, VLD.issuedDate, Literal(issue_date, datatype=XSD.date)))

    effective_match = re.search(
        r"(?:có|co)\s+hi(?:ệ|e)u\s+l(?:ự|u)c.*?ng(?:ày|ay)\s+(\d{1,2}/\d{1,2}/\d{4})",
        source_text,
        re.IGNORECASE,
    )
    if effective_match:
        effective_date = parse_vn_date(effective_match.group(1))
        interval = INST[f"Validity_{slug(str(doc_uri))}"]
        graph.add((interval, RDF.type, VLT.LegalValidityInterval))
        graph.add((doc_uri, VLT.hasValidityInterval, interval))
        graph.add((interval, VLT.validFrom, Literal(effective_date, datatype=XSD.date)))
        graph.add((doc_uri, VLD.effectiveDate, Literal(effective_date, datatype=XSD.date)))
    return doc_uri


def extract_document_number(text: str) -> str | None:
    match = re.search(r"\b(\d{1,4}\s*/\s*\d{4}\s*/\s*[A-Za-zĐđ0-9-]+)\b", text)
    if match:
        return re.sub(r"\s+", "", match.group(1))
    if "Luật An toàn, vệ sinh lao động" in text or "Luật An toan, ve sinh lao dong" in text:
        return "84/2015/QH13"
    return None


def add_source_mapping(graph: Graph, article_uri: URIRef, doc_uri: URIRef, article_code: str) -> None:
    source_id = f"SourceArticle_{slug(article_code)}_{slug(str(doc_uri))}"
    source_uri = INST[source_id]
    graph.add((source_uri, RDF.type, VLD.Article))
    graph.add((source_uri, VLD.locatedInDocument, doc_uri))
    graph.add((article_uri, VLPD.codificationOf, source_uri))

    mapping_uri = INST[f"SourceMapping_{slug(article_code)}_{slug(str(doc_uri))}"]
    graph.add((mapping_uri, RDF.type, VLPD.SourceMapping))
    graph.add((article_uri, VLPD.hasSourceMapping, mapping_uri))
    graph.add((mapping_uri, VLPD.mapsToSourceComponent, source_uri))
    graph.add((mapping_uri, VLPD.mapsToSourceDocument, doc_uri))

    statement_hash = hashlib.sha1(f"{article_uri}|{doc_uri}".encode("utf-8")).hexdigest()[:12]
    statement_uri = INST[f"Statement_{statement_hash}"]
    graph.add((statement_uri, RDF.type, VLP.ExtractedStatement))
    graph.add((statement_uri, VLP.sourceDocument, doc_uri))
    graph.add((statement_uri, VLP.sourceComponent, source_uri))


def parse_html_to_abox(html_path: Path, output_ttl: Path, topic_number: int = 20, item_number: int = 5) -> None:
    graph = Graph()
    for prefix, namespace in {
        "vlc": VLC,
        "vld": VLD,
        "vla": VLA,
        "vlr": VLR,
        "vlt": VLT,
        "vlpd": VLPD,
        "vlp": VLP,
        "inst": INST,
    }.items():
        graph.bind(prefix, namespace)

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    topic_uri = INST[f"Topic_{topic_number}"]
    item_uri = INST[f"Item_{topic_number}_{item_number}"]
    heading = soup.find("h3")
    topic_label = clean_text(heading.get_text(" ")) if heading else f"Đề mục {topic_number}.{item_number}"

    graph.add((topic_uri, RDF.type, VLPD.Topic))
    graph.add((topic_uri, VLPD.topicNumber, Literal(topic_number, datatype=XSD.integer)))
    graph.add((topic_uri, VLPD.topicName, Literal(topic_label, lang="vi")))
    graph.add((topic_uri, RDFS.label, Literal(topic_label, lang="vi")))
    graph.add((item_uri, RDF.type, VLPD.CodificationItem))
    graph.add((item_uri, VLPD.itemNumber, Literal(item_number, datatype=XSD.integer)))
    graph.add((item_uri, VLPD.itemName, Literal(topic_label, lang="vi")))
    graph.add((item_uri, RDFS.label, Literal(f"{topic_number}.{item_number} {topic_label}", lang="vi")))
    graph.add((topic_uri, VLPD.hasItem, item_uri))
    graph.add((item_uri, VLPD.partOfTopic, topic_uri))

    content = soup.find("div", class_="_content")
    if content is None:
        raise ValueError("Không tìm thấy thẻ div._content")

    current_article_uri: URIRef | None = None
    current_article_code: str | None = None
    current_parent_uri: URIRef = item_uri
    chapter_count = 0
    section_count = 0
    article_count = 0
    article_sources: dict[URIRef, set[URIRef]] = {}

    for paragraph in content.find_all("p", recursive=False):
        css_class = (paragraph.get("class") or [None])[0]
        text = clean_text(paragraph.get_text(" "))
        if not text:
            continue

        if css_class == "pChuong":
            if re.match(r"^(Chương|CHƯƠNG)\s", text, re.IGNORECASE):
                chapter_count += 1
                current_parent_uri = INST[f"Topic{topic_number}_{item_number}_Chapter_{chapter_count}"]
                graph.add((current_parent_uri, RDF.type, VLPD.CodificationChapter))
                graph.add((current_parent_uri, VLPD.heading, Literal(text, lang="vi")))
                graph.add((current_parent_uri, RDFS.label, Literal(text, lang="vi")))
                graph.add((current_parent_uri, VLPD.belongsToItem, item_uri))
                graph.add((item_uri, VLPD.hasChapter, current_parent_uri))
            elif re.match(r"^Mục\s", text, re.IGNORECASE):
                section_count += 1
                current_parent_uri = INST[f"Topic{topic_number}_{item_number}_Section_{section_count}"]
                graph.add((current_parent_uri, RDF.type, VLPD.CodificationSection))
                graph.add((current_parent_uri, VLPD.heading, Literal(text, lang="vi")))
                graph.add((current_parent_uri, RDFS.label, Literal(text, lang="vi")))
                graph.add((current_parent_uri, VLPD.belongsToItem, item_uri))
                graph.add((item_uri, VLPD.hasSection, current_parent_uri))
            else:
                graph.add((current_parent_uri, VLPD.heading, Literal(text, lang="vi")))
                graph.add((current_parent_uri, RDFS.label, Literal(text, lang="vi")))
            continue

        if css_class == "pDieu":
            match = re.search(r"Điều\s+([0-9A-Za-zĐđ._\\-]+)\s*[.:]?\s*(.*)", text, re.IGNORECASE)
            if not match:
                continue
            current_article_code, article_title = match.groups()
            current_article_code = current_article_code.rstrip(".")
            current_article_uri = INST[f"Article_{slug(current_article_code)}"]
            article_count += 1
            graph.add((current_article_uri, RDF.type, VLPD.CodificationArticle))
            graph.add((current_article_uri, VLPD.codificationNumber, Literal(current_article_code, datatype=XSD.string)))
            graph.add((current_article_uri, VLPD.heading, Literal(article_title, lang="vi")))
            graph.add((current_article_uri, RDFS.label, Literal(f"Điều {current_article_code}: {article_title}", lang="vi")))
            graph.add((current_article_uri, VLPD.belongsToItem, item_uri))
            graph.add((current_parent_uri, VLPD.hasArticle, current_article_uri))
            graph.add((item_uri, VLPD.hasComponent, current_article_uri))
            continue

        if current_article_uri is None or current_article_code is None:
            continue

        if css_class == "pGhiChu":
            number = extract_document_number(text)
            if number:
                doc_uri = ensure_document(graph, number, text)
                article_sources.setdefault(current_article_uri, set()).add(doc_uri)
                add_source_mapping(graph, current_article_uri, doc_uri, current_article_code)
            continue

        if css_class == "pChiDan":
            for target_code in re.findall(r"Điều\s+([0-9][0-9A-Za-zĐđ._\\-]*)", text, re.IGNORECASE):
                target_code = target_code.rstrip(".")
                if target_code == current_article_code:
                    continue
                target_uri = INST[f"Article_{slug(target_code)}"]
                reference_key = hashlib.sha1(f"{current_article_uri}|{target_uri}|{text}".encode("utf-8")).hexdigest()[:12]
                reference_uri = INST[f"CrossReference_{reference_key}"]
                graph.add((reference_uri, RDF.type, VLPD.CrossReference))
                graph.add((reference_uri, VLPD.referenceText, Literal(text, lang="vi")))
                graph.add((reference_uri, VLPD.refersToCodificationComponent, target_uri))
                graph.add((current_article_uri, VLPD.hasCrossReference, reference_uri))
                graph.add((current_article_uri, VLR.cites, target_uri))
            continue

        if css_class == "pNoiDung":
            graph.add((current_article_uri, VLPD.contentText, Literal(text, lang="vi")))

    for article_uri, documents in article_sources.items():
        for doc_uri in documents:
            statement_hash = hashlib.sha1(f"{article_uri}|{doc_uri}".encode("utf-8")).hexdigest()[:12]
            statement_uri = INST[f"Statement_{statement_hash}"]
            for quote in graph.objects(article_uri, VLPD.contentText):
                graph.add((statement_uri, VLP.sourceQuote, quote))

    output_ttl.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=output_ttl, format="turtle", encoding="utf-8")
    print(f"Created ABox: {output_ttl}")
    print(f"Triples: {len(graph)} | chapters: {chapter_count} | sections: {section_count} | articles: {article_count}")


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    project_dir = base_dir.parent
    default_input = project_dir / "BoPhapDienDienTu" / "linh_vuc" / "lao_dong" / "an_toan_ve_sinh_lao_dong.html"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--output", type=Path, default=base_dir / "abox_an_toan_ve_sinh_lao_dong.ttl")
    parser.add_argument("--topic-number", type=int, default=20)
    parser.add_argument("--item-number", type=int, default=5)
    args = parser.parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Input HTML does not exist: {args.input}")
    parse_html_to_abox(args.input, args.output, args.topic_number, args.item_number)


if __name__ == "__main__":
    main()

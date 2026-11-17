import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from rdflib import Graph, Literal, Namespace, RDF, RDFS
from rdflib.namespace import XSD

sys.stdout.reconfigure(encoding="utf-8")

VLC = Namespace("https://example.org/vn-legal/core#")
VLD = Namespace("https://example.org/vn-legal/document#")
VLR = Namespace("https://example.org/vn-legal/relation#")
VLP = Namespace("https://example.org/vn-legal/phapdien#")
VLT = Namespace("https://example.org/vn-legal/time#")
VLA = Namespace("https://example.org/vn-legal/authority#")
INST = Namespace("https://example.org/vn-legal/instance#")

AUTHORITY_MAP = {
    "QuocHoi": ("Auth_QuocHoi", VLA.LegislativeBody, "Quốc hội"),
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


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_vn_date(date_text):
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_text)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def get_auth_uri(graph, key):
    auth_id, auth_type, label = AUTHORITY_MAP[key]
    uri = INST[auth_id]
    if (uri, RDF.type, None) not in graph:
        graph.add((uri, RDF.type, auth_type))
        graph.add((uri, RDFS.label, Literal(label, lang="vi")))
    return uri


def normalize_doc_uri(doc_type, number):
    clean_number = number.replace("/", "_")
    if doc_type == "Luật" or "QH" in number:
        return INST[f"Doc_Luat_{clean_number}"], VLD.Law, f"Luật số {number}"
    if doc_type == "Nghị định" or "NĐ" in number or "ND" in number:
        return INST[f"Doc_ND_{clean_number}"], VLD.Decree, f"Nghị định số {number}"
    if doc_type == "Quyết định" or "QĐ" in number or "QD" in number:
        return INST[f"Doc_QD_{clean_number}"], VLD.Decision, f"Quyết định số {number}"
    if "liên tịch" in doc_type or "TTLT" in number:
        return INST[f"Doc_TTLT_{clean_number}"], VLD.JointCircular, f"Thông tư liên tịch số {number}"
    if "Thông tư" in doc_type or "TT" in number:
        return INST[f"Doc_TT_{clean_number}"], VLD.Circular, f"Thông tư số {number}"
    return None, None, None


def authority_keys(number):
    aliases = {
        "BLĐTBXH": "BLDTBXH", "BLDTBXH": "BLDTBXH",
        "BQP": "BQP", "BTC": "BTC", "BCA": "BCA", "BYT": "BYT",
        "BCT": "BCT", "BGTVT": "BGTVT", "BVHTTDL": "BVHTTDL",
    }
    return [key for alias, key in aliases.items() if alias in number.upper()]


def assign_authorities(graph, doc_uri, number, doc_type):
    if doc_type == VLD.Law or "QH" in number:
        graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, "QuocHoi")))
    elif doc_type == VLD.Decree or "NĐ-CP" in number or "ND-CP" in number:
        graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, "ChinhPhu")))
    elif doc_type == VLD.Decision or "TTg" in number:
        graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, "ThuTuong")))
    else:
        for key in authority_keys(number):
            graph.add((doc_uri, VLR.promulgatedBy, get_auth_uri(graph, key)))


def ensure_document(graph, doc_type_text, number, source_text):
    doc_uri, doc_type, title = normalize_doc_uri(doc_type_text, number)
    if not doc_uri:
        return None
    if (doc_uri, RDF.type, None) not in graph:
        graph.add((doc_uri, RDF.type, doc_type))
        graph.add((doc_uri, RDFS.label, Literal(title, lang="vi")))
        assign_authorities(graph, doc_uri, number, doc_type)
        issue_date = parse_vn_date(source_text)
        if issue_date:
            graph.add((doc_uri, VLT.issueDate, Literal(issue_date, datatype=XSD.date)))
    return doc_uri


def parse_source_note(graph, text, article_uri):
    header = re.search(
        r"\(.*?\b(Luật|Nghị định|Thông tư liên tịch|Thông tư|Quyết định)\s+"
        r"(?:số\s+)?([^\s,\)]+)", text, re.IGNORECASE,
    )
    if header:
        doc_type_text, number = header.groups()
    elif "Luật An toàn, vệ sinh lao động" in text:
        doc_type_text, number = "Luật", "84/2015/QH13"
    else:
        return

    doc_uri = ensure_document(graph, doc_type_text, number, text)
    if not doc_uri:
        return
    graph.add((article_uri, VLD.locatedInDocument, doc_uri))

    effective = re.search(r"có hiệu lực.*?ngày\s+(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    if effective and (doc_uri, VLT.validFrom, None) not in graph:
        graph.add((doc_uri, VLT.validFrom,
                   Literal(parse_vn_date(effective.group(1)), datatype=XSD.date)))


def parse_html_to_abox(html_path, output_ttl):
    graph = Graph()
    for prefix, namespace in {
        "vlc": VLC, "vld": VLD, "vlr": VLR, "vlp": VLP,
        "vlt": VLT, "vla": VLA, "inst": INST,
    }.items():
        graph.bind(prefix, namespace)

    with open(html_path, encoding="utf-8") as html_file:
        soup = BeautifulSoup(html_file.read(), "html.parser")

    topic_uri = INST["Topic_20_5"]
    heading = soup.find("h3")
    topic_label = clean_text(heading.get_text(" ")) if heading else "Đề mục 20.5 An toàn, vệ sinh lao động"
    graph.add((topic_uri, RDF.type, VLP.LegalTopic))
    graph.add((topic_uri, RDFS.label, Literal(topic_label, lang="vi")))

    content = soup.find("div", class_="_content")
    if content is None:
        raise ValueError("Không tìm thấy thẻ div._content")

    current_article_uri = None
    current_article_code = None
    current_chapter_uri = None
    chapter_count = 0
    article_count = 0

    for paragraph in content.find_all("p", recursive=False):
        css_class = (paragraph.get("class") or [None])[0]
        text = clean_text(paragraph.get_text(" "))

        if css_class == "pChuong":
            if re.match(r"^(Chương|CHƯƠNG)\s", text):
                chapter_count += 1
                current_chapter_uri = INST[f"Topic20_5_Chapter_{chapter_count}"]
                graph.add((current_chapter_uri, RDF.type, VLD.Chapter))
                graph.add((current_chapter_uri, RDFS.label, Literal(text, lang="vi")))
                graph.add((current_chapter_uri, VLP.hasTopic, topic_uri))
            elif current_chapter_uri:
                old_label = graph.value(current_chapter_uri, RDFS.label)
                graph.add((current_chapter_uri, RDFS.label,
                           Literal(f"{old_label}: {text}", lang="vi")))

        elif css_class == "pDieu":
            match = re.search(r"Điều\s+([0-9A-ZĐ._\\]+)\.\s*(.*)", text)
            if match:
                current_article_code, article_title = match.groups()
                article_id = current_article_code.replace(".", "_")
                current_article_uri = INST[f"Article_20_5_{article_id}"]
                graph.add((current_article_uri, RDF.type, VLD.Article))
                graph.add((current_article_uri, VLP.phapDienCode,
                           Literal(f"Điều {current_article_code}", datatype=XSD.string)))
                graph.add((current_article_uri, RDFS.label,
                           Literal(f"Điều {current_article_code}: {article_title}", lang="vi")))
                graph.add((current_article_uri, VLP.hasTopic, topic_uri))
                if current_chapter_uri:
                    graph.add((current_chapter_uri, VLD.hasArticle, current_article_uri))
                article_count += 1

        elif css_class == "pGhiChu" and current_article_uri:
            parse_source_note(graph, text, current_article_uri)

        elif css_class == "pChiDan" and current_article_uri:
            for target_code in re.findall(r"Điều\s+([0-9A-ZĐ._\\]+)", text):
                if target_code != current_article_code:
                    target_id = target_code.replace(".", "_")
                    target_uri = INST[f"Article_{target_id}"]
                    graph.add((current_article_uri, VLP.refersToDetail, target_uri))
                    graph.add((current_article_uri, VLR.cites, target_uri))

        elif css_class == "pNoiDung" and current_article_uri:
            graph.add((current_article_uri, VLC.sourceQuote,
                       Literal(text, lang="vi")))

    graph.serialize(destination=output_ttl, format="turtle", encoding="utf-8")
    print(f"--> Đã tạo thành công Knowledge Graph ABox: {output_ttl}")
    print(f"    Tổng số triples: {len(graph)}")
    print(f"    Số chương:       {chapter_count}")
    print(f"    Số điều:         {article_count}")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    parse_html_to_abox(
        base_dir / "linh_vuc" / "linh_vuc" / "lao_dong" / "an_toan_ve_sinh_lao_dong.html",
        base_dir / "abox_an_toan_ve_sinh_lao_dong.ttl",
    )

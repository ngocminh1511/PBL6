"""Project a v4 RDF ABox into the JSONL contracts used by labor_rag.

The ABox remains the source of truth; chunks.jsonl is what gets embedded and
kg_nodes/kg_edges.jsonl what gets loaded into Neo4j.

chunks.jsonl follows chunk schema v5 (docs/structural_jsonl.md): one chunk
per Dieu, identified by the source document number + the article number in
that document, with long Dieu split at MAX_TOKENS bge-m3 tokens.

The graph is the Phap dien ABox plus the ABox of every loaded PDF
(ontology/abox/pdf/*.ttl, written by pdf_to_chunks): a PDF adds its documents,
Dieu, amendments and replacements, so Neo4j holds them too. Chunks are
projected for the Phap dien Dieu only; PDF chunks come from pdf_to_chunks.

Usage (defaults: the Lao dong ABox + PDF ABoxes -> data/processed/lao_dong_v5):
    python -m labor_rag.ingest.ontology_to_jsonl
    python -m labor_rag.ingest.ontology_to_jsonl --max-tokens 0   # no splitting, no tokenizer
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from rdflib import BNode, Graph, Literal, OWL, RDF, RDFS, URIRef

from labor_rag.config import (
    LAO_DONG_ABOX_PATH,
    LAO_DONG_DATASET_ID,
    LAO_DONG_DIR,
    PDF_ABOX_DIR,
    ROOT_DIR,
    SCHEMA_V4_PATH,
)
from labor_rag.ingest.amending import ACTION_ORDER
from labor_rag.ingest.chunk_schema import (
    MAX_TOKENS,
    TokenCounter,
    build_header,
    content_hash,
    heading_number,
    is_so_hieu,
    make_chunk_id,
    make_document_id,
    nfc,
    split_article,
)

sys.stdout.reconfigure(encoding="utf-8")

VLD = "https://example.org/vn-legal/document#"
VLPD = "https://example.org/vn-legal/phapdien#"
VLR = "https://example.org/vn-legal/relation#"
VLT = "https://example.org/vn-legal/time#"
VLP = "https://example.org/vn-legal/provenance#"
VLA = "https://example.org/vn-legal/authority#"
RDFS_URI = str(RDFS)

PREFIXES = {
    VLD: "vld",
    VLPD: "vlpd",
    VLR: "vlr",
    VLT: "vlt",
    VLP: "vlp",
    "https://example.org/vn-legal/core#": "vlc",
    "https://example.org/vn-legal/authority#": "vla",
    "https://example.org/vn-legal/entity#": "vle",
    "https://example.org/vn-legal/instance#": "inst",
    RDFS_URI: "rdfs",
}

ARTICLE_CLASSES = {
    f"{VLPD}CodificationArticle",
    f"{VLD}Article",
}

CLASS_LABELS = {
    "Topic": "ChuDe",
    "CodificationItem": "DeMuc",
    "CodificationChapter": "Chuong",
    "CodificationSection": "Muc",
    "CodificationSubsection": "TieuMuc",
    "CodificationArticle": "Dieu",
    "Article": "Dieu",
    "LegalDocument": "VanBan",
    "Law": "VanBan",
    "Decree": "VanBan",
    "Decision": "VanBan",
    "Circular": "VanBan",
    "JointCircular": "VanBan",
    "Authority": "Authority",
    "Ministry": "Authority",
    "Government": "Authority",
    "NationalAssembly": "Authority",
    "CrossReference": "CrossReference",
    "SourceMapping": "SourceMapping",
    "LegalValidityInterval": "LegalValidityInterval",
    "ExtractedStatement": "ExtractedStatement",
    "AmendmentEvent": "AmendmentEvent",
}

SPECIAL_PROPERTY_KEYS = {
    f"{VLPD}codificationNumber": "mapc",
    f"{VLPD}heading": "ten",
    f"{VLPD}itemName": "ten",
    f"{VLPD}topicName": "ten",
    f"{VLPD}contentText": "text",
    f"{VLD}title": "ten",
    f"{VLD}documentNumber": "document_number",
    f"{VLD}itemNumber": "article_number",
    f"{VLD}issuedDate": "issued_date",
    f"{VLD}effectiveDate": "effective_date",
    f"{VLT}validFrom": "valid_from",
    f"{VLT}validTo": "valid_to",
    f"{VLP}sourceQuote": "source_quote",
    f"{VLR}amendmentAction": "actions",
    f"{VLR}amendmentScope": "scope",
    f"{VLT}amendsAt": "date",
    f"{VLPD}consolidatedInCodification": "consolidated",
}

CONTAINS_LOCALS = {
    "hasComponent",
    "hasPart",
    "hasChapter",
    "hasSection",
    "hasSubsection",
    "hasArticle",
    "hasClause",
    "hasPoint",
}
PART_OF_LOCALS = {"hasParentComponent", "partOfTopic", "belongsToItem"}
REFERENCE_LOCALS = {"cites", "refersToCodificationComponent", "refersToExternalComponent"}
RELATION_NAME_MAP = {
    "promulgatedBy": "ISSUED_BY",
    "locatedInDocument": "LOCATED_IN_DOCUMENT",
    "codificationOf": "DERIVED_FROM",
    "mapsToSourceComponent": "MAPS_TO_SOURCE_COMPONENT",
    "mapsToSourceDocument": "MAPS_TO_SOURCE_DOCUMENT",
    "hasValidityInterval": "HAS_VALIDITY_INTERVAL",
    "hasCrossReference": "HAS_CROSS_REFERENCE",
    "hasSourceMapping": "HAS_SOURCE_MAPPING",
    "amends": "AMENDS",
    "partiallyAmends": "AMENDS",
    "repeals": "REPEALS",
    "replacedBy": "REPLACED_BY",
    "replaces": "REPLACES",
}


def local_name(term: URIRef) -> str:
    text = str(term)
    return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def prefix_name(term: URIRef) -> str:
    text = str(term)
    for namespace, prefix in PREFIXES.items():
        if text.startswith(namespace):
            return prefix
    return "iri"


def safe_property_name(term: URIRef) -> str:
    return f"ontology_{prefix_name(term)}__{re.sub(r'[^A-Za-z0-9_]', '_', local_name(term))}"


def literal_strings(graph: Graph, subject, predicate: URIRef) -> list[str]:
    return [str(value) for value in graph.objects(subject, predicate) if isinstance(value, Literal)]


def first_literal(graph: Graph, subject, predicates: Iterable[URIRef]) -> str | None:
    for predicate in predicates:
        values = literal_strings(graph, subject, predicate)
        if values:
            return values[0]
    return None


def class_uris(graph: Graph, subject) -> list[str]:
    return [str(value) for value in graph.objects(subject, RDF.type) if isinstance(value, URIRef)]


def choose_label(type_uris: list[str]) -> str:
    if f"{VLD}Article" in type_uris or f"{VLD}Clause" in type_uris:
        if f"{VLPD}CodificationArticle" not in type_uris:
            return "SourceComponent"  # a Dieu / khoan of a source document
    for uri in type_uris:
        label = CLASS_LABELS.get(local_name(URIRef(uri)))
        if label:
            return label
    if any(uri.startswith(VLA) for uri in type_uris):
        return "Authority"  # vla:PrimeMinister, vla:President, ...
    return local_name(URIRef(type_uris[0])) if type_uris else "Resource"


def mapc_for(graph: Graph, subject) -> str | None:
    return first_literal(graph, subject, [URIRef(f"{VLPD}codificationNumber")])


def term_id(term, ids: dict[str, str]) -> str:
    key = str(term)
    if key in ids:
        return ids[key]
    if isinstance(term, BNode):
        return f"bnode:{term}"  # deterministic within one parsed graph
    return key


def value_for_property(value: Literal) -> str | int | float | bool:
    if value.datatype and str(value.datatype).endswith("#boolean"):
        return str(value).lower() == "true"
    if value.datatype and str(value.datatype).endswith("#integer"):
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    if value.datatype and str(value.datatype).endswith(("#decimal", "#double", "#float")):
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    return str(value)


def set_multi(mapping: dict, key: str, value) -> None:
    if key not in mapping:
        mapping[key] = value
    elif isinstance(mapping[key], list):
        mapping[key].append(value)
    else:
        mapping[key] = [mapping[key], value]


def relationship_type(predicate: URIRef) -> str:
    local = local_name(predicate)
    if local in CONTAINS_LOCALS:
        return "CONTAINS"
    if local in PART_OF_LOCALS or local == "hasParentComponent":
        return "PART_OF"
    if local in REFERENCE_LOCALS:
        return "REFERS_TO"
    if local in RELATION_NAME_MAP:
        return RELATION_NAME_MAP[local]
    name = re.sub(r"(?<!^)(?=[A-Z])", "_", local).upper()
    return re.sub(r"[^A-Z0-9_]", "_", name) or "RELATED_TO"


def graph_subjects(graph: Graph) -> set:
    values = set(graph.subjects())
    for obj in graph.objects():
        if isinstance(obj, (URIRef, BNode)):
            values.add(obj)
    return values


def find_document_uri(graph: Graph, article) -> str | None:
    for source_component in graph.objects(article, URIRef(f"{VLPD}codificationOf")):
        document = next(graph.objects(source_component, URIRef(f"{VLD}locatedInDocument")), None)
        if document:
            return str(document)
    document = next(graph.objects(article, URIRef(f"{VLD}locatedInDocument")), None)
    return str(document) if document else None


def ancestors(graph: Graph, article, node_by_uri: dict[str, dict]) -> list[dict]:
    """Containing nodes of a Phap dien Dieu, outermost first:
    [DeMuc, (Phan,) Chuong, (Muc, TieuMuc)]."""
    found = []
    current = article
    seen = set()
    parent_predicates = {URIRef(f"{VLPD}{name}") for name in CONTAINS_LOCALS}
    parent_predicates.update({URIRef(f"{VLPD}hasComponent"), URIRef(f"{VLPD}hasArticle")})
    while current not in seen:
        seen.add(current)
        parents = [subject for subject, predicate, obj in graph.triples((None, None, current)) if predicate in parent_predicates]
        if not parents:
            break
        parent = parents[0]
        parent_node = node_by_uri.get(str(parent))
        if parent_node:
            found.append(parent_node)
        current = parent
    found.reverse()
    return found


def source_of(graph: Graph, article, node_by_uri: dict[str, dict]) -> tuple[URIRef | None, str | None, dict | None]:
    """(source vld:Article, its number in the source document, source document
    node), via vlpd:codificationOf -> vld:Article (vld:itemNumber) -> vld:locatedInDocument."""
    for source_component in graph.objects(article, URIRef(f"{VLPD}codificationOf")):
        number = first_literal(graph, source_component, [URIRef(f"{VLD}itemNumber")])
        document = next(graph.objects(source_component, URIRef(f"{VLD}locatedInDocument")), None)
        return source_component, number, node_by_uri.get(str(document)) if document else None
    return None, None, None


def describe_documents(graph: Graph, nodes: dict[str, dict]) -> None:
    """Put document_id and the validity dates on each document node, and
    document_id / article_number / clause_number on each source Dieu and
    khoan, so Neo4j can look them up by (document_id, article_number) like the
    chunks do."""
    for node in nodes.values():
        if node["label"] == "VanBan" and node.get("document_number"):
            node["document_id"] = make_document_id(str(node["document_number"]))
            interval = next(graph.objects(URIRef(node["uri"]), URIRef(f"{VLT}hasValidityInterval")), None)
            if interval is not None:
                node["valid_from"] = first_literal(graph, interval, [URIRef(f"{VLT}validFrom")])
                node["valid_to"] = first_literal(graph, interval, [URIRef(f"{VLT}validTo")])
    for node in nodes.values():
        if node["label"] != "SourceComponent":
            continue
        subject = URIRef(node["uri"])
        document = nodes.get(str(next(graph.objects(subject, URIRef(f"{VLD}locatedInDocument")), "")))
        if document and document.get("document_id"):
            node["document_id"] = document["document_id"]
        if f"{VLD}Clause" in node["class_iris"]:
            node["clause_number"] = node.pop("article_number", None)
            article = next(graph.subjects(URIRef(f"{VLD}hasClause"), subject), None)
            node["article_number"] = first_literal(graph, article, [URIRef(f"{VLD}itemNumber")]) if article else None
    for node in nodes.values():
        if node["label"] == "AmendmentEvent":
            actions = node.get("actions") or []
            node["actions"] = sorted([actions] if isinstance(actions, str) else actions, key=ACTION_ORDER.index)


def version_date(graph: Graph, source_component, document: dict) -> str | None:
    """Latest effective date the Phap dien text of a Dieu reflects: its
    document, and the amendments of this Dieu that Phap dien consolidated
    (vlpd:consolidatedInCodification). An amendment elsewhere in the
    document, or one loaded later from a PDF, does not date it."""
    dates = [document.get("effective_date")]
    for event in graph.objects(source_component, URIRef(f"{VLR}hasAmendment")):
        if first_literal(graph, event, [URIRef(f"{VLPD}consolidatedInCodification")]) == "true":
            dates.append(first_literal(graph, event, [URIRef(f"{VLT}amendsAt")]))
    return max((str(d) for d in dates if d), default=None)


def article_sort_key(chunk: dict) -> tuple:
    number = re.match(r"\d+", chunk["meta_dieu"] or "")
    part = re.search(r":p(\d+)$", chunk["chunk_id"])
    return (chunk["document_id"], int(number.group()) if number else 0, chunk["meta_dieu"] or "", int(part.group(1)) if part else 0)


def repo_relative(path: Path) -> str:
    """Keep machine-specific prefixes out of the tracked manifest."""
    try:
        return path.resolve().relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abox", type=Path, default=LAO_DONG_ABOX_PATH, help="the Phap dien ABox")
    parser.add_argument(
        "--pdf-abox-dir", type=Path, default=PDF_ABOX_DIR, help="ABoxes of loaded PDFs (*.ttl), merged into the graph"
    )
    parser.add_argument("--schema", type=Path, default=SCHEMA_V4_PATH)
    parser.add_argument("--out-dir", type=Path, default=LAO_DONG_DIR)
    parser.add_argument("--dataset-id", default=LAO_DONG_DATASET_ID)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=MAX_TOKENS,
        help="split Dieu longer than this many bge-m3 tokens (0: never split, no tokenizer download)",
    )
    args = parser.parse_args()

    pdf_aboxes = sorted(args.pdf_abox_dir.glob("*.ttl")) if args.pdf_abox_dir.exists() else []
    graph = Graph()
    for path in [args.abox, *pdf_aboxes]:
        graph.parse(path, format="turtle")
    schema = Graph().parse(args.schema, format="turtle")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_terms = graph_subjects(graph)
    mapc_by_subject: dict[str, str] = {}
    used_mapcs: set[str] = set()
    # Sorted so a repeated code always goes to the first Dieu (Article_X sorts
    # before Article_X_dup2); set order would swap them between runs.
    for subject in sorted(all_terms, key=str):
        mapc = mapc_for(graph, subject)
        if mapc and mapc not in used_mapcs:
            mapc_by_subject[str(subject)] = mapc
            used_mapcs.add(mapc)

    ids: dict[str, str] = {}
    for subject in all_terms:
        subject_key = str(subject)
        if subject_key in mapc_by_subject:
            ids[subject_key] = mapc_by_subject[subject_key]
        elif isinstance(subject, BNode):
            ids[subject_key] = f"bnode:{subject}"
        else:
            ids[subject_key] = subject_key

    nodes: dict[str, dict] = {}
    used_literal_predicates: set[str] = set()
    for subject in sorted(all_terms, key=str):
        subject_key = str(subject)
        types = class_uris(graph, subject)
        label = choose_label(types)
        generic: dict = {}
        aliases: dict[str, list] = defaultdict(list)
        for predicate, value in graph.predicate_objects(subject):
            if not isinstance(value, Literal):
                continue
            used_literal_predicates.add(str(predicate))
            value_out = value_for_property(value)
            key = SPECIAL_PROPERTY_KEYS.get(str(predicate), safe_property_name(predicate))
            set_multi(generic, key, value_out)
            if key in {"mapc", "ten", "text", "document_number", "issued_date", "effective_date", "valid_from", "valid_to", "source_quote"}:
                aliases[key].append(value_out)

        mapc = aliases.get("mapc", [None])[0]
        ten = (aliases.get("ten") or aliases.get("label") or [None])[0]
        text_values = aliases.get("text", [])
        text = "\n".join(str(value) for value in text_values) if text_values else None
        node = {
            "id": ids[subject_key],
            "uri": subject_key,
            "label": label,
            "class_iris": types,
            "mapc": mapc,
            "ten": ten,
            "text": text,
            "content_available": bool(text),
            "source": "ontology_v4",
            "dataset_id": args.dataset_id,
        }
        document_uri = find_document_uri(graph, subject)
        if document_uri:
            node["document_uri"] = document_uri
        node.update(generic)
        for reserved_key in ("mapc", "ten", "document_number", "issued_date", "effective_date", "valid_from", "valid_to"):
            if isinstance(node.get(reserved_key), list):
                node[reserved_key] = node[reserved_key][0] if node[reserved_key] else None
        if isinstance(node.get("text"), list):
            node["text"] = "\n".join(str(value) for value in node["text"])
        if isinstance(node.get("source_quote"), list):
            node["source_quote"] = "\n".join(str(value) for value in node["source_quote"])
        nodes[subject_key] = node

    # Ensure every URI object has a stub node, even when the ABox only has a
    # reference to a not-yet-ingested article.
    for subject, predicate, obj in graph:
        if predicate == RDF.type:
            continue
        if isinstance(obj, (URIRef, BNode)) and str(obj) not in nodes:
            nodes[str(obj)] = {
                "id": ids[str(obj)],
                "uri": str(obj),
                "label": "Resource",
                "class_iris": [],
                "mapc": None,
                "ten": None,
                "text": None,
                "content_available": False,
                "source": "ontology_v4",
                "dataset_id": args.dataset_id,
            }

    edges = []
    seen_edges = set()
    for subject, predicate, obj in graph:
        if not isinstance(obj, (URIRef, BNode)):
            continue
        edge_type = "TYPE" if predicate == RDF.type else relationship_type(predicate)
        if predicate == RDF.type:
            continue  # rdf:type is represented by class_iris/label.
        edge = {
            "source": ids[str(subject)],
            "target": ids[str(obj)],
            "type": edge_type,
            "predicate_iri": str(predicate),
            "dataset_id": args.dataset_id,
        }
        key = tuple(edge.items())
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append(edge)
        if edge_type == "CONTAINS":
            inverse = {**edge, "source": edge["target"], "target": edge["source"], "type": "PART_OF"}
            inverse_key = tuple(inverse.items())
            if inverse_key not in seen_edges:
                seen_edges.add(inverse_key)
                edges.append(inverse)
    edges.sort(key=lambda e: (e["source"], e["type"], e["target"], e["predicate_iri"]))

    node_by_uri = nodes
    describe_documents(graph, nodes)
    count = TokenCounter() if args.max_tokens > 0 else None
    chunks = []
    seen_articles: dict[str, str] = {}
    for subject_key, node in sorted(nodes.items()):
        if not any(class_uri in ARTICLE_CLASSES for class_uri in node["class_iris"]):
            continue
        if not node.get("mapc"):
            continue
        source_component, meta_dieu, document = source_of(graph, URIRef(subject_key), node_by_uri)
        if not meta_dieu or not document or not document.get("document_number"):
            raise SystemExit(
                f"{node['id']}: no source article number or document number. Rebuild the ABox "
                "(python -m labor_rag.ingest.build_abox) so each SourceArticle carries vld:itemNumber."
            )
        so_hieu = str(document["document_number"])
        if not is_so_hieu(so_hieu):
            print(f"WARNING: unusual document number {so_hieu!r} for {node['id']}", file=sys.stderr)
        document_id = make_document_id(so_hieu)
        article = make_chunk_id(document_id, meta_dieu)
        if article in seen_articles:
            raise SystemExit(f"{node['id']} and {seen_articles[article]} are both Dieu {meta_dieu} of {so_hieu}")
        seen_articles[article] = node["id"]
        node["article_number"] = meta_dieu
        node["document_id"] = document_id

        parents = ancestors(graph, URIRef(subject_key), node_by_uri)
        de_muc = next((parent.get("ten") for parent in parents if parent["label"] == "DeMuc"), None)
        headings = [parent.get("ten") for parent in parents if parent["label"] != "DeMuc" and parent.get("ten")]
        chuong = next((parent.get("ten") for parent in parents if parent["label"] == "Chuong"), None)
        muc = next((parent.get("ten") for parent in parents if parent["label"] == "Muc"), None)
        meta_de_muc = nfc(str(document.get("ten") or so_hieu))
        context = " > ".join(part for part in [de_muc, meta_de_muc, *headings] if part)

        ten = nfc(node.get("ten") or "")
        # A Dieu without a title of its own has the bare code as heading
        # ("Điều 20.5.TT.4.2."); the codification number stays out of the text.
        if re.fullmatch(rf"Điều\s+{re.escape(str(node.get('mapc')))}\.?", ten):
            ten = ""
        body = nfc(node.get("text") or node.get("source_quote") or "")
        header = build_header(context, meta_dieu, ten)
        if count:
            parts = split_article(header, body, count, args.max_tokens)
        else:
            parts = [("\n".join(part for part in [header, body] if part), None)]
        for index, (text, meta_khoan) in enumerate(parts, start=1):
            chunks.append(
                {
                    "chunk_id": make_chunk_id(document_id, meta_dieu, index if len(parts) > 1 else None),
                    "document_id": document_id,
                    # The Dieu node id in kg_nodes: the codification number, or
                    # the URI for the few repeated codes (KNOWN_ISSUES), so it
                    # stays unique and joins the chunk to Neo4j.
                    "mapc": node["id"],
                    "source": "phap_dien",
                    "ten": ten,
                    "text": text,
                    "meta_de_muc": meta_de_muc,
                    # Chapter/section of the source document: not in the ontology.
                    "meta_chuong": None,
                    "meta_muc": None,
                    # Chapter/section of the Phap dien de muc the Dieu is filed under.
                    "pd_chuong": heading_number(chuong),
                    "pd_muc": heading_number(muc),
                    "meta_dieu": meta_dieu,
                    "meta_khoan": meta_khoan,
                    "effective_from_date": document.get("effective_date"),
                    "effective_to_date": document.get("valid_to"),
                    "version_date": version_date(graph, source_component, document),
                    # Phap dien drops repealed provisions when it is updated; a
                    # replaced document ends through effective_to_date.
                    "still_valid": True,
                    "content_hash": content_hash(body),
                }
            )
    chunks.sort(key=article_sort_key)

    schema_classes = {str(value) for value in schema.subjects(RDF.type, OWL.Class)}
    schema_object_properties = {str(value) for value in schema.subjects(RDF.type, OWL.ObjectProperty)}
    schema_datatype_properties = {str(value) for value in schema.subjects(RDF.type, OWL.DatatypeProperty)}
    used_classes = sorted({class_uri for node in nodes.values() for class_uri in node["class_iris"]})
    used_predicates = sorted({edge["predicate_iri"] for edge in edges})
    manifest = {
        "schema": repo_relative(args.schema),
        "abox": repo_relative(args.abox),
        "pdf_aboxes": [repo_relative(path) for path in pdf_aboxes],
        "dataset_id": args.dataset_id,
        "schema_counts": {
            "classes": len(schema_classes),
            "object_properties": len(schema_object_properties),
            "datatype_properties": len(schema_datatype_properties),
        },
        "used_terms": {
            "classes": used_classes,
            "object_properties": sorted(set(used_predicates) & schema_object_properties),
            "datatype_properties": sorted(used_literal_predicates & schema_datatype_properties),
        },
        "unused_schema_terms_in_sample": {
            "classes": sorted(schema_classes - set(used_classes)),
            "object_properties": sorted(schema_object_properties - set(used_predicates)),
            "datatype_properties": sorted(schema_datatype_properties - used_literal_predicates),
        },
    }
    report = {
        "dataset_id": args.dataset_id,
        "triples": len(graph),
        "nodes": len(nodes),
        "edges": len(edges),
        "chunks": len(chunks),
        "articles": len(seen_articles),
        "split_articles": sum(1 for chunk in chunks if chunk["chunk_id"].endswith(":p1")),
        "edge_types": dict(Counter(edge["type"] for edge in edges)),
        "node_labels": dict(Counter(node["label"] for node in nodes.values())),
        "unprojected_literal_triples": 0,
        "notes": ["rdf:type is represented by label/class_iris rather than a Neo4j edge."],
    }

    def write_jsonl(path: Path, rows: list[dict]) -> None:
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    write_jsonl(args.out_dir / "kg_nodes.jsonl", list(nodes.values()))
    write_jsonl(args.out_dir / "kg_edges.jsonl", edges)
    write_jsonl(args.out_dir / "chunks.jsonl", chunks)
    (args.out_dir / "ontology_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out_dir / "projection_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Wrote projection to {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

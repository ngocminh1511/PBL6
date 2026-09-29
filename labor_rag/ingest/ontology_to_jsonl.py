"""Project a v4 RDF ABox into the JSONL contracts used by labor_rag.

The ABox remains the source of truth. The generated directory is deliberately
separate from the legacy ``labor_rag/data`` outputs so the current pipeline is
not overwritten.

Usage:
    python labor_rag/ingest/ontology_to_jsonl.py \
        --abox ontology/abox_an_toan_ve_sinh_lao_dong.ttl \
        --schema ontology/vn_legal_ontology_schema_v4.ttl \
        --out-dir labor_rag/data/ontology_v4
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

sys.stdout.reconfigure(encoding="utf-8")

VLD = "https://example.org/vn-legal/document#"
VLPD = "https://example.org/vn-legal/phapdien#"
VLR = "https://example.org/vn-legal/relation#"
VLT = "https://example.org/vn-legal/time#"
VLP = "https://example.org/vn-legal/provenance#"
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
}

SPECIAL_PROPERTY_KEYS = {
    f"{VLPD}codificationNumber": "mapc",
    f"{VLPD}heading": "ten",
    f"{VLPD}contentText": "text",
    f"{VLD}title": "ten",
    f"{VLD}documentNumber": "document_number",
    f"{VLD}issuedDate": "issued_date",
    f"{VLD}effectiveDate": "effective_date",
    f"{VLT}validFrom": "valid_from",
    f"{VLT}validTo": "valid_to",
    f"{VLP}sourceQuote": "source_quote",
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
    for uri in type_uris:
        label = CLASS_LABELS.get(local_name(URIRef(uri)))
        if label:
            return label
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


def build_breadcrumb(graph: Graph, article, node_by_uri: dict[str, dict]) -> str:
    parts = []
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
            label = parent_node.get("ten") or parent_node.get("label")
            if label:
                parts.append(str(label))
        current = parent
    parts.reverse()
    return " > ".join(parts)


def main() -> int:
    base_dir = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--abox", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=base_dir / "ontology" / "vn_legal_ontology_schema_v4.ttl")
    parser.add_argument("--out-dir", type=Path, default=base_dir / "labor_rag" / "data" / "ontology_v4")
    parser.add_argument("--dataset-id", default="an_toan_ve_sinh_lao_dong_v4")
    args = parser.parse_args()

    graph = Graph().parse(args.abox, format="turtle")
    schema = Graph().parse(args.schema, format="turtle")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_terms = graph_subjects(graph)
    mapc_by_subject: dict[str, str] = {}
    used_mapcs: set[str] = set()
    for subject in all_terms:
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
        if f"{VLD}Article" in types and f"{VLPD}CodificationArticle" not in types:
            label = "SourceComponent"
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

    node_by_uri = nodes
    chunks = []
    for subject_key, node in sorted(nodes.items()):
        if not any(class_uri in ARTICLE_CLASSES for class_uri in node["class_iris"]):
            continue
        if not node.get("mapc"):
            continue
        breadcrumb = build_breadcrumb(graph, URIRef(subject_key), node_by_uri)
        citation = f"Điều {node['mapc']}"
        body = node.get("text") or node.get("source_quote") or ""
        text = "\n".join(part for part in [breadcrumb, node.get("ten"), citation, body] if part).strip()
        reference_count = sum(1 for edge in edges if edge["source"] == node["id"] and edge["type"] == "REFERS_TO")
        chunks.append(
            {
                "chunk_id": node["id"],
                "mapc": node["id"],
                "uri": node["uri"],
                "ten": node.get("ten"),
                "citation": citation,
                "breadcrumb": breadcrumb,
                "text": text,
                "document_uri": node.get("document_uri"),
                "source": "ontology_v4",
                "dataset_id": args.dataset_id,
                "n_khoan": None,
                "n_refs": reference_count,
            }
        )

    schema_classes = {str(value) for value in schema.subjects(RDF.type, OWL.Class)}
    schema_object_properties = {str(value) for value in schema.subjects(RDF.type, OWL.ObjectProperty)}
    schema_datatype_properties = {str(value) for value in schema.subjects(RDF.type, OWL.DatatypeProperty)}
    used_classes = sorted({class_uri for node in nodes.values() for class_uri in node["class_iris"]})
    used_predicates = sorted({edge["predicate_iri"] for edge in edges})
    manifest = {
        "schema": str(args.schema),
        "abox": str(args.abox),
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

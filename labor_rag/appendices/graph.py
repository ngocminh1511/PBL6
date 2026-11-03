"""Additive appendix ABox/projection; leaves the core TBox and Phap dien data intact."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD

from labor_rag.config import ABOX_DIR, LAO_DONG_DIR, ROOT_DIR, SCHEMA_V4_PATH, SHAPES_V4_PATH
from .catalog import PROCESSED_DIR, load_manifest, read_json, write_json, write_jsonl

VLD = Namespace("https://example.org/vn-legal/document#")
VLR = Namespace("https://example.org/vn-legal/relation#")
VLP = Namespace("https://example.org/vn-legal/provenance#")
INST = Namespace("https://example.org/vn-legal/instance#")
EXTRA_SCHEMA = ROOT_DIR / "ontology/schema/vn_legal_appendix_schema_v1.ttl"
EXTRA_SHAPES = ROOT_DIR / "ontology/schema/vn_legal_appendix_shapes_v1.ttl"
ABOX_PATH = ABOX_DIR / "appendices/appendices.ttl"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def build(output_dir: Path = PROCESSED_DIR, *, validate: bool = True) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    dataset = os.getenv("DATASET_ID", "lao_dong_v5")
    appendices = jsonl(output_dir / "appendices.jsonl")
    artifacts = read_json(output_dir / "artifacts.json", {})
    base = jsonl(LAO_DONG_DIR / "kg_nodes.jsonl")
    documents = {n["document_id"]: n for n in base if n.get("label") == "VanBan" and n.get("document_id")}
    articles = {(n.get("document_id"), str(n.get("article_number"))): n for n in base
                if n.get("label") == "SourceComponent" and n.get("article_number") and not n.get("clause_number") and not n.get("point_number")}
    nodes, edges, missing = {}, [], []
    graph = Graph()
    for prefix, namespace in [("vld",VLD),("vlr",VLR),("vlp",VLP),("inst",INST)]:
        graph.bind(prefix, namespace)
    def uri_for(node):
        return URIRef(node.get("uri") or node["id"])
    def edge(source, target, predicate):
        graph.add((uri_for(source), predicate, uri_for(target)))
        relation = {VLD.hasComponent:"CONTAINS", VLD.locatedInDocument:"LOCATED_IN_DOCUMENT", VLR.citesComponent:"CITES_COMPONENT", VLP.sourceComponent:"SOURCE_COMPONENT",VLR.replacesComponent:"REPLACES_COMPONENT"}[predicate]
        edges.append({"source":source["id"],"target":target["id"],"type":relation,"predicate_iri":str(predicate),"dataset_id":dataset})
    for item in appendices:
        doc_id = item["document_id"]
        document = documents.get(doc_id)
        if not document:
            uri = INST[f"AppendixDocument_{doc_id}"]
            document = {"id":str(uri),"uri":str(uri),"label":"VanBan","dataset_id":dataset,
                        "document_id":doc_id,"document_number":item["document_number"],"ten":item["document_number"]}
            documents[doc_id] = document
            nodes[document["id"]] = document
            graph.add((uri, RDF.type, VLD.LegalDocument))
            graph.add((uri, VLD.documentNumber, Literal(item["document_number"],datatype=XSD.string)))
            graph.add((uri, VLD.title, Literal(item["document_number"],lang="vi")))
        uri = INST[f"Appendix_{doc_id}_{item['key']}"]
        node = {"id":item["appendix_id"],"uri":str(uri),"label":"Appendix","dataset_id":dataset,
                "document_id":doc_id,"appendix_id":item["appendix_id"],"appendix_number":item["number"],
                "kind":item["kind"],"ten":item["title"],"content_available":bool(item["text"]),
                "review_status":item["review_status"],"source_url":item.get("source_url")}
        nodes[node["id"]] = node
        graph.add((uri, RDF.type, VLD.Appendix))
        graph.add((uri, VLD.itemNumber, Literal(item["number"],datatype=XSD.string)))
        graph.add((uri, VLD.heading, Literal(item["title"],lang="vi")))
        graph.add((uri, VLD.contentText, Literal(item["text"],datatype=XSD.string)))
        graph.add((uri, VLD.appendixKind, Literal(item["kind"],datatype=XSD.string)))
        graph.add((uri, VLD.appendixIdentifier, Literal(item["appendix_id"],datatype=XSD.string)))
        edge(document,node,VLD.hasComponent)
        edge(node,document,VLD.locatedInDocument)
        for link in item["article_ids"]:
            source = articles.get((link["document_id"],str(link["article_number"])))
            if source:
                edge(source,node,VLR.citesComponent)
            else:
                missing.append({"appendix_id":item["appendix_id"],"article":link,"reason":"source_article_not_in_base_projection"})
        for artifact_id in item["artifact_ids"]:
            artifact = artifacts.get(artifact_id)
            if not artifact:
                missing.append({"appendix_id":item["appendix_id"],"artifact_id":artifact_id,"reason":"missing_artifact"})
                continue
            file_uri = INST[f"Artifact_{artifact['sha256']}"]
            file_node = {"id":artifact_id,"uri":str(file_uri),"label":"SourceArtifact","dataset_id":dataset,
                         "artifact_id":artifact_id,"sha256":artifact["sha256"],"file_name":artifact["file_name"],
                         "source_url":artifact["source_url"],"storage_backend":"local"}
            nodes[artifact_id] = file_node
            graph.add((file_uri,RDF.type,VLP.SourceArtifact))
            graph.add((file_uri,VLP.checksum,Literal(artifact["sha256"],datatype=XSD.string)))
            graph.add((file_uri,VLP.artifactIdentifier,Literal(artifact_id,datatype=XSD.string)))
            graph.add((file_uri,VLP.sourceURL,Literal(artifact["source_url"],datatype=XSD.anyURI)))
            graph.add((file_uri,VLP.downloadedAt,Literal(artifact["downloaded_at"],datatype=XSD.dateTime)))
            edge(file_node,node,VLP.sourceComponent)
    for item in appendices:
        for old_id in item.get("replaces_appendix_ids",[]):
            if old_id in nodes:
                edge(documents[item["document_id"]],nodes[old_id],VLR.replacesComponent)
            else:
                missing.append({"appendix_id":item["appendix_id"],"replaces":old_id,"reason":"old_appendix_not_extracted"})
    ABOX_PATH.parent.mkdir(parents=True,exist_ok=True)
    graph.serialize(ABOX_PATH,format="turtle")
    unique_edges = {(e["source"],e["target"],e["predicate_iri"]):e for e in edges}
    write_jsonl(output_dir/"kg_nodes.jsonl",sorted(nodes.values(),key=lambda n:n["id"]))
    write_jsonl(output_dir/"kg_edges.jsonl",sorted(unique_edges.values(),key=lambda e:(e["source"],e["target"],e["type"])))
    result = {"triples":len(graph),"nodes":len(nodes),"edges":len(unique_edges),"unresolved_links":missing,"dataset_id":dataset}
    if validate:
        from pyshacl import validate as shacl_validate
        combined = Graph()
        combined.parse(ABOX_DIR/"abox_lao_dong.ttl",format="turtle")
        for path in sorted((ABOX_DIR/"pdf").glob("*.ttl")):
            combined.parse(path,format="turtle")
        combined += graph
        schema = Graph().parse(SCHEMA_V4_PATH,format="turtle").parse(EXTRA_SCHEMA,format="turtle")
        shapes = Graph().parse(SHAPES_V4_PATH,format="turtle").parse(EXTRA_SHAPES,format="turtle")
        conforms, _, report = shacl_validate(combined,shacl_graph=shapes,ont_graph=schema,inference="rdfs")
        result.update({"shacl_conforms":bool(conforms),"shacl_report":str(report)})
    write_json(output_dir/"graph_report.json",result)
    return result


def load(output_dir: Path = PROCESSED_DIR) -> dict:
    """MERGE only the addon entities and relationships into the configured dataset."""
    from neo4j import GraphDatabase
    from labor_rag.ingest.load_neo4j import safe_identifier
    load_dotenv(ROOT_DIR/".env")
    nodes, edges = jsonl(output_dir/"kg_nodes.jsonl"), jsonl(output_dir/"kg_edges.jsonl")
    if not nodes:
        raise ValueError("Build the appendix graph first")
    report = read_json(output_dir/"graph_report.json",{})
    if not report.get("shacl_conforms"):
        raise ValueError("SHACL validation must pass before loading")
    dataset = os.getenv("DATASET_ID","lao_dong_v5")
    driver = GraphDatabase.driver(os.getenv("NEO4J_URI","bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER","neo4j"),os.getenv("NEO4J_PASSWORD","labor_rag_pw")),connection_timeout=10,max_transaction_retry_time=5)
    try:
        driver.verify_connectivity()
        with driver.session(database=os.getenv("NEO4J_DATABASE","neo4j")) as session:
            new_ids={n["id"] for n in nodes}
            external=sorted({e[k] for e in edges for k in ["source","target"] if e[k] not in new_ids})
            missing=session.run("UNWIND $ids AS id OPTIONAL MATCH (n:Entity {id:id,dataset_id:$dataset}) WITH id,n WHERE n IS NULL RETURN id",ids=external,dataset=dataset).value()
            if missing:
                raise ValueError(f"Base graph is missing {len(missing)} referenced nodes; load the matching base dataset first")
            for label in sorted({n["label"] for n in nodes}):
                safe=safe_identifier(label,"Entity")
                session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{safe}) REQUIRE (n.id,n.dataset_id) IS UNIQUE")
                items=[{**n,"dataset_id":dataset} for n in nodes if n["label"]==label]
                session.run(f"UNWIND $items AS item MERGE (n:Entity {{id:item.id,dataset_id:item.dataset_id}}) SET n:{safe} SET n += item",items=items).consume()
            for relation in sorted({e["type"] for e in edges}):
                safe=safe_identifier(relation,"RELATED_TO")
                items=[e for e in edges if e["type"]==relation]
                session.run(f"UNWIND $items AS item MATCH (a:Entity {{id:item.source,dataset_id:$dataset}}), (b:Entity {{id:item.target,dataset_id:$dataset}}) MERGE (a)-[r:{safe} {{predicate_iri:item.predicate_iri,dataset_id:$dataset}}]->(b)",items=items,dataset=dataset).consume()
        result={"status":"loaded","nodes":len(nodes),"edges":len(edges),"dataset_id":dataset}
        write_json(output_dir/"neo4j_load_report.json",result)
        return result
    finally:
        driver.close()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load",action="store_true")
    args=parser.parse_args()
    result=build()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result.get("shacl_conforms"):
        raise SystemExit(1)
    if args.load:
        try:
            print(json.dumps(load(),ensure_ascii=False))
        except Exception as exc:
            write_json(PROCESSED_DIR/"neo4j_load_report.json",{"status":"failed","error_type":type(exc).__name__,"message":str(exc)[:250]})
            raise


if __name__=="__main__":
    main()

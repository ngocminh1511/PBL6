"""Load a JSONL graph projection into Neo4j.

Every node also gets the label :Entity, unique on (id, dataset_id), so edges
are matched through that constraint instead of a scan of all nodes. Source
Dieu / khoan (:SourceComponent) and documents (:VanBan) are indexed on
document_id (+ article_number), the key retrieval looks them up by.

The default data directory is the Lao dong projection:

    python -m labor_rag.ingest.load_neo4j --replace-dataset
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

from labor_rag.config import LAO_DONG_DIR

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()


def safe_identifier(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", value or "")
    if not value or not re.match(r"^[A-Za-z_]", value):
        return fallback
    return value


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=LAO_DONG_DIR)
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "labor_rag_pw"))
    parser.add_argument("--database", default=os.getenv("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--dataset-id", default=os.getenv("DATASET_ID"))
    parser.add_argument(
        "--replace-dataset",
        action="store_true",
        help="Delete only nodes carrying --dataset-id before loading the projection.",
    )
    args = parser.parse_args()

    nodes = read_jsonl(args.data_dir / "kg_nodes.jsonl")
    edges = read_jsonl(args.data_dir / "kg_edges.jsonl")
    if not nodes:
        raise ValueError(f"No graph nodes found in {args.data_dir}")

    dataset_id = args.dataset_id or nodes[0].get("dataset_id")
    if not dataset_id:
        raise ValueError("Nodes carry no dataset_id; pass --dataset-id")
    for node in nodes:
        node.setdefault("dataset_id", dataset_id)
    for edge in edges:
        edge.setdefault("dataset_id", dataset_id)

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    driver.verify_connectivity()
    print(f"Connected to Neo4j database={args.database}.")

    node_labels = sorted({safe_identifier(str(node.get("label")), "Resource") for node in nodes})
    edge_types = sorted({safe_identifier(str(edge.get("type")), "RELATED_TO") for edge in edges})
    with driver.session(database=args.database) as session:
        if args.replace_dataset:
            deleted = session.run(
                "MATCH (n {dataset_id: $dataset_id}) DETACH DELETE n RETURN count(n) AS deleted",
                dataset_id=dataset_id,
            ).single()["deleted"]
            print(f"  replaced dataset {dataset_id}: deleted {deleted} existing nodes")
        for label in ["Entity", *node_labels]:
            session.run(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                "REQUIRE (n.id, n.dataset_id) IS UNIQUE"
            )
        session.run(
            "CREATE INDEX source_component_article IF NOT EXISTS "
            "FOR (n:SourceComponent) ON (n.dataset_id, n.document_id, n.article_number)"
        )
        session.run("CREATE INDEX van_ban_document IF NOT EXISTS FOR (n:VanBan) ON (n.dataset_id, n.document_id)")

        by_label: dict[str, list[dict]] = defaultdict(list)
        for node in nodes:
            node = dict(node)
            node["label"] = safe_identifier(str(node.get("label")), "Resource")
            by_label[node["label"]].append(node)
        for label, items in by_label.items():
            session.run(
                f"UNWIND $items AS item "
                f"MERGE (n:Entity {{id: item.id, dataset_id: item.dataset_id}}) "
                f"SET n:{label} "
                "SET n += item",
                items=items,
            )
            print(f"  loaded {len(items)} :{label} nodes")

        by_type: dict[str, list[dict]] = defaultdict(list)
        for edge in edges:
            edge = dict(edge)
            edge["type"] = safe_identifier(str(edge.get("type")), "RELATED_TO")
            edge["predicate_iri"] = edge.get("predicate_iri") or f"local:{edge['type']}"
            by_type[edge["type"]].append(edge)
        for edge_type, items in by_type.items():
            session.run(
                f"""
                UNWIND $items AS item
                MATCH (a:Entity {{id: item.source, dataset_id: item.dataset_id}}),
                      (b:Entity {{id: item.target, dataset_id: item.dataset_id}})
                MERGE (a)-[r:{edge_type} {{predicate_iri: item.predicate_iri, dataset_id: item.dataset_id}}]->(b)
                SET r += item
                """,
                items=items,
            )
            print(f"  loaded {len(items)} :{edge_type} edges")

    driver.close()
    print("Done. Browse at http://localhost:7474")
    return 0


if __name__ == "__main__":
    sys.exit(main())

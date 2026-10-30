from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase
from src.backend.app.config import settings

class Neo4jRepository:
    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.auth = (settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        self.database = settings.NEO4J_DATABASE
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=self.auth)
        except Exception:
            self.driver = None

    def is_healthy(self) -> bool:
        if not self.driver:
            return False
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS num")
                return result.single()["num"] == 1
        except Exception:
            return False

    def count_nodes(self) -> int:
        if not self.driver:
            return 0
        try:
            with self.driver.session(database=self.database) as session:
                res = session.run("MATCH (n) RETURN count(n) AS cnt")
                record = res.single()
                return record["cnt"] if record else 0
        except Exception:
            return 0

    def count_edges(self) -> int:
        if not self.driver:
            return 0
        try:
            with self.driver.session(database=self.database) as session:
                res = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
                record = res.single()
                return record["cnt"] if record else 0
        except Exception:
            return 0

    def get_subgraph_for_article(self, document_id: str, article_number: str) -> Dict[str, Any]:
        """Fetches subgraph around a specific article (hierarchy + refers_to edges)."""
        nodes = []
        edges = []
        if not self.driver:
            return {"nodes": nodes, "edges": edges}

        query = """
        MATCH (d:Dieu {document_id: $doc_id, article_number: $article_num})
        OPTIONAL MATCH (d)-[r:PART_OF]->(p)
        OPTIONAL MATCH (c)-[r2:PART_OF]->(d)
        OPTIONAL MATCH (d)-[r3:REFERS_TO]->(target)
        RETURN d, p, r, c, r2, target, r3
        LIMIT 25
        """
        try:
            with self.driver.session(database=self.database) as session:
                results = session.run(query, doc_id=document_id, article_num=article_number)
                seen_nodes = set()
                for rec in results:
                    for node_key in ["d", "p", "c", "target"]:
                        node = rec.get(node_key)
                        if node and node.element_id not in seen_nodes:
                            seen_nodes.add(node.element_id)
                            labels = list(node.labels)
                            nodes.append({
                                "id": node.get("id") or node.element_id,
                                "label": labels[0] if labels else "Node",
                                "title": node.get("ten") or node.get("id") or "Node",
                                "document_id": node.get("document_id"),
                                "article_number": node.get("article_number")
                            })
                    for rel_key in ["r", "r2", "r3"]:
                        rel = rec.get(rel_key)
                        if rel:
                            edges.append({
                                "source": rel.start_node.get("id") or rel.start_node.element_id,
                                "target": rel.end_node.get("id") or rel.end_node.element_id,
                                "type": rel.type
                            })
        except Exception:
            pass

        return {"nodes": nodes, "edges": edges}

neo4j_repo = Neo4jRepository()


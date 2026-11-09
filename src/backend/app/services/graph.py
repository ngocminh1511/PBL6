"""Presentation of a Neo4j neighbourhood for the inspector graph tab.

The graph stores one legal Dieu twice: as a codification node (`Dieu`) and as the
source-document node (`SourceComponent`) it was derived from, plus a clause node per
khoan, each with inverse and bookkeeping edges. Shown as is, the tab lists several nodes
all titled with the bare article number. This module merges and labels them; it never
invents nodes or edges that the query did not return.
"""

# Technical rows linking the two layers; the merge below already shows that link.
HIDDEN_LABELS = {"SourceMapping"}
UNNAMED_LABELS = {"ExtractedStatement": "Mệnh đề trích xuất", "CrossReference": "Tham chiếu"}


def node_title(props, focus_document=None):
    """'Điều 49 · Điều kiện hưởng', 'Điều 9 khoản 2 điểm c', or the node's own name."""
    article = props.get("article_number")
    if props.get("label") in {"Dieu", "SourceComponent"} and article:
        title = f"Điều {article}"
        if props.get("clause_number"):
            title += f" khoản {props['clause_number']}"
        if props.get("point_number"):
            title += f" điểm {props['point_number']}"
        if props.get("label") == "Dieu" and props.get("ten"):
            title += f" · {props['ten']}"
        document = props.get("document_id")
        if document and focus_document and document != focus_document:
            title += f" ({document})"
        return title
    name = props.get("ten") or props.get("ontology_vlpd__referenceText") or props.get("ontology_rdfs__label")
    if name:
        return name
    identity = props.get("id") or ""
    kind = UNNAMED_LABELS.get(props.get("label"))
    # Several unnamed nodes of one kind must stay distinguishable: keep the end of their id.
    return f"{kind} #{identity[-6:]}" if kind else identity


def _natural(value):
    return (0, int(value), "") if str(value or "").isdigit() else (1, 0, str(value or ""))


def _rank(node, focus_document):
    props = node["props"]
    in_focus = props.get("document_id") == focus_document
    article_level = props.get("label") in {"Dieu", "SourceComponent"} and not (
        props.get("clause_number") or props.get("point_number"))
    return (0 if in_focus and article_level else 1 if in_focus else 2,
            _natural(props.get("article_number")), _natural(props.get("clause_number")),
            _natural(props.get("point_number")))


def build_graph(nodes, relations, focus_document=None):
    """`nodes`: {key: {"labels", "props"}}; `relations`: [{"type", "source", "target"}].

    Returns {"nodes": [...], "edges": [...]} in the GraphResponse shape."""
    hidden = {key for key, node in nodes.items()
              if HIDDEN_LABELS & (set(node["labels"]) | {node["props"].get("label")})}

    # A Dieu and the SourceComponent article it is DERIVED_FROM are one article.
    alias = {}
    for relation in relations:
        source, target = nodes.get(relation["source"]), nodes.get(relation["target"])
        if (relation["type"] == "DERIVED_FROM" and source and target
                and source["props"].get("label") == "Dieu"
                and target["props"].get("label") == "SourceComponent"):
            alias[relation["target"]] = relation["source"]

    def canonical(key):
        return alias.get(key, key)

    kept = {}
    for key, node in nodes.items():
        if key not in hidden and key not in alias:
            kept[key] = node

    edges, seen = [], set()
    contains = {(canonical(r["source"]), canonical(r["target"])) for r in relations if r["type"] == "CONTAINS"}
    for relation in relations:
        source, target = canonical(relation["source"]), canonical(relation["target"])
        if source == target or source in hidden or target in hidden:
            continue
        if source not in kept or target not in kept:
            continue
        kind = relation["type"]
        if kind == "PART_OF" and (target, source) in contains:
            continue  # the inverse of CONTAINS: one fact
        if kind == "LOCATED_IN_DOCUMENT" and (
                kept[source]["props"].get("clause_number") or kept[source]["props"].get("point_number")):
            continue  # implied by the article that contains the khoan
        identity = (source, target, kind)
        if identity in seen:
            continue
        seen.add(identity)
        edges.append({"source": source, "target": target, "type": kind})

    ordered = sorted(kept.items(), key=lambda item: _rank(item[1], focus_document))
    return {
        "nodes": [{
            "id": key, "label": node["props"].get("label") or "component",
            "title": node_title(node["props"], focus_document),
            "article_number": node["props"].get("article_number"),
            "document_id": node["props"].get("document_id"),
        } for key, node in ordered],
        "edges": edges,
    }

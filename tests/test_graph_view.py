from src.backend.app.services.graph import build_graph, node_title

DOC = "38-2013-qh13"


def node(key, label, **props):
    return key, {"labels": ["Entity", label], "props": {"id": key, "label": label, "document_id": DOC, **props}}


def graph():
    nodes = dict([
        node("dieu", "Dieu", ten="Điều kiện hưởng", article_number="49"),
        node("article", "SourceComponent", article_number="49"),
        node("k1", "SourceComponent", article_number="49", clause_number="1"),
        node("k2", "SourceComponent", article_number="49", clause_number="2"),
        node("mapping", "SourceMapping"),
        node("doc", "VanBan", ten="Luật số 38/2013/QH13"),
        node("other", "SourceComponent", article_number="43", clause_number="1"),
    ])
    nodes["other"]["props"]["document_id"] = "other-doc"
    relations = [
        {"type": "DERIVED_FROM", "source": "dieu", "target": "article"},
        {"type": "HAS_SOURCE_MAPPING", "source": "dieu", "target": "mapping"},
        {"type": "CONTAINS", "source": "article", "target": "k1"},
        {"type": "PART_OF", "source": "k1", "target": "article"},
        {"type": "CONTAINS", "source": "article", "target": "k2"},
        {"type": "PART_OF", "source": "k2", "target": "article"},
        {"type": "LOCATED_IN_DOCUMENT", "source": "article", "target": "doc"},
        {"type": "LOCATED_IN_DOCUMENT", "source": "k1", "target": "doc"},
        {"type": "CITES_COMPONENT", "source": "k1", "target": "other"},
        {"type": "CITES_COMPONENT", "source": "k1", "target": "other"},
    ]
    return nodes, relations


def test_dieu_and_its_source_article_are_one_node_with_readable_titles():
    nodes, relations = graph()
    result = build_graph(nodes, relations, focus_document=DOC)
    titles = [n["title"] for n in result["nodes"]]
    assert titles[0] == "Điều 49 · Điều kiện hưởng"
    assert "Điều 49 khoản 1" in titles and "Điều 49 khoản 2" in titles
    assert len(titles) == len(set(titles))
    assert "Điều 43 khoản 1 (other-doc)" in titles
    assert {n["id"] for n in result["nodes"]} == {"dieu", "k1", "k2", "doc", "other"}


def test_redundant_and_technical_edges_are_dropped_but_real_ones_kept():
    nodes, relations = graph()
    edges = {(e["source"], e["target"], e["type"]) for e in build_graph(nodes, relations, DOC)["edges"]}
    assert edges == {
        ("dieu", "k1", "CONTAINS"), ("dieu", "k2", "CONTAINS"),
        ("dieu", "doc", "LOCATED_IN_DOCUMENT"), ("k1", "other", "CITES_COMPONENT"),
    }


def test_nodes_without_article_keep_their_own_name():
    assert node_title({"label": "VanBan", "ten": "Thông tư số 28/2015/TT-BLĐTBXH"}) == "Thông tư số 28/2015/TT-BLĐTBXH"
    assert node_title({"label": "SourceComponent", "article_number": "9", "clause_number": "2",
                       "point_number": "c", "document_id": DOC}, DOC) == "Điều 9 khoản 2 điểm c"


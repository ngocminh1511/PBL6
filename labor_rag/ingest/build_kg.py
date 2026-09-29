"""Build Knowledge Graph nodes/edges from parsed de-muc trees.

Node labels: DeMuc, Chuong, Muc, Dieu.
Edge types:
  CONTAINS  parent -> child   (DeMuc->Chuong, Chuong->Muc, Chuong->Dieu, Muc->Dieu)
  PART_OF   child  -> parent  (inverse of CONTAINS, stored explicitly so both
                                top-down and bottom-up traversal are single-hop)
  REFERS_TO Dieu -> Dieu      (from pChiDan cross-reference links)

REFERS_TO targets that fall outside the set of de-muc files actually parsed
(cross-domain references -- see analysis in the plan) are resolved via the
global data/mapc_index.json (built from jdAllTree, which covers the ENTIRE
Bo Phap Dien, not just the ingested domain) and stored as a stub Dieu node
with content_available=false, so the edge still exists for graph traversal /
explanation even before that domain is ingested.

Output (JSON Lines, one object per line -- easy to UNWIND/MERGE into Neo4j):
  data/kg_nodes.jsonl  {"id", "label", **properties}
  data/kg_edges.jsonl  {"source", "target", "type"}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(r"D:\Work\Learn\HK7_2026-2027\PBL6\labor_rag\data")
PARSED_DIR = DATA_DIR / "parsed"


def main() -> None:
    mapc_index = json.loads((DATA_DIR / "mapc_index.json").read_text(encoding="utf-8"))
    de_muc_meta = json.loads((DATA_DIR / "de_muc.json").read_text(encoding="utf-8"))

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    known_dieu_mapc: set[str] = set()

    def add_node(mapc: str, label: str, **props) -> None:
        if mapc in nodes:
            nodes[mapc].update({k: v for k, v in props.items() if v is not None})
        else:
            nodes[mapc] = {"id": mapc, "label": label, **props}

    def add_edge(source: str, target: str, etype: str) -> None:
        edges.append({"source": source, "target": target, "type": etype})

    parsed_paths = sorted(PARSED_DIR.glob("*.json"))
    for path in parsed_paths:
        tree = json.loads(path.read_text(encoding="utf-8"))
        de_muc_id = tree["de_muc_id"]
        de_muc_so = tree["de_muc_so"]
        de_muc_ten = de_muc_meta.get(de_muc_id, {}).get("Text", "")
        de_muc_node_id = f"demuc:{de_muc_id}"
        add_node(de_muc_node_id, "DeMuc", de_muc_id=de_muc_id, so_hieu=de_muc_so, ten=de_muc_ten)

        def add_dieu(dieu: dict, parent_id: str):
            add_node(
                dieu["mapc"],
                "Dieu",
                ten=dieu["ten"],
                citation=dieu["citation"],
                de_muc_id=de_muc_id,
                content_available=True,
            )
            known_dieu_mapc.add(dieu["mapc"])
            add_edge(parent_id, dieu["mapc"], "CONTAINS")
            add_edge(dieu["mapc"], parent_id, "PART_OF")
            for ref in dieu["references"]:
                edges.append(
                    {
                        "source": dieu["mapc"],
                        "target": ref["target_mapc"],
                        "type": "REFERS_TO",
                        "display_text": ref["display_text"],
                    }
                )

        for dieu in tree["top_level_dieu"]:
            add_dieu(dieu, de_muc_node_id)

        for chuong in tree["chuong"]:
            add_node(
                chuong["mapc"],
                "Chuong",
                so_hieu=chuong["so_hieu"],
                ten=chuong["ten"],
                de_muc_id=de_muc_id,
            )
            add_edge(de_muc_node_id, chuong["mapc"], "CONTAINS")
            add_edge(chuong["mapc"], de_muc_node_id, "PART_OF")

            for dieu in chuong["dieu"]:
                add_dieu(dieu, chuong["mapc"])

            for muc in chuong["muc"]:
                add_node(
                    muc["mapc"],
                    "Muc",
                    so_hieu=muc["so_hieu"],
                    ten=muc["ten"],
                    de_muc_id=de_muc_id,
                )
                add_edge(chuong["mapc"], muc["mapc"], "CONTAINS")
                add_edge(muc["mapc"], chuong["mapc"], "PART_OF")
                for dieu in muc["dieu"]:
                    add_dieu(dieu, muc["mapc"])

    # Resolve REFERS_TO targets not covered by the ingested de-muc files as stub nodes.
    # Prefer the global mapc_index (from jdAllTree); if a target isn't indexed there
    # either (seen for: de-muc not yet "phap dien hoa", e.g. "Giao duc nghe nghiep",
    # or Muc-level anchors, which jdAllTree does not list), fall back to the display
    # title pChiDan already carries, so the edge/node still exists with a real title.
    n_stub_indexed = 0
    n_stub_from_display = 0
    for edge in edges:
        if edge["type"] != "REFERS_TO":
            continue
        target = edge["target"]
        if target in known_dieu_mapc:
            continue
        info = mapc_index.get(target)
        if info is not None:
            add_node(target, "Dieu", ten=info["TEN"], de_muc_id=info["DeMucID"], content_available=False)
            n_stub_indexed += 1
        else:
            add_node(target, "Dieu", ten=edge["display_text"], de_muc_id=None, content_available=False)
            n_stub_from_display += 1

    (DATA_DIR / "kg_nodes.jsonl").write_text(
        "\n".join(json.dumps(node, ensure_ascii=False) for node in nodes.values()),
        encoding="utf-8",
    )
    (DATA_DIR / "kg_edges.jsonl").write_text(
        "\n".join(json.dumps(edge, ensure_ascii=False) for edge in edges), encoding="utf-8"
    )

    n_by_label: dict[str, int] = {}
    for node in nodes.values():
        n_by_label[node["label"]] = n_by_label.get(node["label"], 0) + 1
    n_refers_to = sum(1 for e in edges if e["type"] == "REFERS_TO")

    print(f"Nodes: {len(nodes)} -> {n_by_label}")
    print(f"Edges: {len(edges)} (REFERS_TO: {n_refers_to})")
    print(f"REFERS_TO stub targets resolved via mapc_index: {n_stub_indexed}")
    print(f"REFERS_TO stub targets resolved via pChiDan display_text (not in mapc_index): {n_stub_from_display}")
    print(f"Wrote {DATA_DIR / 'kg_nodes.jsonl'} and {DATA_DIR / 'kg_edges.jsonl'}")


if __name__ == "__main__":
    main()

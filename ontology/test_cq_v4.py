"""Small v4 competency-question regression suite for the generated ABox."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rdflib import Graph

sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--abox", type=Path, default=base_dir / "abox_an_toan_ve_sinh_lao_dong.ttl")
    args = parser.parse_args()

    graph = Graph().parse(args.abox, format="turtle")
    cases = [
        (
            "CQ20",
            "Luật 84/2015/QH13 được biểu diễn là Law",
            """
            PREFIX vld: <https://example.org/vn-legal/document#>
            SELECT ?type WHERE {
                ?doc vld:documentNumber ?number ; a ?type .
                FILTER(str(?number) = "84/2015/QH13")
                FILTER(?type = vld:Law)
            }
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ21",
            "Nghị định 39/2016/NĐ-CP có cơ quan ban hành",
            """
            PREFIX vld: <https://example.org/vn-legal/document#>
            PREFIX vlr: <https://example.org/vn-legal/relation#>
            SELECT ?authority WHERE {
                ?doc vld:documentNumber ?number ; vlr:promulgatedBy ?authority .
                FILTER(str(?number) = "39/2016/NĐ-CP")
            }
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ24",
            "Luật 84/2015/QH13 có ngày ban hành",
            """
            PREFIX vld: <https://example.org/vn-legal/document#>
            SELECT ?date WHERE {
                ?doc vld:documentNumber ?number ; vld:issuedDate ?date .
                FILTER(str(?number) = "84/2015/QH13")
            }
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ25",
            "Đề mục có chương và điều",
            """
            PREFIX vlpd: <https://example.org/vn-legal/phapdien#>
            SELECT ?chapter ?article WHERE {
                ?item a vlpd:CodificationItem ; vlpd:hasChapter ?chapter .
                ?chapter vlpd:hasArticle ?article .
            }
            LIMIT 1
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ26",
            "Điều pháp điển ánh xạ tới văn bản nguồn",
            """
            PREFIX vlpd: <https://example.org/vn-legal/phapdien#>
            PREFIX vld: <https://example.org/vn-legal/document#>
            SELECT ?document WHERE {
                ?article vlpd:codificationNumber ?code ; vlpd:codificationOf ?source .
                ?source vld:locatedInDocument ?document .
            }
            LIMIT 1
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ29",
            "Điều có quan hệ dẫn chiếu",
            """
            PREFIX vlpd: <https://example.org/vn-legal/phapdien#>
            SELECT ?target WHERE {
                ?article vlpd:hasCrossReference ?reference .
                ?reference vlpd:refersToCodificationComponent ?target .
            }
            LIMIT 1
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ34",
            "Có quan hệ cites để truy hồi graph",
            """
            PREFIX vlr: <https://example.org/vn-legal/relation#>
            SELECT ?target WHERE { ?article vlr:cites ?target } LIMIT 1
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ45",
            "Điều có mã và nhãn",
            """
            PREFIX vlpd: <https://example.org/vn-legal/phapdien#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?code ?label WHERE {
                ?article vlpd:codificationNumber ?code ; rdfs:label ?label .
            }
            LIMIT 1
            """,
            lambda rows: bool(rows),
        ),
        (
            "CQ46",
            "Điều có nội dung để tạo chunk",
            """
            PREFIX vlpd: <https://example.org/vn-legal/phapdien#>
            SELECT ?text WHERE {
                ?article vlpd:contentText ?text .
                FILTER(strlen(str(?text)) > 20)
            }
            LIMIT 1
            """,
            lambda rows: bool(rows),
        ),
    ]

    passed = 0
    for case_id, title, query, check in cases:
        try:
            rows = list(graph.query(query))
            ok = check(rows)
            status = "PASS" if ok else "FAIL"
        except Exception as exc:  # pragma: no cover - diagnostic output
            rows = []
            status = f"ERROR: {exc}"
            ok = False
        passed += int(ok)
        print(f"{case_id:<6} {status:<8} {title}")

    print(f"Result: {passed}/{len(cases)} competency questions passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())

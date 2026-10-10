"""Validate an ABox against schema v4 and SHACL shapes.

Usage:
    python scripts/validate_abox.py --report ontology/reports/validation_report.json
    (default --abox: ontology/abox/abox_lao_dong.ttl)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdflib import Graph, Namespace

try:
    from pyshacl import validate
except ImportError as exc:  # pragma: no cover - exercised when dependencies are missing
    raise SystemExit("pyshacl is required. Install requirements before validating an ABox.") from exc

SH = Namespace("http://www.w3.org/ns/shacl#")


def main() -> int:
    ontology_dir = Path(__file__).resolve().parents[1] / "ontology"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=ontology_dir / "schema" / "vn_legal_ontology_schema_v4.ttl")
    parser.add_argument("--shapes", type=Path, default=ontology_dir / "schema" / "vn_legal_ontology_shapes_v4.ttl")
    parser.add_argument("--abox", type=Path, default=ontology_dir / "abox" / "abox_lao_dong.ttl")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    data_graph = Graph().parse(args.abox, format="turtle")
    schema_graph = Graph().parse(args.schema, format="turtle")
    shapes_graph = Graph().parse(args.shapes, format="turtle")
    conforms, results_graph, results_text = validate(
        data_graph=data_graph,
        shacl_graph=shapes_graph,
        ont_graph=schema_graph,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=True,
    )

    results = []
    for result in results_graph.subjects(RDF_TYPE, SH.ValidationResult):
        focus = results_graph.value(result, SH.focusNode)
        path = results_graph.value(result, SH.resultPath)
        message = results_graph.value(result, SH.resultMessage)
        severity = results_graph.value(result, SH.resultSeverity)
        results.append(
            {
                "focus_node": str(focus) if focus else None,
                "path": str(path) if path else None,
                "message": str(message) if message else None,
                "severity": str(severity) if severity else None,
            }
        )

    report = {
        "conforms": bool(conforms),
        "triples": len(data_graph),
        "violations": len(results),
        "results": results,
    }
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("PASS" if conforms else "FAIL")
    print(f"Triples: {len(data_graph)} | validation results: {len(results)}")
    if results:
        print(results_text)
    return 0 if conforms else 1


RDF_TYPE = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#").type


if __name__ == "__main__":
    sys.exit(main())

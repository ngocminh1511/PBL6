"""Build separate ontology v4 ABoxes for the remaining labor de muc.

The safety and hygiene labor item (20.5) has its own legacy parser.  This
script uses the canonical parser from ``labor_rag.ingest.build_abox`` for the
other codified labor items, so article hierarchy, source mappings, citations,
and duplicate article codes are handled consistently.

Usage:
    python ontology/parse_lao_dong_con_lai_abox.py
    python ontology/parse_lao_dong_con_lai_abox.py --de-muc 20.2 20.3
    python ontology/parse_lao_dong_con_lai_abox.py --output-dir ontology/abox
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from labor_rag.config import ABOX_DIR
from labor_rag.ingest.build_abox import AboxBuilder, resolve_de_muc

sys.stdout.reconfigure(encoding="utf-8")

REMAINING_DE_MUC = ("20.2", "20.3", "20.4")


def build_aboxes(de_muc: list[str], output_dir: Path) -> list[Path]:
    """Build one ABox per selected de muc and return the generated paths."""

    selected = resolve_de_muc(argparse.Namespace(chu_de=None, de_muc=de_muc))
    if not selected:
        raise SystemExit("Khong tim thay de muc nao de parse.")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for row in selected:
        output = output_dir / f"abox_{row['code'].replace('.', '_')}_{row['path'].stem}.ttl"
        builder = AboxBuilder()
        stats = builder.add_de_muc(
            row["path"],
            row["topic_number"],
            row["topic_name"],
            row["item_number"],
            row["item_name"],
        )
        if stats["articles"] == 0:
            print(f"{row['code']} {row['item_name']}: khong co Dieu nao, bo qua.")
            continue

        builder.serialize(output)
        outputs.append(output)
        print(f"{row['code']} {row['item_name']}: {dict(stats)}")
        print(f"Created ABox: {output} ({len(builder.graph)} triples)")
        if builder.unparsed_citations:
            print(
                f"CANH BAO: {len(builder.unparsed_citations)} ghi chu nguon "
                f"khong tach duoc, vd: {builder.unparsed_citations[:2]}"
            )
        if builder.unknown_issuers:
            print(
                "CANH BAO: co quan ban hanh chua co ten day du: "
                f"{dict(builder.unknown_issuers.most_common(10))}"
            )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--de-muc",
        nargs="+",
        default=list(REMAINING_DE_MUC),
        help="Ma de muc can parse (mac dinh: 20.2 20.3 20.4)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ABOX_DIR,
        help="Thu muc chua cac ABox rieng (mac dinh: ontology/abox)",
    )
    args = parser.parse_args()
    build_aboxes(args.de_muc, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
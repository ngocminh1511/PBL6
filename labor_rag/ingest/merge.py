"""Decide which chunks to write when new chunks meet the ones already indexed
(docs/structural_jsonl.md, section 7).

Decisions are per Dieu (article_id: "<document_id>:d35", or ":pl1" for an
appendix), never per part, so a Dieu never mixes parts from two sources:

- only in the new set: write it;
- in both: the side with the later version_date wins; on a tie Phap dien
  wins over a PDF, and a reload from the same source replaces;
- when the new side wins, every old part is deleted first, since the two
  sides may split the Dieu into a different number of parts;
- a Dieu only in the old set is kept, with a warning (often an OCR miss).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from labor_rag.ingest.chunk_schema import article_id, part_number

PHAP_DIEN = "phap_dien"


@dataclass
class UpsertPlan:
    upsert: list[dict] = field(default_factory=list)  # new chunks to embed and write
    delete: list[str] = field(default_factory=list)  # chunk_ids of old parts to remove first
    kept: list[str] = field(default_factory=list)  # article ids where the old version wins
    unchanged: list[str] = field(default_factory=list)  # article ids identical in both
    warnings: list[str] = field(default_factory=list)


def group_by_article(chunks: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        groups[article_id(chunk["chunk_id"])].append(chunk)
    for parts in groups.values():
        parts.sort(key=lambda chunk: part_number(chunk["chunk_id"]))
    return groups


def new_wins(new: dict, old: dict) -> bool:
    new_date, old_date = new.get("version_date") or "", old.get("version_date") or ""
    if new_date != old_date:
        return new_date > old_date
    if new.get("source") == old.get("source"):
        return True  # reloading the same source replaces it
    return new.get("source") == PHAP_DIEN


def plan_upsert(existing: list[dict], new: list[dict]) -> UpsertPlan:
    """existing: payloads already indexed for the documents in ``new``."""
    plan = UpsertPlan()
    old_groups = group_by_article(existing)
    new_groups = group_by_article(new)

    for key, new_parts in new_groups.items():
        old_parts = old_groups.get(key)
        if not old_parts:
            plan.upsert += new_parts
            continue
        if [(c["chunk_id"], c.get("text")) for c in old_parts] == [(c["chunk_id"], c.get("text")) for c in new_parts] and (
            old_parts[0].get("version_date") == new_parts[0].get("version_date")
        ):
            plan.unchanged.append(key)
            continue
        if new_wins(new_parts[0], old_parts[0]):
            plan.delete += [c["chunk_id"] for c in old_parts]
            plan.upsert += new_parts
        else:
            plan.kept.append(key)

    for key, old_parts in old_groups.items():
        if key not in new_groups:
            old = old_parts[0]
            plan.warnings.append(
                f"{key} is indexed ({old.get('source')}, version {old.get('version_date')}) "
                "but missing from the new chunks; kept as is"
            )
    return plan

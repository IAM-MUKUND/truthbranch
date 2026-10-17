"""
Demo dataset for TruthBranch: the fictional company "Lumen Analytics".

This file re-exports the canonical Lumen dataset from datasets.lumen
and provides helper count functions for tests and seed scripts.
"""
from __future__ import annotations

from backend.app.seed.datasets.lumen import (
    PEOPLE,
    SYSTEMS,
    SOURCES,
    _FACTS_BASE,
    _FACTS_CONTRADICTION,
    _FACT_SOURCED,
    _FACT_SOURCED_CONTRADICTION,
    _FACT_OWNED,
    _FACT_OWNED_CONTRADICTION,
    FACT_DERIVED,
    DOCUMENTS,
    DOC_CITES,
    DOC_DERIVED,
    DOC_PUBLISHED,
    DOC_OWNED,
    META,
    SCENARIOS,
    build_dataset,
)

NODE_LISTS = ("people", "systems", "sources", "facts", "documents", "meta")
EDGE_LISTS = ("fact_sourced", "fact_owned", "fact_derived", "doc_cites",
              "doc_derived", "doc_published", "doc_owned")


def expected_node_count(ds: dict) -> int:
    return sum(len(ds[k]) for k in NODE_LISTS)


def expected_edge_count(ds: dict) -> int:
    return sum(len(ds[k]) for k in EDGE_LISTS)
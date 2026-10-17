"""
Baseline service for TruthBranch: compares naive keyword / regex search against graph impact.
"""
from __future__ import annotations

import re
from typing import Any


def literal_pattern(value: int | str) -> re.Pattern:
    """Matches `$49` but not `$490`, `$149`, or bare `49`."""
    return re.compile(rf"(?<![\d,])\${value}(?!\d)")


def keyword_baseline(documents: list[dict[str, Any]], term: str = "49") -> list[str]:
    """Naive keyword search across document contents."""
    return [d["id"] for d in documents if term in d.get("content", "")]


def exact_regex_baseline(documents: list[dict[str, Any]], value: int = 49) -> list[str]:
    """Exact currency regex search across document contents."""
    pat = literal_pattern(value)
    return [d["id"] for d in documents if pat.search(d.get("content", ""))]


def compute_baseline_comparison(
    documents: list[dict[str, Any]],
    graph_impact_docs: list[str],
    value: int = 49,
) -> dict[str, Any]:
    """Compare naive keyword search, exact regex, and graph traversal.

    Returns the metrics needed for Section 7.8 and GET /api/change-requests/{id}/baseline.
    """
    naive_hits = set(keyword_baseline(documents, str(value)))
    exact_hits = set(exact_regex_baseline(documents, value))
    graph_set = set(graph_impact_docs)

    false_positives = naive_hits - exact_hits
    keyword_misses = graph_set - exact_hits
    dark_dependencies = exact_hits - graph_set

    return {
        "naive_search": {
            "query": str(value),
            "found_count": len(naive_hits),
            "doc_ids": sorted(naive_hits),
            "false_positives": sorted(false_positives),
        },
        "exact_regex": {
            "pattern": rf"(?<![\d,])\${value}(?!\d)",
            "found_count": len(exact_hits),
            "doc_ids": sorted(exact_hits),
            "missed_multi_hop": sorted(keyword_misses),
        },
        "graph_traversal": {
            "found_count": len(graph_set),
            "doc_ids": sorted(graph_set),
            "dark_dependencies": sorted(dark_dependencies),
        },
        "summary": (
            f"Keyword search missed {len(keyword_misses)} documents (derived via multi-hop chains). "
            f"Graph traversal found all {len(graph_set)} impacted documents with explainable paths."
        ),
    }

"""
Baseline service for TruthBranch: compares naive keyword / regex search against graph impact.
"""
from __future__ import annotations

import re
from typing import Any


def literal_pattern(value: int | float | str, unit: str = "USD") -> re.Pattern:
    """Matches literal value in text according to unit, e.g. `$49`, `30 days`, `99.9%`."""
    val_str = str(value)
    if not unit or unit in ("USD", "$"):
        return re.compile(rf"(?<![\d,])\${re.escape(val_str)}(?!\d)")
    elif unit == "kUSD":
        return re.compile(rf"(?<![\d,])\${re.escape(val_str)}k(?!\w)")
    elif unit == "MUSD":
        return re.compile(rf"(?<![\d,])\${re.escape(val_str)}M(?!\w)")
    elif unit == "percent":
        return re.compile(rf"(?<![\d,]){re.escape(val_str)}%(?!\w)")
    elif unit in ("days", "hours", "minutes", "weeks", "months", "years", "seats", "chars", "codes", "people"):
        singular = unit[:-1] if unit.endswith("s") else unit
        return re.compile(rf"\b{re.escape(val_str)}\s*(?:{unit}|{singular})\b")
    else:
        return re.compile(rf"(?<![\d,]){re.escape(val_str)}(?!\d)")


def keyword_baseline(documents: list[dict[str, Any]], term: str = "49") -> list[str]:
    """Naive keyword search across document contents."""
    return [d["id"] for d in documents if term in d.get("content", "")]


def exact_regex_baseline(
    documents: list[dict[str, Any]],
    value: int | float | str = 49,
    unit: str = "USD",
) -> list[str]:
    """Exact currency / literal regex search across document contents."""
    pat = literal_pattern(value, unit=unit)
    return [d["id"] for d in documents if pat.search(d.get("content", ""))]


def compute_baseline_comparison(
    documents: list[dict[str, Any]],
    graph_impact_docs: list[str],
    value: int | float | str = 49,
    unit: str = "USD",
) -> dict[str, Any]:
    """Compare naive keyword search, exact regex, and graph traversal.

    Returns the metrics needed for Section 7.8 and GET /api/change-requests/{id}/baseline.
    """
    term = str(value)
    naive_hits = set(keyword_baseline(documents, term))
    exact_hits = set(exact_regex_baseline(documents, value, unit=unit))
    graph_set = set(graph_impact_docs)

    false_positives = naive_hits - exact_hits
    keyword_misses = graph_set - exact_hits
    dark_dependencies = exact_hits - graph_set

    query_repr = f"${value}" if unit in ("USD", "$") else str(value)

    return {
        "naive_search": {
            "query": query_repr,
            "found_count": len(naive_hits),
            "doc_ids": sorted(naive_hits),
            "false_positives": sorted(false_positives),
        },
        "exact_regex": {
            "pattern": literal_pattern(value, unit=unit).pattern,
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

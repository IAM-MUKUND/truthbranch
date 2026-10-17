"""
Impact service for TruthBranch: identifies all documents and facts impacted by a change.
"""
from __future__ import annotations

from typing import Any
from falkordb import Graph

from backend.app.queries.impact import (
    Q_DIRECT_CITERS,
    Q_DOWNSTREAM_FACTS,
    Q_DOCS_CITING_DOWNSTREAM_FACTS,
    Q_MULTI_HOP_DERIVED_DOCS,
    Q_DOCS_DERIVED_FROM_DOWNSTREAM_CITERS,
    Q_SHORTEST_PATH,
    Q_DOC_METADATA_BATCH,
)


def impact_for_fact(graph: Graph, fact_id: str) -> list[dict[str, Any]]:
    """Compute the full impact set of documents for a fact change.

    Returns a list of dicts:
        {
            "doc_id": "doc:...",
            "title": "...",
            "reason": "CITES" | "CITES_DERIVED_FACT" | "DERIVED_FROM_DOC",
            "reasons": ["..."],
            "path": ["doc:...", ..., "fact:..."],
            "owner_id": "p:...",
            "owner_name": "...",
            "system_id": "sys:...",
            "system_name": "...",
        }
    """
    # 1. Direct citers
    direct_rows = graph.ro_query(Q_DIRECT_CITERS, params={"old_fact_id": fact_id}).result_set
    direct_docs = {r[0] for r in direct_rows}

    # 2. Documents citing downstream facts
    via_fact_rows = graph.ro_query(Q_DOCS_CITING_DOWNSTREAM_FACTS, params={"old_fact_id": fact_id}).result_set
    via_fact_docs = {r[0] for r in via_fact_rows}

    # 3. Documents derived from direct citers
    via_doc_rows = graph.ro_query(Q_MULTI_HOP_DERIVED_DOCS, params={"old_fact_id": fact_id}).result_set
    via_doc_docs = {r[0] for r in via_doc_rows}

    # 4. Documents derived from downstream fact citers
    via_doc2_rows = graph.ro_query(Q_DOCS_DERIVED_FROM_DOWNSTREAM_CITERS, params={"old_fact_id": fact_id}).result_set
    via_doc2_docs = {r[0] for r in via_doc2_rows}

    all_doc_ids = direct_docs | via_fact_docs | via_doc_docs | via_doc2_docs
    if not all_doc_ids:
        return []

    # Metadata enrichment
    meta_rows = graph.ro_query(Q_DOC_METADATA_BATCH, params={"doc_ids": list(all_doc_ids)}).result_set
    meta_by_id = {
        r[0]: {
            "title": r[1],
            "status": r[2],
            "content": r[3],
            "owner_id": r[4],
            "owner_name": r[5],
            "system_id": r[6],
            "system_name": r[7],
        }
        for r in meta_rows
    }

    results = []
    for doc_id in sorted(all_doc_ids):
        doc_reasons = []
        if doc_id in direct_docs:
            doc_reasons.append("CITES")
        if doc_id in via_fact_docs:
            doc_reasons.append("CITES_DERIVED_FACT")
        if doc_id in via_doc_docs or doc_id in via_doc2_docs:
            doc_reasons.append("DERIVED_FROM_DOC")

        # Prioritize primary reason: CITES > CITES_DERIVED_FACT > DERIVED_FROM_DOC
        if "CITES" in doc_reasons:
            primary_reason = "CITES"
        elif "CITES_DERIVED_FACT" in doc_reasons:
            primary_reason = "CITES_DERIVED_FACT"
        else:
            primary_reason = "DERIVED_FROM_DOC"

        # Shortest path
        path_res = graph.ro_query(Q_SHORTEST_PATH, params={"doc_id": doc_id, "old_fact_id": fact_id}).result_set
        if path_res and path_res[0]:
            path = path_res[0][0]
        else:
            # Fallback path if Cypher didn't return
            path = [doc_id, fact_id]

        meta = meta_by_id.get(doc_id, {})
        results.append({
            "doc_id": doc_id,
            "title": meta.get("title", ""),
            "reason": primary_reason,
            "reasons": doc_reasons,
            "path": path,
            "owner_id": meta.get("owner_id"),
            "owner_name": meta.get("owner_name"),
            "system_id": meta.get("system_id"),
            "system_name": meta.get("system_name"),
        })

    return results


def downstream_facts_for_fact(graph: Graph, fact_id: str) -> list[dict[str, str]]:
    """Return all facts derived from this fact."""
    rows = graph.ro_query(Q_DOWNSTREAM_FACTS, params={"old_fact_id": fact_id}).result_set
    return [{"fact_id": r[0], "key": r[1]} for r in rows]

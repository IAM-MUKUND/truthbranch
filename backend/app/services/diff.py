"""
Deterministic diff service: calculates exact changes between kb_main and candidate branch.
"""
from __future__ import annotations

from typing import Any
from falkordb import Graph


def compute_branch_diff(main_graph: Graph, branch_graph: Graph) -> dict[str, Any]:
    """Compute the exact differences between kb_main and the branch graph."""
    # 1. Fact diffs based on SUPERSEDES edges on branch
    fact_res = branch_graph.ro_query(
        """
        MATCH (new:Fact)-[:SUPERSEDES]->(old:Fact)
        RETURN new.key, old.id, new.id, old.value, new.value, old.version, new.version, new.unit
        ORDER BY new.key
        """
    )
    fact_diffs = []
    for r in fact_res.result_set:
        fact_diffs.append({
            "key": r[0],
            "old_id": r[1],
            "new_id": r[2],
            "old_value": r[3],
            "new_value": r[4],
            "old_version": r[5],
            "new_version": r[6],
            "unit": r[7],
        })

    # 2. Proposed edits on documents
    edit_res = branch_graph.ro_query(
        """
        MATCH (e:ProposedEdit)-[:EDITS]->(d:Document)
        RETURN e.id, d.id, d.title, e.before, e.after, e.status
        ORDER BY d.id
        """
    )
    proposed_edits = []
    for r in edit_res.result_set:
        proposed_edits.append({
            "edit_id": r[0],
            "doc_id": r[1],
            "doc_title": r[2],
            "before": r[3],
            "after": r[4],
            "status": r[5],
        })

    # 3. Document status changes (e.g. marked NEEDS_REVIEW)
    main_doc_status = {
        r[0]: r[1]
        for r in main_graph.ro_query("MATCH (d:Document) RETURN d.id, d.status").result_set
    }
    branch_doc_status = {
        r[0]: r[1]
        for r in branch_graph.ro_query("MATCH (d:Document) RETURN d.id, d.status").result_set
    }
    
    doc_status_changes = []
    for doc_id, b_status in branch_doc_status.items():
        m_status = main_doc_status.get(doc_id)
        if m_status and m_status != b_status:
            doc_status_changes.append({
                "doc_id": doc_id,
                "main_status": m_status,
                "branch_status": b_status,
            })

    return {
        "facts": fact_diffs,
        "edits": proposed_edits,
        "doc_status_changes": doc_status_changes,
        "summary": {
            "facts_changed": len(fact_diffs),
            "edits_count": len(proposed_edits),
            "docs_status_changed": len(doc_status_changes),
        },
    }

"""
Deterministic edit proposals service for TruthBranch.
Replaces price literals on documents with exact values and marks derived documents without literals as NEEDS_REVIEW.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from backend.app.db import get_falkordb, get_graph
from backend.app.models import Operation, OpType, ProposedEdit, utc_now_iso
from backend.app.schema import fact_id
from backend.app.services.baseline import literal_pattern
from backend.app.services.impact import impact_for_fact
from backend.app.services.meta import (
    get_change_request,
    record_audit_event,
    save_change_request,
)
from backend.app.services.operations import apply_operations_to_graph


def draft_content_replace(content: str, old_monthly: int = 49, new_monthly: int = 59) -> str:
    """Deterministically replace monthly and annual price literals in text.

    Guarantees:
    - Replaces $49 -> $59
    - Replaces $490 -> $590 (annual x10)
    - Leaves $149 (Enterprise) untouched
    - Leaves bare numbers like '49 engineers' untouched
    """
    out = literal_pattern(old_monthly).sub(f"${new_monthly}", content)
    out = literal_pattern(old_monthly * 10).sub(f"${new_monthly * 10}", out)
    return out


def propose_edits_for_cr(cr_id: str) -> dict[str, Any]:
    """Generate proposed edits for all impacted documents on the branch."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    client = get_falkordb()
    branch = client.select_graph(cr.branch_graph)
    main = client.select_graph("kb_main")

    # Find base fact id
    old_fact_id = None
    for op in cr.ops:
        if op.key == cr.fact_key and op.old_fact_id:
            old_fact_id = op.old_fact_id
            break
    if not old_fact_id:
        old_fact_id = fact_id(cr.fact_key, 1)

    # 1. Compute impact set
    impacted = impact_for_fact(main, old_fact_id)
    now = utc_now_iso()

    created_edits: list[dict[str, Any]] = []
    marked_stale_docs: list[str] = []

    # Clean existing proposed edits on branch to be idempotent
    branch.query("MATCH (e:ProposedEdit) DETACH DELETE e")

    # Dynamically look up old fact value
    val_res = main.ro_query("MATCH (f:Fact {id:$id}) RETURN f.value", params={"id": old_fact_id}).result_set
    old_val = val_res[0][0] if (val_res and val_res[0] and val_res[0][0] is not None) else 49
    if isinstance(old_val, str) and old_val.isdigit():
        old_val = int(old_val)
    new_val_num = int(cr.new_value) if str(cr.new_value).isdigit() else cr.new_value

    for item in impacted:
        doc_id = item["doc_id"]
        # Fetch current content from branch
        doc_res = branch.ro_query(
            "MATCH (d:Document {id:$doc_id}) RETURN d.content, d.title",
            params={"doc_id": doc_id},
        )
        if not doc_res.result_set:
            continue

        content, title = doc_res.result_set[0]
        content = content or ""

        # Check if content has literal old value or derived annual value (x10)
        has_literal = False
        if isinstance(old_val, (int, float)):
            has_literal = bool(literal_pattern(old_val).search(content) or literal_pattern(int(old_val * 10)).search(content))
        elif isinstance(old_val, str):
            has_literal = bool(re.search(re.escape(old_val), content))

        if has_literal:
            if isinstance(old_val, (int, float)) and isinstance(new_val_num, (int, float)):
                new_content = draft_content_replace(content, old_monthly=int(old_val), new_monthly=int(new_val_num))
            else:
                new_content = content.replace(str(old_val), str(new_val_num))
            edit_id = f"edit_{uuid.uuid4().hex[:8]}"

            branch.query(
                """
                MATCH (d:Document {id:$doc_id})
                CREATE (e:ProposedEdit {
                    id: $id,
                    doc_id: $doc_id,
                    before: $before,
                    after: $after,
                    status: 'PROPOSED',
                    author: 'TruthBranch Agent',
                    created_at: $now
                })
                CREATE (e)-[:EDITS]->(d)
                """,
                params={
                    "id": edit_id,
                    "doc_id": doc_id,
                    "before": content,
                    "after": new_content,
                    "now": now,
                },
            )
            created_edits.append({
                "edit_id": edit_id,
                "doc_id": doc_id,
                "doc_title": title,
                "before": content,
                "after": new_content,
            })
        else:
            # Multi-hop derived document without literal -> mark NEEDS_REVIEW
            branch.query(
                "MATCH (d:Document {id:$doc_id}) SET d.status = 'NEEDS_REVIEW'",
                params={"doc_id": doc_id},
            )
            marked_stale_docs.append(doc_id)

    # Record audit event
    record_audit_event(
        cr_id,
        "EDITS_DRAFTED",
        {
            "edits_count": len(created_edits),
            "marked_stale_count": len(marked_stale_docs),
            "edited_docs": [e["doc_id"] for e in created_edits],
            "marked_stale_docs": marked_stale_docs,
        },
    )

    return {
        "cr_id": cr_id,
        "edits": created_edits,
        "marked_stale": marked_stale_docs,
    }

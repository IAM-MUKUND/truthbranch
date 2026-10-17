"""
Lifecycle transitions and merge procedure for TruthBranch.
Handles:
- submit (CHECKS_PASSED -> READY_FOR_REVIEW)
- approve (READY_FOR_REVIEW -> APPROVED)
- reject (-> REJECTED, teardown branch)
- merge (APPROVED -> MERGED, optimistic concurrency check, replay ops on kb_main, repoint citations, bump revision, teardown branch)
"""
from __future__ import annotations

from typing import Any

from falkordb import Graph

from backend.app.db import get_falkordb, get_graph
from backend.app.models import (
    CRStatus,
    CheckSeverity,
    Operation,
    OpType,
    transition,
    utc_now_iso,
)
from backend.app.schema import branch_graph_name, fact_id
from backend.app.services.branching import delete_branch, get_base_revision
from backend.app.services.checks import run_quality_checks
from backend.app.services.impact import impact_for_fact
from backend.app.services.meta import (
    get_change_request,
    record_audit_event,
    save_change_request,
)


def submit_change_request(cr_id: str) -> dict[str, Any]:
    """Submit a change request for review once checks have passed."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    if cr.status != CRStatus.CHECKS_PASSED:
        raise ValueError(
            f"Cannot submit Change Request in status '{cr.status.value}'. Must be 'CHECKS_PASSED'."
        )

    transition(cr, CRStatus.READY_FOR_REVIEW)
    save_change_request(cr)
    record_audit_event(cr_id, "SUBMITTED", {"status": cr.status.value})
    return {"cr": cr, "status": cr.status.value}


def approve_change_request(cr_id: str, reviewer: str = "admin") -> dict[str, Any]:
    """Human approval gate for a Change Request."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    if cr.status != CRStatus.READY_FOR_REVIEW:
        raise ValueError(
            f"Cannot approve Change Request in status '{cr.status.value}'. Must be 'READY_FOR_REVIEW'."
        )

    transition(cr, CRStatus.APPROVED)
    cr.approved_by = reviewer
    save_change_request(cr)
    record_audit_event(cr_id, "APPROVED", {"approved_by": reviewer, "status": cr.status.value})
    return {"cr": cr, "status": cr.status.value}


def reject_change_request(cr_id: str, reviewer: str = "admin", reason: str = "Rejected by reviewer") -> dict[str, Any]:
    """Reject a Change Request and clean up its branch graph."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    if cr.status not in (CRStatus.DRAFT, CRStatus.BLOCKED, CRStatus.CHECKS_PASSED, CRStatus.READY_FOR_REVIEW):
        raise ValueError(f"Cannot reject Change Request in status '{cr.status.value}'.")

    transition(cr, CRStatus.REJECTED, reason=reason)
    cr.approved_by = reviewer
    save_change_request(cr)

    # Delete branch graph
    delete_branch(cr.branch_graph)
    record_audit_event(cr_id, "REJECTED", {"rejected_by": reviewer, "reason": reason, "status": cr.status.value})
    return {"cr": cr, "status": cr.status.value}


def merge_change_request(cr_id: str) -> dict[str, Any]:
    """Replay approved candidate changes into authoritative kb_main graph with full history preservation."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    # Idempotent return if already merged
    if cr.status == CRStatus.MERGED:
        return {
            "cr": cr,
            "status": "MERGED",
            "message": "Change Request already merged.",
            "already_merged": True,
        }

    if cr.status != CRStatus.APPROVED:
        raise ValueError(
            f"Cannot merge Change Request in status '{cr.status.value}'. Must be 'APPROVED'."
        )

    client = get_falkordb()
    main = client.select_graph("kb_main")
    branch = client.select_graph(cr.branch_graph)

    # 1. Re-verify checks on the branch before writing to main
    old_fact_id = fact_id(cr.fact_key, 1)
    impacted = impact_for_fact(main, old_fact_id)
    pre_checks = run_quality_checks(branch, impacted, cr.fact_key, old_val=49)
    if any(not c.passed and c.severity == CheckSeverity.BLOCK for c in pre_checks):
        raise ValueError("Cannot merge: one or more blocking quality checks failed on branch.")

    # 2. Optimistic Concurrency Check
    current_rev = get_base_revision(main)
    if current_rev != cr.base_revision:
        # Base revision moved: verify expected version still active
        ver_check = main.ro_query(
            "MATCH (f:Fact {key:$key, status:'ACTIVE'}) RETURN f.version",
            params={"key": cr.fact_key},
        ).result_set
        if not ver_check or ver_check[0][0] != cr.ops[0].expected_version:
            transition(cr, CRStatus.CONFLICT)
            save_change_request(cr)
            record_audit_event(cr_id, "CONFLICT", {"base_revision": cr.base_revision, "current_revision": current_rev})
            raise ValueError(
                f"Merge conflict: base revision moved from {cr.base_revision} to {current_rev} and active version changed."
            )

    now = utc_now_iso()

    # 3. Pre-validate operations against kb_main
    for op in cr.ops:
        if op.op_type == OpType.UPDATE_FACT:
            v_res = main.ro_query(
                "MATCH (f:Fact {key:$key, status:'ACTIVE'}) RETURN f.version",
                params={"key": op.key},
            ).result_set
            if not v_res or v_res[0][0] != op.expected_version:
                transition(cr, CRStatus.CONFLICT)
                save_change_request(cr)
                raise ValueError(f"Merge aborted: expected active version for '{op.key}' was not found on kb_main.")

    # 4. Replay UPDATE_FACT and ATTACH_SOURCE operations onto kb_main
    for op in cr.ops:
        if op.op_type == OpType.UPDATE_FACT:
            # Create new version and supersede old
            main.query(
                """
                MATCH (old:Fact {key:$key, status:'ACTIVE'})
                WHERE old.version = $expected_version
                CREATE (new:Fact {
                    id: $new_id,
                    key: $key,
                    version: $new_version,
                    subject: old.subject,
                    attribute: old.attribute,
                    value: $new_value,
                    unit: old.unit,
                    status: 'ACTIVE',
                    created_at: $now
                })
                CREATE (new)-[:SUPERSEDES]->(old)
                SET old.status = 'SUPERSEDED'
                RETURN new.id
                """,
                params={
                    "key": op.key,
                    "expected_version": op.expected_version,
                    "new_id": op.new_fact_id,
                    "new_version": (op.expected_version or 1) + 1,
                    "new_value": op.new_value,
                    "now": now,
                },
            )

            # Carry over owner
            main.query(
                """
                MATCH (old:Fact {id:$old_id})-[:OWNED_BY]->(p:Person), (new:Fact {id:$new_id})
                MERGE (new)-[:OWNED_BY]->(p)
                """,
                params={"old_id": op.old_fact_id, "new_id": op.new_fact_id},
            )

            # Link derived fact if applicable
            if op.derived:
                main.query(
                    """
                    MATCH (new_derived:Fact {id:$derived_id})
                    MATCH (new_base:Fact {key:$base_key, status:'ACTIVE'})
                    MERGE (new_derived)-[r:DERIVED_FROM]->(new_base)
                    SET r.rule = $rule
                    """,
                    params={
                        "derived_id": op.new_fact_id,
                        "base_key": op.derived.from_key,
                        "rule": op.derived.rule,
                    },
                )

        elif op.op_type == OpType.ATTACH_SOURCE:
            main.query(
                """
                MATCH (f:Fact {id:$fact_id}), (s:Source {id:$source_id})
                MERGE (f)-[:SOURCED_FROM]->(s)
                """,
                params={"fact_id": op.fact_id, "source_id": op.source_id},
            )

    # 5. Apply ProposedEdits and REPOINT_CITATION to kb_main
    branch_edits = branch.ro_query(
        "MATCH (e:ProposedEdit)-[:EDITS]->(d:Document) RETURN d.id, e.after"
    ).result_set

    # Find the new fact IDs created on merge
    new_monthly_id = fact_id("pricing.pro.monthly", 2)
    new_annual_id = fact_id("pricing.pro.annual", 2)
    old_monthly_id = fact_id("pricing.pro.monthly", 1)
    old_annual_id = fact_id("pricing.pro.annual", 1)

    for doc_id, after_text in branch_edits:
        # Update content and mark CURRENT on kb_main
        main.query(
            """
            MATCH (d:Document {id:$doc_id})
            SET d.content = $after,
                d.status = 'CURRENT',
                d.last_reviewed = $now
            """,
            params={"doc_id": doc_id, "after": after_text, "now": now[:10]},
        )

        # Repoint monthly citation if cited
        main.query(
            """
            MATCH (d:Document {id:$doc_id})-[c:CITES]->(old:Fact {id:$old_id})
            MATCH (new:Fact {id:$new_id})
            DELETE c
            WITH d, new
            MERGE (d)-[:CITES]->(new)
            """,
            params={
                "doc_id": doc_id,
                "old_id": old_monthly_id,
                "new_id": new_monthly_id,
            },
        )

        # Repoint annual citation if cited (pricing_page)
        main.query(
            """
            MATCH (d:Document {id:$doc_id})-[c:CITES]->(old:Fact {id:$old_id})
            MATCH (new:Fact {id:$new_id})
            DELETE c
            WITH d, new
            MERGE (d)-[:CITES]->(new)
            """,
            params={
                "doc_id": doc_id,
                "old_id": old_annual_id,
                "new_id": new_annual_id,
            },
        )

    # 6. Mark multi-hop derived documents without literals as NEEDS_REVIEW on kb_main
    branch_stale = branch.ro_query(
        "MATCH (d:Document {status:'NEEDS_REVIEW'}) RETURN d.id"
    ).result_set
    for (stale_doc_id,) in branch_stale:
        main.query(
            "MATCH (d:Document {id:$doc_id}) SET d.status = 'NEEDS_REVIEW'",
            params={"doc_id": stale_doc_id},
        )

    # 7. Increment revision counter on kb_main
    main.query("MATCH (m:Meta {id:'main'}) SET m.revision = m.revision + 1")

    # 8. Record audit event and set CR to MERGED
    transition(cr, CRStatus.MERGED)
    cr.merged_at = now
    save_change_request(cr)

    record_audit_event(
        cr_id,
        "MERGED",
        {
            "merged_at": now,
            "revision": current_rev + 1,
            "edits_applied": len(branch_edits),
            "stale_docs": [r[0] for r in branch_stale],
        },
    )

    # 9. Clean up candidate branch container
    delete_branch(cr.branch_graph)

    return {
        "cr": cr,
        "status": "MERGED",
        "merged_at": now,
        "revision": current_rev + 1,
        "edits_applied": len(branch_edits),
    }

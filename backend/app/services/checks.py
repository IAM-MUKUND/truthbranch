"""
Deterministic Quality Checks service for TruthBranch.
Rules:
- SOURCE_MISSING (BLOCK): New fact must have >= 1 source.
- SOURCE_INVALID (BLOCK): All sources must be valid=True and trust >= 0.6.
- STALE_DEPENDENCY (BLOCK): Every document in the impact set must be covered by a ProposedEdit or marked NEEDS_REVIEW.
- CONTRADICTION (BLOCK): No two ACTIVE facts may share subject+attribute with different values.
- LITERAL_VALUE_LEAK (WARN): Documents outside the impact set must not contain the old price literal (currency regex).
"""
from __future__ import annotations

import re
from typing import Any

from falkordb import Graph

from backend.app.db import get_falkordb, get_graph
from backend.app.models import (
    CheckCode,
    CheckResult,
    CheckSeverity,
    CRStatus,
    transition,
)
from backend.app.queries.checks import (
    Q_ALL_DOCUMENTS,
    Q_CHECK_CONTRADICTION,
    Q_CHECK_SOURCE,
)
from backend.app.schema import fact_id
from backend.app.services.baseline import compute_baseline_comparison, literal_pattern
from backend.app.services.impact import impact_for_fact
from backend.app.services.meta import (
    get_change_request,
    record_audit_event,
    save_change_request,
)


def run_quality_checks(
    branch_graph: Graph,
    impact_docs: list[dict[str, Any]],
    fact_key: str,
    old_val: int = 49,
) -> list[CheckResult]:
    """Execute all deterministic checks against the branch graph."""
    results: list[CheckResult] = []

    # 1. Fetch new active facts on the branch
    active_facts_res = branch_graph.ro_query(
        """
        MATCH (f:Fact {key:$key, status:'ACTIVE'})
        RETURN f.id, f.value, f.version
        """,
        params={"key": fact_key},
    )
    if not active_facts_res.result_set:
        return [
            CheckResult(
                code=CheckCode.SOURCE_MISSING,
                severity=CheckSeverity.BLOCK,
                passed=False,
                message=f"No active fact found on branch for key '{fact_key}'.",
            )
        ]

    new_fact_id = active_facts_res.result_set[0][0]

    # Check 1: SOURCE_MISSING & SOURCE_INVALID
    src_res = branch_graph.ro_query(Q_CHECK_SOURCE, params={"fact_id": new_fact_id})
    if src_res.result_set and src_res.result_set[0]:
        fact_id_val, src_count, valids, trusts = src_res.result_set[0]
        # Source missing check
        if src_count == 0:
            results.append(
                CheckResult(
                    code=CheckCode.SOURCE_MISSING,
                    severity=CheckSeverity.BLOCK,
                    passed=False,
                    message="Proposed fact has no attached source.",
                    evidence=[new_fact_id],
                )
            )
        else:
            results.append(
                CheckResult(
                    code=CheckCode.SOURCE_MISSING,
                    severity=CheckSeverity.BLOCK,
                    passed=True,
                    message="Fact has at least one source attached.",
                    evidence=[new_fact_id],
                )
            )

        # Source invalid check (valid=True and trust >= 0.6)
        invalid_sources = []
        for v, t in zip(valids, trusts):
            if not v or t < 0.6:
                invalid_sources.append({"valid": v, "trust": t})

        if invalid_sources:
            results.append(
                CheckResult(
                    code=CheckCode.SOURCE_INVALID,
                    severity=CheckSeverity.BLOCK,
                    passed=False,
                    message=f"Source verification failed: {len(invalid_sources)} source(s) untrusted or invalid.",
                    evidence=invalid_sources,
                )
            )
        else:
            results.append(
                CheckResult(
                    code=CheckCode.SOURCE_INVALID,
                    severity=CheckSeverity.BLOCK,
                    passed=True,
                    message="All attached sources are valid and meet trust threshold (>= 0.6).",
                    evidence=[{"valid": v, "trust": t} for v, t in zip(valids, trusts)],
                )
            )

    # Check 2: STALE_DEPENDENCY
    # Every doc in the impact set must have a ProposedEdit or status='NEEDS_REVIEW' on branch
    impact_doc_ids = {d["doc_id"] for d in impact_docs}

    # Fetch docs that have proposed edits on the branch
    edits_res = branch_graph.ro_query("MATCH (e:ProposedEdit)-[:EDITS]->(d:Document) RETURN DISTINCT d.id")
    docs_with_edits = {r[0] for r in edits_res.result_set}

    # Fetch docs that have status='NEEDS_REVIEW' on the branch
    stale_res = branch_graph.ro_query("MATCH (d:Document {status:'NEEDS_REVIEW'}) RETURN DISTINCT d.id")
    docs_marked_stale = {r[0] for r in stale_res.result_set}

    covered_docs = docs_with_edits | docs_marked_stale
    uncovered_docs = impact_doc_ids - covered_docs

    if uncovered_docs:
        results.append(
            CheckResult(
                code=CheckCode.STALE_DEPENDENCY,
                severity=CheckSeverity.BLOCK,
                passed=False,
                message=f"{len(uncovered_docs)} document(s) in impact set lack proposed edits or review flags.",
                evidence=sorted(uncovered_docs),
            )
        )
    else:
        results.append(
            CheckResult(
                code=CheckCode.STALE_DEPENDENCY,
                severity=CheckSeverity.BLOCK,
                passed=True,
                message="All impacted documents are covered by proposed edits or review flags.",
                evidence=sorted(impact_doc_ids),
            )
        )

    # Check 3: CONTRADICTION
    # Check on branch for active facts with same subject+attribute but different values
    contra_res = branch_graph.ro_query(Q_CHECK_CONTRADICTION)
    if contra_res.result_set:
        contra_evidence = []
        for row in contra_res.result_set:
            contra_evidence.append({
                "fact_a": row[0],
                "val_a": row[1],
                "fact_b": row[2],
                "val_b": row[3],
            })
        results.append(
            CheckResult(
                code=CheckCode.CONTRADICTION,
                severity=CheckSeverity.BLOCK,
                passed=False,
                message="Contradiction detected: active facts share subject/attribute with conflicting values.",
                evidence=contra_evidence,
            )
        )
    else:
        results.append(
            CheckResult(
                code=CheckCode.CONTRADICTION,
                severity=CheckSeverity.BLOCK,
                passed=True,
                message="No contradictory active facts detected.",
                evidence=[],
            )
        )

    # Check 4: LITERAL_VALUE_LEAK (WARN)
    # Search documents OUTSIDE the impact set for regex matching $old_val
    all_docs_res = branch_graph.ro_query(Q_ALL_DOCUMENTS)
    outside_docs = [r for r in all_docs_res.result_set if r[0] not in impact_doc_ids]

    leak_pattern = literal_pattern(old_val)
    leaked_docs = []
    for doc_id_val, title, content in outside_docs:
        if leak_pattern.search(content or ""):
            leaked_docs.append(doc_id_val)

    if leaked_docs:
        results.append(
            CheckResult(
                code=CheckCode.LITERAL_VALUE_LEAK,
                severity=CheckSeverity.WARN,
                passed=False,
                message=f"Possible dark dependency: {len(leaked_docs)} document(s) outside graph impact contain '${old_val}'.",
                evidence=sorted(leaked_docs),
            )
        )
    else:
        results.append(
            CheckResult(
                code=CheckCode.LITERAL_VALUE_LEAK,
                severity=CheckSeverity.WARN,
                passed=True,
                message="No leaked literal values found in unlinked documents.",
                evidence=[],
            )
        )

    return results


def analyze_change_request(cr_id: str) -> dict[str, Any]:
    """Run full deterministic impact analysis, baseline comparison, and quality checks."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    client = get_falkordb()
    branch = client.select_graph(cr.branch_graph)
    main = client.select_graph("kb_main")

    # 1. Determine base fact ID on kb_main (or old fact being updated)
    old_fact_id = None
    for op in cr.ops:
        if op.key == cr.fact_key and op.old_fact_id:
            old_fact_id = op.old_fact_id
            break

    if not old_fact_id:
        old_fact_id = fact_id(cr.fact_key, 1)

    # 2. Compute impact set (from kb_main or branch)
    impact_items = impact_for_fact(main, old_fact_id)
    impact_doc_ids = [i["doc_id"] for i in impact_items]

    # 3. Compute baseline comparison
    all_docs_res = main.ro_query("MATCH (d:Document) RETURN d.id, d.title, d.content").result_set
    documents_list = [{"id": r[0], "title": r[1], "content": r[2]} for r in all_docs_res]
    baseline_card = compute_baseline_comparison(documents_list, impact_doc_ids, value=49)

    # 4. Run quality checks on the branch
    check_results = run_quality_checks(
        branch_graph=branch,
        impact_docs=impact_items,
        fact_key=cr.fact_key,
        old_val=49,
    )

    # 5. Evaluate pass/block status
    has_blocking_failure = any(
        not c.passed and c.severity == CheckSeverity.BLOCK for c in check_results
    )
    new_status = CRStatus.BLOCKED if has_blocking_failure else CRStatus.CHECKS_PASSED

    # 6. Update CR status
    if cr.status in (CRStatus.DRAFT, CRStatus.BLOCKED, CRStatus.CHECKS_PASSED, CRStatus.READY_FOR_REVIEW):
        transition(cr, new_status)
        save_change_request(cr)

    # 7. Record audit event
    record_audit_event(
        cr_id,
        "ANALYZED",
        {
            "status": cr.status.value,
            "impact_count": len(impact_items),
            "checks_passed": not has_blocking_failure,
            "checks_summary": [f"{c.code.value}: {'PASS' if c.passed else 'FAIL'}" for c in check_results],
        },
    )

    return {
        "cr": cr,
        "impact": impact_items,
        "baseline": baseline_card,
        "checks": [c.model_dump() for c in check_results],
        "status": cr.status.value,
    }

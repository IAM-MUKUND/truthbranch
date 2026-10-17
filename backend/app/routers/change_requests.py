"""
Change Requests router: CRUD, analyze, diff, baseline, submit, approve, reject, merge.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.db import get_falkordb, get_graph
from backend.app.models import ChangeRequest, ChangeRequestCreate
from backend.app.schema import fact_id
from backend.app.services.baseline import compute_baseline_comparison
from backend.app.services.change_requests import create_change_request
from backend.app.services.checks import analyze_change_request, run_quality_checks
from backend.app.services.diff import compute_branch_diff
from backend.app.services.edits import propose_edits_for_cr
from backend.app.services.impact import impact_for_fact
from backend.app.services.merge import (
    approve_change_request,
    merge_change_request,
    reject_change_request,
    submit_change_request,
)
from backend.app.services.meta import (
    get_agent_steps,
    get_audit_events,
    get_change_request,
    list_change_requests,
)

router = APIRouter(prefix="/api/change-requests", tags=["change_requests"])


class ApproveRequest(BaseModel):
    reviewer: str = "Admin"


class RejectRequest(BaseModel):
    reviewer: str = "Admin"
    reason: str = "Rejected"


@router.post("", response_model=ChangeRequest)
def create_cr(payload: ChangeRequestCreate):
    """Create a new change request, fork a branch, build operations, and apply them."""
    try:
        cr = create_change_request(
            title=payload.title,
            fact_key=payload.fact_key,
            new_value=payload.new_value,
            source_id=payload.source_id,
            created_by=payload.created_by,
        )
        return cr
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[ChangeRequest])
def list_crs():
    """List all change requests."""
    return list_change_requests()


@router.get("/{cr_id}")
def get_cr_detail(cr_id: str):
    """Get full change request details including diff, impact, checks, edits, steps, and audit."""
    cr = get_change_request(cr_id)
    if not cr:
        raise HTTPException(status_code=404, detail=f"Change Request '{cr_id}' not found.")

    client = get_falkordb()
    main = get_graph("kb_main")
    
    # 1. Old fact id
    old_fact_id = fact_id(cr.fact_key, 1)
    f_res = main.ro_query("MATCH (f:Fact {id: $id}) RETURN f.value", params={"id": old_fact_id}).result_set
    fact_val = f_res[0][0] if f_res else 49

    # 2. Impact set
    impact_items = impact_for_fact(main, old_fact_id)
    impact_doc_ids = [i["doc_id"] for i in impact_items]

    # 3. Diff (if branch exists)
    diff = {"facts": [], "edits": [], "doc_status_changes": [], "summary": {}}
    checks = []
    if cr.branch_graph in client.list_graphs():
        branch = client.select_graph(cr.branch_graph)
        diff = compute_branch_diff(main, branch)
        raw_checks = run_quality_checks(branch, impact_items, cr.fact_key, old_val=fact_val)
        checks = [c.model_dump() for c in raw_checks]

    # 4. Baseline
    all_docs = main.ro_query("MATCH (d:Document) RETURN d.id, d.title, d.content").result_set
    documents_list = [{"id": r[0], "title": r[1], "content": r[2]} for r in all_docs]
    baseline = compute_baseline_comparison(documents_list, impact_doc_ids, value=fact_val)

    # 5. Audit & Steps
    audit_events = get_audit_events(cr_id)
    steps = get_agent_steps(cr_id)

    return {
        "cr": cr,
        "diff": diff,
        "impact": impact_items,
        "baseline": baseline,
        "checks": checks,
        "steps": steps,
        "audit": [a.model_dump() for a in audit_events],
    }


@router.post("/{cr_id}/analyze")
def analyze_cr(cr_id: str):
    """Run deterministic impact analysis, checks, and state transitions."""
    try:
        return analyze_change_request(cr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{cr_id}/baseline")
def get_cr_baseline(cr_id: str):
    """Get naive keyword vs graph comparison."""
    cr = get_change_request(cr_id)
    if not cr:
        raise HTTPException(status_code=404, detail=f"Change Request '{cr_id}' not found.")

    main = get_graph("kb_main")
    old_fact_id = fact_id(cr.fact_key, 1)
    impact_items = impact_for_fact(main, old_fact_id)
    impact_doc_ids = [i["doc_id"] for i in impact_items]

    all_docs = main.ro_query("MATCH (d:Document) RETURN d.id, d.title, d.content").result_set
    documents_list = [{"id": r[0], "title": r[1], "content": r[2]} for r in all_docs]
    return compute_baseline_comparison(documents_list, impact_doc_ids, value=49)


@router.post("/{cr_id}/agent-review")
def agent_review(cr_id: str):
    """Run autonomous agent review loop (Groq or scripted fallback)."""
    from backend.app.agent.loop import run_groq_agent_review
    try:
        return run_groq_agent_review(cr_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent review failed: {str(e)}")


@router.post("/{cr_id}/propose-edits")
def propose_edits(cr_id: str):
    """Deterministically draft edits for all impacted documents."""
    try:
        return propose_edits_for_cr(cr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cr_id}/submit")
def submit_cr(cr_id: str):
    """Submit Change Request for review."""
    try:
        return submit_change_request(cr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cr_id}/approve")
def approve_cr(cr_id: str, payload: ApproveRequest = ApproveRequest()):
    """Approve Change Request."""
    try:
        return approve_change_request(cr_id, reviewer=payload.reviewer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cr_id}/reject")
def reject_cr(cr_id: str, payload: RejectRequest = RejectRequest()):
    """Reject Change Request and drop candidate branch."""
    try:
        return reject_change_request(cr_id, reviewer=payload.reviewer, reason=payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cr_id}/merge")
def merge_cr(cr_id: str):
    """Replay approved changes into kb_main."""
    try:
        return merge_change_request(cr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

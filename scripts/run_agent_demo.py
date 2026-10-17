"""
End-to-End Autonomous Agent Execution Demo (Sprint 3).
Demonstrates both:
1. Scenario A: Trusted source -> agent inspects lineage, identifies 7 impacted documents,
   detects stale dependencies, drafts edits, re-verifies checks, requests dark leak verification,
   and submits for human review. Followed by human approval and safe merge.
2. Scenario B: Untrusted Slack rumor -> agent inspects lineage, detects low trust (0.2),
   refuses to draft edits or submit, and dispatches verification request to stakeholder.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.agent.loop import run_groq_agent_review
from backend.app.db import get_falkordb
from backend.app.models import CRStatus
from backend.app.seed.seed import seed_graph
from backend.app.services.change_requests import create_change_request
from backend.app.services.merge import approve_change_request, merge_change_request
from backend.app.services.meta import get_agent_steps, get_change_request, reset_meta


def run_demo():
    print("=" * 80)
    print("TRUTHBRANCH — SPRINT 3 AUTONOMOUS AGENT DEMO (TRACK 1 & TRACK 3)")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # Setup
    # -------------------------------------------------------------------------
    print("\n[INIT] Resetting database to clean baseline...")
    client = get_falkordb()
    for gname in client.list_graphs():
        if gname.startswith("kb_cr_") or gname.startswith("kb_branch_"):
            try:
                client.select_graph(gname).delete()
            except Exception:
                pass
    reset_meta()
    seed_graph("kb_main", with_contradiction=False, drop_existing=True)
    print("       kb_main seeded cleanly.")

    # -------------------------------------------------------------------------
    # PART 1: SCENARIO A (Valid Price Increase $49 -> $59)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PART 1: SCENARIO A — TRUSTED SOURCE (Pricing Committee Memo, Oct 2026)")
    print("=" * 80)

    cr_a = create_change_request(
        title="Pro Monthly Price Increase to $59",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
        created_by="Maya Rao (Product Owner)",
    )
    print(f"[A.1] Created Change Request {cr_a.id} in branch '{cr_a.branch_graph}'. Status: {cr_a.status.value}")

    print("\n[A.2] Launching Autonomous Agent Review Loop...")
    res_a = run_groq_agent_review(cr_a.id)

    print(f"\n[A.3] Agent Execution Completed with {len(res_a['steps'])} steps:")
    for step in res_a["steps"]:
        tool = step["tool"]
        summary = step["summary"]
        args = step["args"]
        print(f"      Step #{step['idx']}: {tool}")
        print(f"        Args:    {args}")
        print(f"        Summary: {summary}")

    print(f"\n[A.4] Agent Verdict: {res_a['verdict']}")
    cr_a_updated = get_change_request(cr_a.id)
    print(f"      CR Status: {cr_a_updated.status.value}")
    assert cr_a_updated.status == CRStatus.READY_FOR_REVIEW

    print("\n[A.5] Human Approval Gate:")
    app_res = approve_change_request(cr_a.id, reviewer="Finance Committee Lead")
    print(f"      Status after Human Approval: {app_res['status']}")
    assert app_res["status"] == "APPROVED"

    print("\n[A.6] Merging Approved Candidate Branch to kb_main:")
    merge_res = merge_change_request(cr_a.id)
    print(f"      Merge status: {merge_res['status']}")
    print(f"      kb_main Revision: {merge_res['revision']}")
    print(f"      Edits applied: {merge_res['edits_applied']}")

    # Verify kb_main state
    main = client.select_graph("kb_main")
    active_facts = main.ro_query("MATCH (f:Fact {key:'pricing.pro.monthly', status:'ACTIVE'}) RETURN f.id, f.value, f.version").result_set
    print(f"      Active Fact on kb_main: {active_facts[0][0]} = ${active_facts[0][1]} (v{active_facts[0][2]})")
    old_facts = main.ro_query("MATCH (f:Fact {key:'pricing.pro.monthly', status:'SUPERSEDED'}) RETURN f.id, f.value, f.version").result_set
    print(f"      Superseded Fact retained: {old_facts[0][0]} = ${old_facts[0][1]} (v{old_facts[0][2]})")

    # -------------------------------------------------------------------------
    # PART 2: SCENARIO B (Untrusted Slack Rumor $39)
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("PART 2: SCENARIO B — UNTRUSTED SOURCE (Unverified Slack Rumor, trust=0.2)")
    print("=" * 80)

    cr_b = create_change_request(
        title="Unverified Price Cut to $39",
        fact_key="pricing.pro.monthly",
        new_value=39,
        source_id="src:slack_rumor_2026_10",  # valid=False, trust=0.2
        created_by="Sales Anon",
    )
    print(f"[B.1] Created Change Request {cr_b.id} with untrusted source. Status: {cr_b.status.value}")

    print("\n[B.2] Launching Autonomous Agent Review Loop...")
    res_b = run_groq_agent_review(cr_b.id)

    print(f"\n[B.3] Agent Execution Completed with {len(res_b['steps'])} steps:")
    for step in res_b["steps"]:
        tool = step["tool"]
        summary = step["summary"]
        args = step["args"]
        print(f"      Step #{step['idx']}: {tool}")
        print(f"        Args:    {args}")
        print(f"        Summary: {summary}")

    print(f"\n[B.4] Agent Verdict: {res_b['verdict']}")
    cr_b_updated = get_change_request(cr_b.id)
    print(f"      CR Status: {cr_b_updated.status.value}")

    # Verify agent REFUSED submission
    assert not res_b["submitted"]
    assert cr_b_updated.status != CRStatus.READY_FOR_REVIEW
    print("      SUCCESS: Agent refused submission and alerted stakeholders.")

    print("\n" + "=" * 80)
    print("DEMO COMPLETE: BOTH SCENARIOS VERIFIED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()

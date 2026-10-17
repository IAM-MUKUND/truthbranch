"""
End-to-End Execution Script for Scenario A (Checklist Block 2.8).
Runs propose -> branch -> analyze -> edits -> submit -> approve -> merge
with 100% deterministic correctness. Zero LLM, zero frontend required.
"""
from __future__ import annotations

import sys
from falkordb import FalkorDB

from backend.app.config import get_settings
from backend.app.db import get_falkordb, get_graph
from backend.app.models import CRStatus
from backend.app.seed.seed import seed_graph
from backend.app.services.change_requests import create_change_request
from backend.app.services.checks import analyze_change_request
from backend.app.services.edits import propose_edits_for_cr
from backend.app.services.merge import (
    approve_change_request,
    merge_change_request,
    submit_change_request,
)
from backend.app.services.meta import reset_meta


def run():
    print("=" * 70)
    print("TRUTHBRANCH — SCENARIO A END-TO-END EXECUTION")
    print("Propose -> Branch -> Analyze -> Edits -> Submit -> Approve -> Merge")
    print("=" * 70)

    # Step 0: Clean reset
    print("\n[0/7] Resetting database to clean Lumen Analytics baseline...")
    client = get_falkordb()
    for gname in client.list_graphs():
        if gname.startswith("kb_cr_"):
            try:
                client.select_graph(gname).delete()
            except Exception:
                pass
    reset_meta()
    seed_res = seed_graph("kb_main", with_contradiction=False, drop_existing=True)
    print(f"      Seeded kb_main: {seed_res['nodes']} nodes, {seed_res['edges']} edges.")

    # Step 1: Propose Change Request
    print("\n[1/7] Step 1: Proposing change on a candidate branch...")
    cr = create_change_request(
        title="Raise Pro monthly price to $59",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
        created_by="Maya Rao",
    )
    print(f"      Created Change Request: {cr.id}")
    print(f"      Branch Graph: {cr.branch_graph}")
    print(f"      Operations planned: {len(cr.ops)} ops")
    for op in cr.ops:
        print(f"        - {op.op_type.value}: {op.key or op.fact_id} -> {op.new_value or op.source_id}")

    # Step 2: Initial Analysis
    print("\n[2/7] Step 2: Running deterministic impact analysis and quality checks...")
    analysis1 = analyze_change_request(cr.id)
    print(f"      Initial Status: {analysis1['status']}")
    print(f"      Impacted Documents Found by Graph: {len(analysis1['impact'])}")
    for item in analysis1['impact']:
        print(f"        * {item['doc_id']} ({item['reason']}): {' -> '.join(item['path'])}")

    print(f"\n      Baseline Comparison:")
    base = analysis1['baseline']
    print(f"        - Naive search found {base['naive_search']['found_count']} (false positive: {base['naive_search']['false_positives']})")
    print(f"        - Exact regex found {base['exact_regex']['found_count']} (missed {len(base['exact_regex']['missed_multi_hop'])} multi-hop docs)")
    print(f"        - Graph traversal found {base['graph_traversal']['found_count']} documents with 0 false positives.")

    # Step 3: Propose Edits
    print("\n[3/7] Step 3: Drafting deterministic edits for impacted documents...")
    edits = propose_edits_for_cr(cr.id)
    print(f"      Drafted {len(edits['edits'])} document edits:")
    for e in edits['edits']:
        print(f"        - {e['doc_id']}: '{e['before'][:40]}...' -> '{e['after'][:40]}...'")
    print(f"      Marked {len(edits['marked_stale'])} multi-hop documents as NEEDS_REVIEW:")
    for d in edits['marked_stale']:
        print(f"        - {d}")

    # Step 4: Re-analyze
    print("\n[4/7] Step 4: Re-evaluating checks on candidate branch...")
    analysis2 = analyze_change_request(cr.id)
    print(f"      New Status: {analysis2['status']}")
    assert analysis2['status'] == CRStatus.CHECKS_PASSED.value, f"Expected CHECKS_PASSED, got {analysis2['status']}"
    for c in analysis2['checks']:
        print(f"        [{'PASS' if c['passed'] else c['severity']}] {c['code']}: {c['message']}")

    # Step 5: Submit for review
    print("\n[5/7] Step 5: Submitting change request for human review...")
    sub = submit_change_request(cr.id)
    print(f"      Status: {sub['status']}")

    # Step 6: Human Approval
    print("\n[6/7] Step 6: Human approval gate...")
    appr = approve_change_request(cr.id, reviewer="Maya Rao (Product Owner)")
    print(f"      Status: {appr['status']} by {appr['cr'].approved_by}")

    # Step 7: Merge into kb_main
    print("\n[7/7] Step 7: Merging into production kb_main with history preservation...")
    merged = merge_change_request(cr.id)
    print(f"      Status: {merged['status']} at revision {merged['revision']}")

    # Post-Merge Verification
    print("\n" + "=" * 70)
    print("VERIFYING POST-MERGE PRODUCTION GRAPH (kb_main)")
    print("=" * 70)
    main = get_graph("kb_main")

    m_facts = main.query(
        "MATCH (f:Fact {key:'pricing.pro.monthly'}) RETURN f.id, f.value, f.status ORDER BY f.version"
    ).result_set
    print(f"1. Monthly Facts in kb_main:")
    for row in m_facts:
        print(f"   - {row[0]}: value={row[1]}, status={row[2]}")
    assert m_facts == [["fact:pricing.pro.monthly@v1", 49, "SUPERSEDED"], ["fact:pricing.pro.monthly@v2", 59, "ACTIVE"]]

    a_facts = main.query(
        "MATCH (f:Fact {key:'pricing.pro.annual'}) RETURN f.id, f.value, f.status ORDER BY f.version"
    ).result_set
    print(f"2. Annual Facts in kb_main:")
    for row in a_facts:
        print(f"   - {row[0]}: value={row[1]}, status={row[2]}")
    assert a_facts == [["fact:pricing.pro.annual@v1", 490, "SUPERSEDED"], ["fact:pricing.pro.annual@v2", 590, "ACTIVE"]]

    cites_v2 = main.query(
        "MATCH (d:Document)-[:CITES]->(f:Fact {status:'ACTIVE'}) RETURN d.id, f.id ORDER BY d.id"
    ).result_set
    print(f"3. Active Citations in kb_main (Re-pointed):")
    for row in cites_v2:
        print(f"   - {row[0]} -> {row[1]}")

    stale_docs = main.query(
        "MATCH (d:Document {status:'NEEDS_REVIEW'}) RETURN d.id"
    ).result_set
    print(f"4. Documents remaining in NEEDS_REVIEW (multi-hop without literal):")
    for row in stale_docs:
        print(f"   - {row[0]}")
    assert len(stale_docs) == 3

    print("\nSCENARIO A COMPLETED SUCCESSFULLY WITH 100% CORRECTNESS!")
    print("=" * 70)


if __name__ == "__main__":
    run()

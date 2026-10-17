"""
Tests for change request submit, approval, rejection, and merge procedures (Block 2.7).
"""
import pytest
from backend.app.db import get_falkordb, get_graph
from backend.app.models import CRStatus
from backend.app.seed.seed import seed_graph
from backend.app.services.branching import delete_branch
from backend.app.services.change_requests import create_change_request
from backend.app.services.checks import analyze_change_request
from backend.app.services.edits import propose_edits_for_cr
from backend.app.services.merge import (
    approve_change_request,
    merge_change_request,
    reject_change_request,
    submit_change_request,
)


@pytest.fixture(autouse=True)
def clean_db():
    seed_graph("kb_main", drop_existing=True)


@pytest.mark.db
def test_full_scenario_a_merge_lifecycle():
    # 1. Propose change
    cr = create_change_request(
        title="Raise Pro monthly to $59",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
    )

    # 2. Analyze (BLOCKED initially due to STALE_DEPENDENCY)
    res_analyze = analyze_change_request(cr.id)
    assert res_analyze["status"] == CRStatus.BLOCKED.value

    # 3. Draft edits
    propose_edits_for_cr(cr.id)

    # 4. Re-analyze (passes!)
    res_analyze2 = analyze_change_request(cr.id)
    assert res_analyze2["status"] == CRStatus.CHECKS_PASSED.value

    # 5. Submit for approval
    res_submit = submit_change_request(cr.id)
    assert res_submit["status"] == CRStatus.READY_FOR_REVIEW.value

    # 6. Approve
    res_approve = approve_change_request(cr.id, reviewer="Maya Rao")
    assert res_approve["status"] == CRStatus.APPROVED.value
    assert res_approve["cr"].approved_by == "Maya Rao"

    # 7. Merge into kb_main
    res_merge = merge_change_request(cr.id)
    assert res_merge["status"] == CRStatus.MERGED.value
    assert res_merge["revision"] == 2

    # Verify kb_main state
    client = get_falkordb()
    main = client.select_graph("kb_main")

    # Facts: monthly@v1 is SUPERSEDED, monthly@v2 is ACTIVE
    m1 = main.query("MATCH (f:Fact {id:'fact:pricing.pro.monthly@v1'}) RETURN f.status, f.value").result_set
    m2 = main.query("MATCH (f:Fact {id:'fact:pricing.pro.monthly@v2'}) RETURN f.status, f.value").result_set
    assert m1 == [["SUPERSEDED", 49]]
    assert m2 == [["ACTIVE", 59]]

    # Facts: annual@v1 is SUPERSEDED, annual@v2 is ACTIVE
    a1 = main.query("MATCH (f:Fact {id:'fact:pricing.pro.annual@v1'}) RETURN f.status, f.value").result_set
    a2 = main.query("MATCH (f:Fact {id:'fact:pricing.pro.annual@v2'}) RETURN f.status, f.value").result_set
    assert a1 == [["SUPERSEDED", 490]]
    assert a2 == [["ACTIVE", 590]]

    # Derived fact edge connects annual@v2 -> monthly@v2
    derived = main.query(
        "MATCH (:Fact {id:'fact:pricing.pro.annual@v2'})-[r:DERIVED_FROM]->(:Fact {id:'fact:pricing.pro.monthly@v2'}) RETURN r.rule"
    ).result_set
    assert derived == [["x10"]]

    # Citations re-pointed: pricing_page now cites monthly@v2 and annual@v2
    cites = main.query(
        "MATCH (d:Document {id:'doc:pricing_page'})-[:CITES]->(f:Fact) RETURN f.id ORDER BY f.id"
    ).result_set
    assert cites == [["fact:pricing.pro.annual@v2"], ["fact:pricing.pro.monthly@v2"]]

    # Document contents updated
    deck_content = main.query("MATCH (d:Document {id:'doc:sales_deck'}) RETURN d.content").result_set[0][0]
    assert "$59/month" in deck_content
    assert "$149/month" in deck_content

    # Multi-hop derived documents without literals stay NEEDS_REVIEW
    macro_status = main.query("MATCH (d:Document {id:'doc:support_macro_upgrade'}) RETURN d.status").result_set[0][0]
    assert macro_status == "NEEDS_REVIEW"

    # Branch was deleted
    assert cr.branch_graph not in client.list_graphs()

    # Calling merge again is idempotent
    second_merge = merge_change_request(cr.id)
    assert second_merge["status"] == "MERGED"
    assert second_merge["already_merged"] is True


@pytest.mark.db
def test_reject_change_request_deletes_branch():
    cr = create_change_request(
        title="Unwanted change",
        fact_key="pricing.pro.monthly",
        new_value=120,
    )
    client = get_falkordb()
    assert cr.branch_graph in client.list_graphs()

    # Run analysis first (transitions DRAFT -> BLOCKED because no source and no edits)
    analyze_change_request(cr.id)

    res = reject_change_request(cr.id, reviewer="Arjun", reason="Too expensive")
    assert res["status"] == CRStatus.REJECTED.value
    assert cr.branch_graph not in client.list_graphs()

    # Main graph remains on v1 with 49
    main = client.select_graph("kb_main")
    monthly = main.query("MATCH (f:Fact {key:'pricing.pro.monthly', status:'ACTIVE'}) RETURN f.value").result_set[0][0]
    assert monthly == 49

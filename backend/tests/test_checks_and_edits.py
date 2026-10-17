"""
Tests for quality checks, analyze pipeline, and deterministic edit proposals (Blocks 2.4, 2.5, 2.6).
"""
import pytest
from backend.app.db import get_falkordb, get_graph
from backend.app.models import CRStatus, CheckCode, CheckSeverity
from backend.app.seed.seed import seed_graph
from backend.app.services.branching import delete_branch
from backend.app.services.change_requests import create_change_request
from backend.app.services.checks import analyze_change_request, run_quality_checks
from backend.app.services.edits import propose_edits_for_cr


@pytest.fixture(autouse=True)
def clean_database():
    seed_graph("kb_main", with_contradiction=False, drop_existing=True)


@pytest.mark.db
def test_scenario_a_full_analysis_and_edit_cycle():
    # 1. Propose change
    cr = create_change_request(
        title="Raise Pro monthly to $59",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
    )

    # 2. Initial analysis must BLOCK on STALE_DEPENDENCY
    res1 = analyze_change_request(cr.id)
    assert res1["status"] == CRStatus.BLOCKED.value
    stale_check = next(c for c in res1["checks"] if c["code"] == CheckCode.STALE_DEPENDENCY.value)
    assert stale_check["passed"] is False
    assert len(stale_check["evidence"]) == 7  # all 7 impacted docs uncovered

    # 3. Baseline comparison returned accurately
    assert res1["baseline"]["naive_search"]["found_count"] == 6
    assert res1["baseline"]["exact_regex"]["found_count"] == 5
    assert res1["baseline"]["graph_traversal"]["found_count"] == 7
    assert "doc:careers_page" in res1["baseline"]["naive_search"]["false_positives"]
    assert "doc:partner_faq" in res1["baseline"]["graph_traversal"]["dark_dependencies"]

    # 4. Draft edits deterministically
    edit_summary = propose_edits_for_cr(cr.id)
    assert len(edit_summary["edits"]) == 4  # pricing_page, sales_deck, faq, revenue_forecast_q4
    assert len(edit_summary["marked_stale"]) == 3  # support_macro_upgrade, investor_update, board_deck

    # Verify sales_deck has $59 but $149 is untouched
    deck_edit = next(e for e in edit_summary["edits"] if e["doc_id"] == "doc:sales_deck")
    assert "$59/month" in deck_edit["after"]
    assert "$149/month" in deck_edit["after"]

    # Verify pricing_page has $59 and $590
    pricing_edit = next(e for e in edit_summary["edits"] if e["doc_id"] == "doc:pricing_page")
    assert "$59 per month" in pricing_edit["after"]
    assert "$590 per year" in pricing_edit["after"]

    # 5. Re-run analysis -> All BLOCK checks must PASS -> CHECKS_PASSED!
    res2 = analyze_change_request(cr.id)
    assert res2["status"] == CRStatus.CHECKS_PASSED.value

    stale_check2 = next(c for c in res2["checks"] if c["code"] == CheckCode.STALE_DEPENDENCY.value)
    assert stale_check2["passed"] is True

    # LITERAL_VALUE_LEAK is a warning on partner_faq
    leak_check = next(c for c in res2["checks"] if c["code"] == CheckCode.LITERAL_VALUE_LEAK.value)
    assert leak_check["passed"] is False
    assert leak_check["severity"] == CheckSeverity.WARN.value
    assert leak_check["evidence"] == ["doc:partner_faq"]

    delete_branch(cr.branch_graph)


@pytest.mark.db
def test_scenario_b_unverified_source_blocks():
    # Source is unverified Slack rumor (valid=False, trust=0.2)
    cr = create_change_request(
        title="Unverified Slack Rumor",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:slack_rumor_2026_10",
    )

    res = analyze_change_request(cr.id)
    assert res["status"] == CRStatus.BLOCKED.value

    src_check = next(c for c in res["checks"] if c["code"] == CheckCode.SOURCE_INVALID.value)
    assert src_check["passed"] is False
    assert src_check["severity"] == CheckSeverity.BLOCK.value

    delete_branch(cr.branch_graph)


@pytest.mark.db
def test_scenario_c_regional_contradiction_blocks():
    # Seed graph with EU contradiction
    seed_graph("kb_main", with_contradiction=True, drop_existing=True)

    cr = create_change_request(
        title="Contradiction Test",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
    )

    res = analyze_change_request(cr.id)
    assert res["status"] == CRStatus.BLOCKED.value

    contra_check = next(c for c in res["checks"] if c["code"] == CheckCode.CONTRADICTION.value)
    assert contra_check["passed"] is False
    assert contra_check["severity"] == CheckSeverity.BLOCK.value
    assert len(contra_check["evidence"]) == 1

    delete_branch(cr.branch_graph)

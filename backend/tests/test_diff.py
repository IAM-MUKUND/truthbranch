"""
Tests for deterministic diff engine (Block 2.3).
"""
import pytest
from backend.app.db import get_falkordb, get_graph
from backend.app.seed.seed import seed_graph
from backend.app.services.change_requests import create_change_request
from backend.app.services.branching import delete_branch
from backend.app.services.diff import compute_branch_diff
from backend.app.models import Operation, OpType
from backend.app.services.operations import apply_operations_to_graph


@pytest.fixture(scope="module", autouse=True)
def setup_main():
    seed_graph("kb_main", drop_existing=True)


@pytest.mark.db
def test_diff_engine_detects_fact_changes_and_status():
    cr = create_change_request(
        title="Raise Pro monthly to $59",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
    )
    client = get_falkordb()
    main = client.select_graph("kb_main")
    branch = client.select_graph(cr.branch_graph)

    # Add a proposed edit and mark stale on the branch
    apply_operations_to_graph(
        branch,
        [
            Operation(
                op_type=OpType.PROPOSE_EDIT,
                doc_id="doc:pricing_page",
                before="old text",
                after="new text",
            ),
            Operation(
                op_type=OpType.MARK_STALE,
                node_id="doc:support_macro_upgrade",
                reason="Derived from FAQ",
            ),
        ],
    )

    diff = compute_branch_diff(main, branch)

    # Fact diffs
    assert len(diff["facts"]) == 2
    keys = {f["key"] for f in diff["facts"]}
    assert keys == {"pricing.pro.monthly", "pricing.pro.annual"}
    monthly = next(f for f in diff["facts"] if f["key"] == "pricing.pro.monthly")
    assert monthly["old_value"] == 49
    assert monthly["new_value"] == 59
    assert monthly["old_id"] == "fact:pricing.pro.monthly@v1"
    assert monthly["new_id"] == "fact:pricing.pro.monthly@v2"

    annual = next(f for f in diff["facts"] if f["key"] == "pricing.pro.annual")
    assert annual["old_value"] == 490
    assert annual["new_value"] == 590

    # Edits
    assert len(diff["edits"]) == 1
    assert diff["edits"][0]["doc_id"] == "doc:pricing_page"
    assert diff["edits"][0]["before"] == "old text"
    assert diff["edits"][0]["after"] == "new text"

    # Status changes
    assert len(diff["doc_status_changes"]) == 1
    assert diff["doc_status_changes"][0]["doc_id"] == "doc:support_macro_upgrade"
    assert diff["doc_status_changes"][0]["main_status"] == "CURRENT"
    assert diff["doc_status_changes"][0]["branch_status"] == "NEEDS_REVIEW"

    delete_branch(cr.branch_graph)

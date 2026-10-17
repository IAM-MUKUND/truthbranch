"""
Tests for Agent Tools Layer (Sprint 3 Block 3.1).
Verifies:
- Tool definitions and Pydantic validation.
- Hard limits: no merge or approve tools allowed.
- Tool executions (lineage, impact, checks, submit refusal).
"""
import pytest
from backend.app.agent.tools import (
    TOOL_DEFINITIONS,
    TOOL_FUNCTIONS,
    execute_tool,
    get_lineage,
)
from backend.app.db import get_falkordb
from backend.app.seed.seed import seed_graph
from backend.app.services.branching import create_branch
from backend.app.services.meta import reset_meta, save_change_request
from backend.app.models import ChangeRequest, Operation, OpType, CRStatus


@pytest.fixture(autouse=True)
def setup_db():
    seed_graph()
    reset_meta()


def test_hard_limits_agent_catalog():
    """Assert that merge and approve tools are strictly absent from the catalog."""
    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "merge" not in names
    assert "approve" not in names
    assert "merge_change_request" not in names
    assert "approve_change_request" not in names

    assert "merge" not in TOOL_FUNCTIONS
    assert "approve" not in TOOL_FUNCTIONS

    # Direct execution attempt must return security violation
    res = execute_tool("merge", {"cr_id": "test"})
    assert "Security violation" in res.get("error", "")

    res_app = execute_tool("approve", {"cr_id": "test"})
    assert "Security violation" in res_app.get("error", "")


def test_tool_argument_validation():
    """Test Pydantic argument validation rejects invalid input."""
    res = execute_tool("get_lineage", {})
    assert "Argument validation error" in res.get("error", "")

    res_str = execute_tool("get_lineage", "not json")
    assert "Invalid JSON arguments" in res_str.get("error", "")


def test_get_lineage_tool():
    """Test get_lineage returns version and source details."""
    res = execute_tool("get_lineage", {"fact_id": "fact:pricing.pro.monthly@v1"})
    assert res["fact_id"] == "fact:pricing.pro.monthly@v1"
    assert len(res["versions"]) >= 1
    assert res["versions"][0]["value"] == 49
    assert len(res["sources"]) >= 1
    assert res["sources"][0]["valid"] is True


from backend.app.schema import branch_graph_name

def test_submit_for_approval_refuses_blocking_checks():
    """Test submit_for_approval refuses when blocking checks fail."""
    cr_id = "cr_test_tools_001"
    branch = create_branch(cr_id)
    cr = ChangeRequest(
        id=cr_id,
        title="Test Price Change",
        fact_key="pricing.pro.monthly",
        new_value=59,
        branch_graph=branch_graph_name(cr_id),
        status=CRStatus.DRAFT,
        ops=[],
    )
    save_change_request(cr)

    # Submit without drafted edits should refuse because STALE_DEPENDENCY fails
    res = execute_tool("submit_for_approval", {"cr_id": cr_id})
    assert res.get("refused") is True
    assert "blocking" in res.get("error", "").lower()

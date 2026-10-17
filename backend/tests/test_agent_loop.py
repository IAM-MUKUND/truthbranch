"""
Tests for Agent Loop and Review Endpoint (Sprint 3 Blocks 3.2 and 3.3).
Tests:
- Scripted agent on Scenario A (successful review, drafts edits, submits).
- Scripted agent on Scenario B (untrusted source -> refusal & verification request).
- Agent review API endpoint.
- Agent step persistence in kb_meta.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.agent.scripted import run_scripted_agent
from backend.app.main import app
from backend.app.models import CRStatus
from backend.app.schema import branch_graph_name
from backend.app.seed.seed import seed_graph
from backend.app.services.change_requests import create_change_request
from backend.app.services.meta import get_agent_steps, get_change_request, reset_meta

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    seed_graph()
    reset_meta()


def test_scripted_agent_scenario_a():
    """Scenario A: Trusted source -> agent inspects, drafts edits, runs checks, submits."""
    cr = create_change_request(
        title="Pro Monthly Price Increase",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
        created_by="user:maya",
    )
    assert cr.status == CRStatus.DRAFT

    res = run_scripted_agent(cr.id)
    assert res["submitted"] is True
    assert res["verdict"] == "READY_FOR_REVIEW"
    assert len(res["steps"]) >= 4

    # Verify steps logged in kb_meta
    saved_steps = get_agent_steps(cr.id)
    assert len(saved_steps) >= 4
    tool_names = [s["tool"] for s in saved_steps]
    assert "get_lineage" in tool_names
    assert "get_impact" in tool_names
    assert "propose_edits_for_affected_docs" in tool_names
    assert "submit_for_approval" in tool_names

    # Verify CR status updated
    updated_cr = get_change_request(cr.id)
    assert updated_cr.status == CRStatus.READY_FOR_REVIEW


def test_scripted_agent_scenario_b_untrusted_source():
    """Scenario B: Untrusted Slack rumor -> agent halts, requests verification, does not submit."""
    cr = create_change_request(
        title="Slack Rumor Price Drop",
        fact_key="pricing.pro.monthly",
        new_value=39,
        source_id="src:slack_rumor_2026_10",  # valid=False, trust=0.2
        created_by="user:anon",
    )

    res = run_scripted_agent(cr.id)
    assert res["submitted"] is False
    assert res["verdict"] == "VERIFICATION_REQUESTED"

    tool_names = [s["tool"] for s in res["steps"]]
    assert "get_lineage" in tool_names
    assert "request_verification" in tool_names
    # Agent must NEVER draft edits or submit for approval on untrusted source
    assert "propose_edits_for_affected_docs" not in tool_names
    assert "submit_for_approval" not in tool_names


def test_agent_review_api_endpoint():
    """Test POST /api/change-requests/{id}/agent-review endpoint."""
    cr = create_change_request(
        title="Pro Monthly Price Increase API Test",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
    )

    resp = client.post(f"/api/change-requests/{cr.id}/agent-review")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cr_id"] == cr.id
    assert "verdict" in data
    assert "steps" in data
    assert len(data["steps"]) >= 1

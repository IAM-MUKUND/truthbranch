"""
API Integration tests for FastAPI endpoints (Checklist Section 12).
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.seed.seed import seed_graph


@pytest.fixture(autouse=True)
def reset_db():
    seed_graph("kb_main", drop_existing=True)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["falkordb"] == "connected"


def test_admin_reset_demo(client):
    res = client.post("/api/admin/reset-demo", json={"with_contradiction": False})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["nodes"] == 29
    assert data["edges"] == 41


def test_facts_lineage(client):
    res = client.get("/api/facts/fact:pricing.pro.monthly@v1/lineage")
    assert res.status_code == 200
    data = res.json()
    assert data["fact"]["key"] == "pricing.pro.monthly"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["valid"] is True


def test_full_api_change_request_flow(client):
    # 1. Create CR
    create_res = client.post(
        "/api/change-requests",
        json={
            "title": "Raise Pro Monthly to $59",
            "fact_key": "pricing.pro.monthly",
            "new_value": 59,
            "source_id": "src:pricing_committee_memo_2026_10",
        },
    )
    assert create_res.status_code == 200
    cr_id = create_res.json()["id"]

    # 2. Get Detail
    detail_res = client.get(f"/api/change-requests/{cr_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["cr"]["id"] == cr_id
    assert len(detail_res.json()["impact"]) == 7

    # 3. Analyze (BLOCKED)
    analyze_res1 = client.post(f"/api/change-requests/{cr_id}/analyze")
    assert analyze_res1.status_code == 200
    assert analyze_res1.json()["status"] == "BLOCKED"

    # 4. Propose Edits
    edits_res = client.post(f"/api/change-requests/{cr_id}/propose-edits")
    assert edits_res.status_code == 200
    assert len(edits_res.json()["edits"]) == 4

    # 5. Re-analyze (CHECKS_PASSED)
    analyze_res2 = client.post(f"/api/change-requests/{cr_id}/analyze")
    assert analyze_res2.status_code == 200
    assert analyze_res2.json()["status"] == "CHECKS_PASSED"

    # 6. Submit
    submit_res = client.post(f"/api/change-requests/{cr_id}/submit")
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "READY_FOR_REVIEW"

    # 7. Approve
    approve_res = client.post(
        f"/api/change-requests/{cr_id}/approve",
        json={"reviewer": "Maya Rao"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # 8. Merge
    merge_res = client.post(f"/api/change-requests/{cr_id}/merge")
    assert merge_res.status_code == 200
    assert merge_res.json()["status"] == "MERGED"
    assert merge_res.json()["revision"] == 2


def test_entities_endpoint(client):
    res = client.get("/api/entities")
    assert res.status_code == 200
    data = res.json()
    assert "people" in data
    assert "facts" in data
    assert "sources" in data
    assert len(data["people"]) >= 5
    assert len(data["facts"]) >= 2


def test_chat_endpoint(client):
    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "What is the Pro plan monthly cost?"}]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "assistant"
    assert "$49" in data["content"] or "49" in data["content"]
    assert len(data["citations"]) >= 1

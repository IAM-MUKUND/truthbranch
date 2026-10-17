"""
Tests for Change Request creation, branch isolation, and operation application (Block 2.2).
"""
import pytest
from backend.app.db import get_falkordb, get_graph
from backend.app.seed.seed import seed_graph
from backend.app.services.change_requests import create_change_request
from backend.app.services.branching import delete_branch


@pytest.fixture(scope="module", autouse=True)
def setup_main():
    seed_graph("kb_main", drop_existing=True)


@pytest.mark.db
def test_create_cr_creates_branch_with_v2_facts():
    cr = create_change_request(
        title="Raise Pro monthly to $59",
        fact_key="pricing.pro.monthly",
        new_value=59,
        source_id="src:pricing_committee_memo_2026_10",
    )
    assert cr.id.startswith("cr_")
    assert cr.branch_graph.startswith("kb_cr_")
    assert len(cr.ops) >= 2  # monthly update, attach source, annual update, attach source

    client = get_falkordb()
    branch = client.select_graph(cr.branch_graph)
    main = client.select_graph("kb_main")

    # 1. Branch has v2 active for monthly
    branch_monthly = branch.query(
        "MATCH (f:Fact {key:'pricing.pro.monthly', status:'ACTIVE'}) RETURN f.id, f.value, f.version"
    ).result_set
    assert branch_monthly == [["fact:pricing.pro.monthly@v2", 59, 2]]

    # 2. Branch has v2 active for annual (derived, 590)
    branch_annual = branch.query(
        "MATCH (f:Fact {key:'pricing.pro.annual', status:'ACTIVE'}) RETURN f.id, f.value, f.version"
    ).result_set
    assert branch_annual == [["fact:pricing.pro.annual@v2", 590, 2]]

    # 3. Branch has supersedes edges
    supersedes = branch.query(
        "MATCH (new:Fact)-[:SUPERSEDES]->(old:Fact) RETURN new.id, old.id ORDER BY new.id"
    ).result_set
    assert len(supersedes) == 2
    assert supersedes[0] == ["fact:pricing.pro.annual@v2", "fact:pricing.pro.annual@v1"]
    assert supersedes[1] == ["fact:pricing.pro.monthly@v2", "fact:pricing.pro.monthly@v1"]

    # 4. kb_main remains 100% on v1
    main_monthly = main.query(
        "MATCH (f:Fact {key:'pricing.pro.monthly', status:'ACTIVE'}) RETURN f.id, f.value, f.version"
    ).result_set
    assert main_monthly == [["fact:pricing.pro.monthly@v1", 49, 1]]

    main_annual = main.query(
        "MATCH (f:Fact {key:'pricing.pro.annual', status:'ACTIVE'}) RETURN f.id, f.value, f.version"
    ).result_set
    assert main_annual == [["fact:pricing.pro.annual@v1", 490, 1]]

    # Clean up
    delete_branch(cr.branch_graph)


@pytest.mark.db
def test_two_crs_create_two_independent_branches():
    cr1 = create_change_request("CR 1", "pricing.pro.monthly", 65)
    cr2 = create_change_request("CR 2", "pricing.pro.monthly", 75)

    client = get_falkordb()
    b1 = client.select_graph(cr1.branch_graph)
    b2 = client.select_graph(cr2.branch_graph)
    main = client.select_graph("kb_main")

    v1 = b1.query("MATCH (f:Fact {key:'pricing.pro.monthly', status:'ACTIVE'}) RETURN f.value").result_set[0][0]
    v2 = b2.query("MATCH (f:Fact {key:'pricing.pro.monthly', status:'ACTIVE'}) RETURN f.value").result_set[0][0]
    v_main = main.query("MATCH (f:Fact {key:'pricing.pro.monthly', status:'ACTIVE'}) RETURN f.value").result_set[0][0]

    assert v1 == 65
    assert v2 == 75
    assert v_main == 49

    delete_branch(cr1.branch_graph)
    delete_branch(cr2.branch_graph)


@pytest.mark.db
def test_invalid_fact_key_raises_error():
    with pytest.raises(ValueError, match="No ACTIVE fact found"):
        create_change_request("Bogus Fact", "nonexistent.key", 100)

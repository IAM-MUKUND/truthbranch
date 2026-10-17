"""
Tests for multi-tenant dataset catalog, idempotent switching, zero-duplication guarantee,
and custom dataset ingestion API.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import get_falkordb, get_active_dataset_id, get_active_graph_name

client = TestClient(app)


def test_datasets_catalog_listing():
    """Verify catalog lists available company datasets."""
    res = client.get("/api/admin/datasets/catalog")
    assert res.status_code == 200
    data = res.json()
    assert "catalog" in data
    assert "active_dataset" in data
    ids = [d["id"] for d in data["catalog"]]
    assert "lumen" in ids
    assert "cloudgrid" in ids


def test_activate_cloudgrid_idempotency_zero_duplication():
    """Verify switching to CloudGrid creates it once, and second call does not reseed (zero duplication)."""
    falkor = get_falkordb()

    # Clean up any preexisting cloudgrid graph to test clean first run
    try:
        falkor.select_graph("kb_dataset_cloudgrid").delete()
    except Exception:
        pass

    # 1. First activation: should create and seed
    res1 = client.post("/api/admin/datasets/activate", json={"dataset_id": "cloudgrid", "force_reseed": False})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "ok"
    assert data1["dataset_id"] == "cloudgrid"
    assert data1["graph_name"] == "kb_dataset_cloudgrid"
    assert data1["reseeded"] is True
    assert data1["nodes"] > 0
    first_nodes = data1["nodes"]

    # Assert active pointers
    assert get_active_dataset_id() == "cloudgrid"
    assert get_active_graph_name() == "kb_dataset_cloudgrid"

    # Verify entities router returns CloudGrid facts & people
    ent_res = client.get("/api/entities")
    assert ent_res.status_code == 200
    ent_data = ent_res.json()
    fact_keys = [f["key"] for f in ent_data["facts"]]
    assert "compute.h100.hourly" in fact_keys
    people_names = [p["name"] for p in ent_data["people"]]
    assert "Sarah Lin" in people_names

    # 2. Second activation: MUST NOT reseed! MUST report reseeded=False (Zero Duplication)
    res2 = client.post("/api/admin/datasets/activate", json={"dataset_id": "cloudgrid", "force_reseed": False})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "ok"
    assert data2["reseeded"] is False
    assert data2["nodes"] == first_nodes
    assert "zero duplication" in data2["message"].lower()

    # 3. Switch back to Lumen
    res_lumen = client.post("/api/admin/datasets/activate", json={"dataset_id": "lumen", "force_reseed": False})
    assert res_lumen.status_code == 200
    assert get_active_dataset_id() == "lumen"

    # Entities should now be Lumen again
    ent_res_lumen = client.get("/api/entities")
    assert ent_res_lumen.status_code == 200
    lumen_facts = [f["key"] for f in ent_res_lumen.json()["facts"]]
    assert "pricing.pro.monthly" in lumen_facts
    lumen_people = [p["name"] for p in ent_res_lumen.json()["people"]]
    assert "Maya Rao" in lumen_people


def test_custom_dataset_ingest_referential_integrity():
    """Verify custom dataset ingestion rejects dangling foreign keys with 422."""
    bad_payload = {
        "id": "broken_dataset",
        "name": "Broken Dataset",
        "domain": "Testing",
        "people": [{"id": "p:alice", "name": "Alice", "role": "Engineer", "email": "a@ex.com"}],
        "systems": [{"id": "sys:web", "name": "Web"}],
        "sources": [{"id": "src:memo", "title": "Memo", "kind": "memo", "valid": True, "trust": 0.9}],
        "facts": [{"id": "fact:test@v1", "key": "test.fact", "version": 1, "subject": "test", "attribute": "attr", "value": 10, "unit": "units", "status": "ACTIVE"}],
        "documents": [{"id": "doc:readme", "title": "Readme", "kind": "doc", "status": "CURRENT", "content": "hello"}],
        # Dangling citation pointing to non-existent fact:missing@v1
        "doc_cites": [{"doc": "doc:readme", "fact": "fact:missing@v1"}],
    }
    res = client.post("/api/admin/datasets/ingest", json=bad_payload)
    assert res.status_code == 422
    assert "Dangling edge" in res.json()["detail"]


def test_custom_dataset_ingest_and_activate():
    """Verify successfully ingesting a valid custom dataset."""
    falkor = get_falkordb()
    try:
        falkor.select_graph("kb_dataset_novapay").delete()
    except Exception:
        pass

    valid_payload = {
        "id": "novapay",
        "name": "NovaPay Gateway",
        "domain": "FinTech & Payments",
        "people": [{"id": "p:marcus", "name": "Marcus Vance", "role": "Risk Lead", "email": "m@novapay.io"}],
        "systems": [{"id": "sys:core", "name": "Core Banking Engine"}],
        "sources": [{"id": "src:fee_schedule", "title": "2026 Interchange Fee Schedule", "kind": "memo", "valid": True, "trust": 0.95}],
        "facts": [{"id": "fact:interchange.fee@v1", "key": "interchange.fee", "version": 1, "subject": "payment_processing", "attribute": "fixed_fee", "value": 0.25, "unit": "USD", "status": "ACTIVE"}],
        "documents": [{"id": "doc:merchant_agreement", "title": "Merchant Agreement", "kind": "contract", "status": "CURRENT", "content": "Standard interchange fee is fixed at $0.25 per settled transaction."}],
        "fact_sourced": [{"fact": "fact:interchange.fee@v1", "source": "src:fee_schedule"}],
        "fact_owned": [{"fact": "fact:interchange.fee@v1", "person": "p:marcus"}],
        "doc_cites": [{"doc": "doc:merchant_agreement", "fact": "fact:interchange.fee@v1"}],
        "doc_published": [{"doc": "doc:merchant_agreement", "system": "sys:core"}],
        "doc_owned": [{"doc": "doc:merchant_agreement", "person": "p:marcus"}],
    }

    try:
        res = client.post("/api/admin/datasets/ingest?activate=true", json=valid_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["dataset_id"] == "novapay"
        assert data["graph_name"] == "kb_dataset_novapay"
        assert data["reseeded"] is True

        # Active dataset is now novapay
        assert get_active_dataset_id() == "novapay"

        # Entities should show NovaPay
        ent_res = client.get("/api/entities")
        assert ent_res.status_code == 200
        ent_data = ent_res.json()
        assert any(f["key"] == "interchange.fee" for f in ent_data["facts"])
        assert any(p["name"] == "Marcus Vance" for p in ent_data["people"])
    finally:
        # Reset back to Lumen
        client.post("/api/admin/datasets/activate", json={"dataset_id": "lumen", "force_reseed": False})
        assert get_active_dataset_id() == "lumen"
        try:
            falkor.select_graph("kb_dataset_novapay").delete()
        except Exception:
            pass


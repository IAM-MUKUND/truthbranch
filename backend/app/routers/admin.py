"""
Admin router for resetting demo, managing dataset catalog, and ingesting custom knowledge graphs.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.db import get_falkordb, get_active_dataset_id, get_active_graph_name
from backend.app.models import DatasetIngestPayload
from backend.app.seed.datasets import CATALOG, list_catalog_entries, get_catalog_entry
from backend.app.seed.seed import seed_graph, ensure_dataset_graph, ingest_dataset_to_graph
from backend.app.services.meta import reset_meta, set_meta_active_dataset

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ResetDemoRequest(BaseModel):
    with_contradiction: bool = False


class ActivateDatasetRequest(BaseModel):
    dataset_id: str
    force_reseed: bool = False


@router.get("/datasets/catalog")
def get_datasets_catalog():
    """List all available datasets in the catalog with active and seeded statuses."""
    client = get_falkordb()
    existing_graphs = set(client.list_graphs())
    active_id = get_active_dataset_id()

    catalog = []
    for entry in list_catalog_entries():
        gname = entry["default_graph"]
        catalog.append({
            **entry,
            "is_active": entry["id"] == active_id,
            "is_seeded": gname in existing_graphs,
        })
    return {"active_dataset": active_id, "catalog": catalog}


@router.post("/datasets/activate")
def activate_dataset(req: ActivateDatasetRequest):
    """Switch active company knowledge base to a catalog dataset with zero duplicate queries."""
    client = get_falkordb()
    entry = get_catalog_entry(req.dataset_id)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dataset '{req.dataset_id}'. Available: {list(CATALOG.keys())}",
        )

    # Idempotent ensure: seeds only if not already in FalkorDB (or if force_reseed=True)
    res = ensure_dataset_graph(dataset_id=req.dataset_id, force_reseed=req.force_reseed, client=client)

    # Update active dataset pointer in kb_meta
    set_meta_active_dataset(dataset_id=req.dataset_id, graph_name=res["graph_name"])

    return {
        "status": "ok",
        "dataset_id": req.dataset_id,
        "name": entry["name"],
        "graph_name": res["graph_name"],
        "reseeded": res["reseeded"],
        "nodes": res["nodes"],
        "edges": res["edges"],
        "message": "Switched to existing graph (zero duplication)." if not res["reseeded"] else "Graph seeded and activated.",
    }


@router.post("/datasets/ingest")
def ingest_custom_dataset(payload: DatasetIngestPayload, activate: bool = Query(True), force_reseed: bool = Query(False)):
    """Ingest an arbitrary carefully curated company dataset JSON into a new FalkorDB graph."""
    try:
        payload.validate_referential_integrity()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    client = get_falkordb()
    graph_name = f"kb_dataset_{payload.id}"
    existing_graphs = set(client.list_graphs())

    if graph_name in existing_graphs and not force_reseed:
        if activate:
            set_meta_active_dataset(dataset_id=payload.id, graph_name=graph_name)
        return {
            "status": "ok",
            "dataset_id": payload.id,
            "graph_name": graph_name,
            "reseeded": False,
            "activated": activate,
            "message": "Graph already exists. Activated without duplicating nodes.",
        }

    # Transform payload to dict for generic ingest
    ds_dict = payload.model_dump()
    res = ingest_dataset_to_graph(ds=ds_dict, graph_name=graph_name, drop_existing=True, client=client)

    if activate:
        set_meta_active_dataset(dataset_id=payload.id, graph_name=graph_name)

    return {
        "status": "ok",
        "dataset_id": payload.id,
        "graph_name": graph_name,
        "reseeded": True,
        "activated": activate,
        "nodes": res["nodes"],
        "edges": res["edges"],
        "message": f"Custom dataset '{payload.name}' successfully ingested into {graph_name}.",
    }


@router.post("/reset-demo")
def reset_demo(req: ResetDemoRequest = ResetDemoRequest()):
    """Wipe branches, reset kb_meta, and reseed active dataset cleanly."""
    client = get_falkordb()

    # 1. Delete all branch graphs
    for gname in client.list_graphs():
        if gname.startswith("kb_cr_"):
            try:
                client.select_graph(gname).delete()
            except Exception:
                pass

    # 2. Reset kb_meta
    reset_meta()

    # 3. Reseed active dataset
    active_id = get_active_dataset_id()
    if active_id != "lumen" and active_id in CATALOG:
        res = ensure_dataset_graph(dataset_id=active_id, force_reseed=True, client=client)
        set_meta_active_dataset(dataset_id=active_id, graph_name=res["graph_name"])
    else:
        res = seed_graph(
            graph_name="kb_main",
            with_contradiction=req.with_contradiction,
            drop_existing=True,
        )
        set_meta_active_dataset(dataset_id="lumen", graph_name="kb_main")

    return {
        "status": "ok",
        "message": f"Demo reset successfully for dataset '{active_id}'.",
        "nodes": res["nodes"],
        "edges": res["edges"],
        "with_contradiction": req.with_contradiction,
    }

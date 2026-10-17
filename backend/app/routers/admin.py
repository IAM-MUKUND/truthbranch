"""
Admin router for resetting demo and database state.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.db import get_falkordb
from backend.app.seed.seed import seed_graph
from backend.app.services.meta import reset_meta

router = APIRouter(prefix="/api/admin", tags=["admin"])


class ResetDemoRequest(BaseModel):
    with_contradiction: bool = False


@router.post("/reset-demo")
def reset_demo(req: ResetDemoRequest = ResetDemoRequest()):
    """Wipe branches, reset kb_meta, and reseed kb_main cleanly."""
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

    # 3. Reseed kb_main
    res = seed_graph(
        graph_name="kb_main",
        with_contradiction=req.with_contradiction,
        drop_existing=True,
    )

    return {
        "status": "ok",
        "message": "Demo reset successfully.",
        "nodes": res["nodes"],
        "edges": res["edges"],
        "with_contradiction": req.with_contradiction,
    }

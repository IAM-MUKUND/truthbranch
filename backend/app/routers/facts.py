"""
Facts router: lineage, history, and fact lookups.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException

from backend.app.db import get_graph
from backend.app.queries.lineage import (
    Q_FACT_BY_ID,
    Q_LINEAGE_SOURCES,
    Q_LINEAGE_SUPERSEDES,
    Q_LINEAGE_UPSTREAM,
)

router = APIRouter(prefix="/api/facts", tags=["facts"])


@router.get("/{fact_id:path}/lineage")
def get_fact_lineage(fact_id: str):
    """Retrieve full provenance and lineage history for a fact."""
    main = get_graph("kb_main")
    
    # 1. Fact info
    f_res = main.ro_query(Q_FACT_BY_ID, params={"fact_id": fact_id}).result_set
    if not f_res:
        raise HTTPException(status_code=404, detail=f"Fact '{fact_id}' not found.")

    fact_data = {
        "id": f_res[0][0],
        "key": f_res[0][1],
        "version": f_res[0][2],
        "value": f_res[0][3],
        "unit": f_res[0][4],
        "status": f_res[0][5],
    }

    # 2. Supersedes chain
    supersedes_res = main.ro_query(Q_LINEAGE_SUPERSEDES, params={"fact_id": fact_id}).result_set
    history = [
        {"id": r[0], "version": r[1], "value": r[2], "status": r[3]}
        for r in supersedes_res
    ]

    # 3. Sources
    sources_res = main.ro_query(Q_LINEAGE_SOURCES, params={"fact_id": fact_id}).result_set
    sources = [
        {"id": r[0], "title": r[1], "valid": r[2], "trust": r[3]}
        for r in sources_res
    ]

    # 4. Upstream derived facts
    upstream_res = main.ro_query(Q_LINEAGE_UPSTREAM, params={"fact_id": fact_id}).result_set
    upstream = [{"id": r[0], "value": r[1]} for r in upstream_res]

    return {
        "fact": fact_data,
        "history": history,
        "sources": sources,
        "upstream_facts": upstream,
    }

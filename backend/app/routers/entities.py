"""
Entities router: dynamic discovery of people, active facts, sources, and documents.
Provides dataset-agnostic metadata for frontend dropdowns and entity pickers.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter

from backend.app.db import get_falkordb

router = APIRouter(prefix="/api/entities", tags=["entities"])


@router.get("")
def get_entities() -> dict[str, Any]:
    """Retrieve all people, active facts, sources, and documents currently in the active graph."""
    from backend.app.db import get_graph
    main = get_graph("kb_main")

    # 1. People
    p_res = main.ro_query(
        "MATCH (p:Person) RETURN p.id, p.name, p.role, p.email ORDER BY p.name"
    ).result_set
    people = [
        {"id": r[0], "name": r[1], "role": r[2], "email": r[3]}
        for r in p_res
    ]

    # 2. Active Facts
    f_res = main.ro_query(
        """
        MATCH (f:Fact {status:'ACTIVE'})
        RETURN f.id, f.key, f.value, f.unit, f.subject, f.attribute, f.version
        ORDER BY f.key
        """
    ).result_set
    facts = [
        {
            "id": r[0],
            "key": r[1],
            "value": r[2],
            "unit": r[3],
            "subject": r[4],
            "attribute": r[5],
            "version": r[6],
        }
        for r in f_res
    ]

    # 3. Sources
    s_res = main.ro_query(
        "MATCH (s:Source) RETURN s.id, s.title, s.trust, s.valid, s.kind ORDER BY s.trust DESC"
    ).result_set
    sources = [
        {"id": r[0], "title": r[1], "trust": r[2], "valid": r[3], "kind": r[4]}
        for r in s_res
    ]

    # 4. Documents
    d_res = main.ro_query(
        "MATCH (d:Document) RETURN d.id, d.title, d.status ORDER BY d.title"
    ).result_set
    documents = [
        {"id": r[0], "title": r[1], "status": r[2]}
        for r in d_res
    ]

    return {
        "people": people,
        "facts": facts,
        "sources": sources,
        "documents": documents,
    }

"""
Branching service for TruthBranch: clones and manages isolated graph containers.
"""
from __future__ import annotations

from falkordb import Graph
from backend.app.db import get_falkordb, get_graph
from backend.app.schema import branch_graph_name


def get_base_revision(graph: Graph | None = None) -> int:
    """Get the current revision number of kb_main."""
    if graph is None:
        graph = get_graph("kb_main")
    res = graph.query("MATCH (m:Meta {id:'main'}) RETURN m.revision")
    if res.result_set and res.result_set[0]:
        return int(res.result_set[0][0])
    return 1


def create_branch(cr_id: str, base_graph_name: str = "kb_main") -> Graph:
    """Clone kb_main into a new isolated branch graph for the Change Request."""
    client = get_falkordb()
    target_name = branch_graph_name(cr_id)
    
    # Clean up existing branch if any
    try:
        client.select_graph(target_name).delete()
    except Exception:
        pass

    base_graph = client.select_graph(base_graph_name)
    branch = base_graph.copy(target_name)
    return branch


def delete_branch(name: str) -> None:
    """Delete a branch graph from FalkorDB."""
    client = get_falkordb()
    target_name = branch_graph_name(name)
    try:
        client.select_graph(target_name).delete()
    except Exception:
        pass

"""
Persistence for Change Requests, Audit Events, and Agent Steps in kb_meta.
"""
from __future__ import annotations

import json
from typing import Any

from backend.app.db import get_falkordb, get_graph
from backend.app.models import AuditEvent, ChangeRequest, Operation


META_GRAPH_NAME = "kb_meta"


def get_meta_graph():
    return get_graph(META_GRAPH_NAME)


def init_meta_indexes():
    g = get_meta_graph()
    for stmt in [
        "CREATE INDEX FOR (c:ChangeRequest) ON (c.id)",
        "CREATE INDEX FOR (a:AuditEvent) ON (a.cr_id)",
        "CREATE INDEX FOR (s:AgentStep) ON (s.cr_id)",
    ]:
        try:
            g.query(stmt)
        except Exception:
            pass


def save_change_request(cr: ChangeRequest) -> None:
    """Save or update a change request node in kb_meta."""
    init_meta_indexes()
    g = get_meta_graph()
    ops_json = json.dumps([op.model_dump() for op in cr.ops])

    query = """
    MERGE (c:ChangeRequest {id: $id})
    SET c.title = $title,
        c.fact_key = $fact_key,
        c.new_value = $new_value,
        c.source_id = $source_id,
        c.status = $status,
        c.branch_graph = $branch_graph,
        c.base_revision = $base_revision,
        c.ops_json = $ops_json,
        c.created_by = $created_by,
        c.created_at = $created_at,
        c.approved_by = $approved_by,
        c.merged_at = $merged_at,
        c.rejected_reason = $rejected_reason
    """
    g.query(
        query,
        params={
            "id": cr.id,
            "title": cr.title,
            "fact_key": cr.fact_key,
            "new_value": cr.new_value,
            "source_id": cr.source_id,
            "status": cr.status.value,
            "branch_graph": cr.branch_graph,
            "base_revision": cr.base_revision,
            "ops_json": ops_json,
            "created_by": cr.created_by,
            "created_at": cr.created_at,
            "approved_by": cr.approved_by,
            "merged_at": cr.merged_at,
            "rejected_reason": cr.rejected_reason,
        },
    )


def get_change_request(cr_id: str) -> ChangeRequest | None:
    """Retrieve a change request by ID."""
    g = get_meta_graph()
    res = g.query("MATCH (c:ChangeRequest {id: $id}) RETURN c", params={"id": cr_id})
    if not res.result_set:
        return None

    node = res.result_set[0][0]
    props = node.properties
    ops_data = json.loads(props.get("ops_json", "[]"))
    ops = [Operation(**item) for item in ops_data]

    return ChangeRequest(
        id=props["id"],
        title=props["title"],
        fact_key=props["fact_key"],
        new_value=props["new_value"],
        source_id=props.get("source_id"),
        status=props["status"],
        branch_graph=props["branch_graph"],
        base_revision=props.get("base_revision", 1),
        ops=ops,
        created_by=props.get("created_by", "user"),
        created_at=props.get("created_at", ""),
        approved_by=props.get("approved_by"),
        merged_at=props.get("merged_at"),
        rejected_reason=props.get("rejected_reason"),
    )


def list_change_requests() -> list[ChangeRequest]:
    """List all change requests ordered by creation time."""
    g = get_meta_graph()
    res = g.query("MATCH (c:ChangeRequest) RETURN c ORDER BY c.created_at DESC")
    crs = []
    for row in res.result_set:
        node = row[0]
        props = node.properties
        ops_data = json.loads(props.get("ops_json", "[]"))
        ops = [Operation(**item) for item in ops_data]
        crs.append(
            ChangeRequest(
                id=props["id"],
                title=props["title"],
                fact_key=props["fact_key"],
                new_value=props["new_value"],
                source_id=props.get("source_id"),
                status=props["status"],
                branch_graph=props["branch_graph"],
                base_revision=props.get("base_revision", 1),
                ops=ops,
                created_by=props.get("created_by", "user"),
                created_at=props.get("created_at", ""),
                approved_by=props.get("approved_by"),
                merged_at=props.get("merged_at"),
                rejected_reason=props.get("rejected_reason"),
            )
        )
    return crs


def record_audit_event(cr_id: str, event_type: str, detail: dict[str, Any] | None = None) -> AuditEvent:
    """Record an audit event for a change request."""
    init_meta_indexes()
    g = get_meta_graph()
    evt = AuditEvent(cr_id=cr_id, event_type=event_type, detail=detail or {})

    query = """
    CREATE (a:AuditEvent {
        id: $id,
        cr_id: $cr_id,
        event_type: $event_type,
        detail_json: $detail_json,
        created_at: $created_at
    })
    """
    g.query(
        query,
        params={
            "id": evt.id,
            "cr_id": evt.cr_id,
            "event_type": evt.event_type,
            "detail_json": json.dumps(evt.detail),
            "created_at": evt.created_at,
        },
    )
    return evt


def get_audit_events(cr_id: str) -> list[AuditEvent]:
    """Get all audit events for a change request."""
    g = get_meta_graph()
    res = g.query(
        "MATCH (a:AuditEvent {cr_id: $cr_id}) RETURN a ORDER BY a.created_at ASC",
        params={"cr_id": cr_id},
    )
    events = []
    for row in res.result_set:
        props = row[0].properties
        detail = json.loads(props.get("detail_json", "{}"))
        events.append(
            AuditEvent(
                id=props["id"],
                cr_id=props["cr_id"],
                event_type=props["event_type"],
                detail=detail,
                created_at=props["created_at"],
            )
        )
    return events


def record_agent_step(
    cr_id: str,
    idx: int,
    tool: str,
    args: dict[str, Any],
    result_summary: str,
) -> None:
    """Log an agent reasoning/tool execution step."""
    init_meta_indexes()
    g = get_meta_graph()
    query = """
    CREATE (s:AgentStep {
        id: $id,
        cr_id: $cr_id,
        idx: $idx,
        tool: $tool,
        args_json: $args_json,
        result_summary: $result_summary,
        created_at: $created_at
    })
    """
    from backend.app.models import utc_now_iso
    import uuid

    g.query(
        query,
        params={
            "id": f"step_{uuid.uuid4().hex[:8]}",
            "cr_id": cr_id,
            "idx": idx,
            "tool": tool,
            "args_json": json.dumps(args),
            "result_summary": result_summary,
            "created_at": utc_now_iso(),
        },
    )


def get_agent_steps(cr_id: str) -> list[dict[str, Any]]:
    """Get all agent steps for a change request in execution order."""
    g = get_meta_graph()
    res = g.query(
        "MATCH (s:AgentStep {cr_id: $cr_id}) RETURN s ORDER BY s.idx ASC",
        params={"cr_id": cr_id},
    )
    steps = []
    for row in res.result_set:
        props = row[0].properties
        steps.append({
            "id": props["id"],
            "cr_id": props["cr_id"],
            "idx": props["idx"],
            "tool": props["tool"],
            "args": json.loads(props.get("args_json", "{}")),
            "result_summary": props["result_summary"],
            "created_at": props["created_at"],
        })
    return steps


def reset_meta() -> None:
    """Wipe kb_meta."""
    client = get_falkordb()
    try:
        client.select_graph(META_GRAPH_NAME).delete()
    except Exception:
        pass

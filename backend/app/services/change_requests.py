"""
Change Request management service: creation, retrieval, and lifecycle hooks.
"""
from __future__ import annotations

from typing import Any
import uuid

from backend.app.db import get_falkordb, get_graph
from backend.app.models import (
    ChangeRequest,
    CRStatus,
    utc_now_iso,
)
from backend.app.services.branching import (
    create_branch,
    delete_branch,
    get_base_revision,
)
from backend.app.services.meta import (
    get_change_request,
    list_change_requests,
    record_audit_event,
    save_change_request,
)
from backend.app.services.operations import (
    apply_operations_to_graph,
    build_cr_operations,
)


def create_change_request(
    title: str,
    fact_key: str,
    new_value: Any,
    source_id: str | None = None,
    created_by: str = "user",
) -> ChangeRequest:
    """Create a new change request, fork a branch, build ops, and apply them to the branch."""
    main_graph = get_graph("kb_main")

    # 1. Capture base revision
    base_rev = get_base_revision(main_graph)

    # 2. Build operations (validates fact exists and is ACTIVE)
    ops = build_cr_operations(main_graph, fact_key, new_value, source_id)

    # 3. Create branch graph
    cr_id = f"cr_{uuid.uuid4().hex[:8]}"
    branch = create_branch(cr_id, base_graph_name="kb_main")

    # 4. Apply operations to the branch
    apply_operations_to_graph(branch, ops)

    # 5. Build and save ChangeRequest
    cr = ChangeRequest(
        id=cr_id,
        title=title,
        fact_key=fact_key,
        new_value=new_value,
        source_id=source_id,
        status=CRStatus.DRAFT,
        branch_graph=branch.name,
        base_revision=base_rev,
        ops=ops,
        created_by=created_by,
        created_at=utc_now_iso(),
    )
    save_change_request(cr)

    # 6. Audit event
    record_audit_event(
        cr_id,
        "CREATED",
        {
            "title": title,
            "fact_key": fact_key,
            "new_value": new_value,
            "source_id": source_id,
            "branch": branch.name,
            "base_revision": base_rev,
            "ops_count": len(ops),
        },
    )

    return cr

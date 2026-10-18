"""
Deterministic edit proposals service for TruthBranch.
Replaces price literals on documents with exact values and marks derived documents without literals as NEEDS_REVIEW.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from backend.app.db import get_falkordb, get_graph
from backend.app.models import Operation, OpType, ProposedEdit, utc_now_iso
from backend.app.schema import fact_id
from backend.app.services.baseline import literal_pattern
from backend.app.services.impact import impact_for_fact
from backend.app.services.meta import (
    get_change_request,
    record_audit_event,
    save_change_request,
)
from backend.app.services.operations import apply_operations_to_graph


_SINGULAR = {
    "days": "day",
    "hours": "hour",
    "weeks": "week",
    "months": "month",
    "years": "year",
    "minutes": "minute",
    "seats": "seat",
}
_UNIT_FMT = {
    "USD": "${v}",
    "kUSD": "${v}k",
    "MUSD": "${v}M",
    "percent": "{v}%",
    "days": "{v} days",
    "hours": "{v} hours",
    "minutes": "{v} minutes",
    "weeks": "{v} weeks",
    "months": "{v} months",
    "years": "{v} years",
    "chars": "{v} characters",
    "seats": "{v} seats",
    "people": "{v} people",
    "employees": "{v} employees",
    "offices": "{v} offices",
    "ms": "{v} ms",
    "per_min": "{v} requests per minute",
    "codes": "{v} backup codes",
    "year": "{v}",
}


def render_literal(unit: str, value: Any) -> str:
    """Render literal string from unit and value, respecting singular forms."""
    if not unit:
        return str(value)
    if value == 1 and unit in _SINGULAR:
        return f"1 {_SINGULAR[unit]}"
    if unit in _UNIT_FMT:
        return _UNIT_FMT[unit].format(v=value)
    return f"{value} {unit}"


def draft_content_replace(
    content: str,
    old_monthly: int | float | str = 49,
    new_monthly: int | float | str = 59,
    unit: str = "USD",
    extra_replacements: list[tuple[Any, Any, str]] | None = None,
) -> str:
    """Deterministically replace literal occurrences for primary and derived facts.

    Guarantees:
    - Formats from unit (e.g. 30 days -> 25 days, $49 -> $59)
    - Replaces annual derivations (e.g. $490 -> $590)
    - Leaves Enterprise / other numbers untouched
    """
    out = content
    # Primary replacement
    pat = literal_pattern(old_monthly, unit=unit)
    rep = render_literal(unit, new_monthly)
    out = pat.sub(rep, out)

    # Legacy default USD annual pricing derivation (x10)
    if unit in ("USD", "$") and not extra_replacements:
        try:
            old_num = float(old_monthly) if "." in str(old_monthly) else int(old_monthly)
            new_num = float(new_monthly) if "." in str(new_monthly) else int(new_monthly)
            pat_annual = literal_pattern(old_num * 10, unit="USD")
            rep_annual = f"${new_num * 10}"
            out = pat_annual.sub(rep_annual, out)
        except Exception:
            pass

    if extra_replacements:
        for old_v, new_v, u in extra_replacements:
            pat_extra = literal_pattern(old_v, unit=u)
            rep_extra = render_literal(u, new_v)
            out = pat_extra.sub(rep_extra, out)

    return out


def propose_edits_for_cr(cr_id: str) -> dict[str, Any]:
    """Generate proposed edits for all impacted documents on the branch."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    client = get_falkordb()
    branch = client.select_graph(cr.branch_graph)
    main = get_graph("kb_main")

    # Find base fact id
    old_fact_id = None
    for op in cr.ops:
        if op.key == cr.fact_key and op.old_fact_id:
            old_fact_id = op.old_fact_id
            break
    if not old_fact_id:
        old_fact_id = fact_id(cr.fact_key, cr.base_revision or 1)

    # 1. Compute impact set
    impacted = impact_for_fact(main, old_fact_id)
    now = utc_now_iso()

    created_edits: list[dict[str, Any]] = []
    marked_stale_docs: list[str] = []

    # Clean existing proposed edits on branch to be idempotent
    branch.query("MATCH (e:ProposedEdit) DETACH DELETE e")

    # Look up old fact value AND unit
    val_res = main.ro_query(
        "MATCH (f:Fact {id:$id}) RETURN f.value, f.unit",
        params={"id": old_fact_id},
    ).result_set
    if not val_res:
        val_res = main.ro_query(
            "MATCH (f:Fact) WHERE f.key = $key RETURN f.value, f.unit ORDER BY f.version DESC LIMIT 1",
            params={"key": cr.fact_key},
        ).result_set

    old_val = val_res[0][0] if (val_res and val_res[0] and val_res[0][0] is not None) else 49
    fact_unit = val_res[0][1] if (val_res and val_res[0] and len(val_res[0]) > 1 and val_res[0][1]) else "USD"
    if isinstance(old_val, str) and old_val.isdigit():
        old_val = int(old_val)
    new_val_num = int(cr.new_value) if str(cr.new_value).isdigit() else cr.new_value

    # Derived replacements
    derived_replacements: list[tuple[Any, Any, str]] = []
    for op in cr.ops:
        if op.op_type == OpType.UPDATE_FACT and op.key != cr.fact_key:
            d_res = main.ro_query(
                "MATCH (f:Fact) WHERE f.key = $key RETURN f.value, f.unit ORDER BY f.version DESC LIMIT 1",
                params={"key": op.key},
            ).result_set
            d_old = d_res[0][0] if d_res else None
            d_unit = d_res[0][1] if (d_res and len(d_res[0]) > 1) else fact_unit
            if d_old is not None:
                derived_replacements.append((d_old, op.new_value, d_unit))
            elif op.derived and op.derived.rule.startswith("x") and op.derived.rule[1:].isdigit():
                mult = int(op.derived.rule[1:])
                derived_replacements.append((old_val * mult, op.new_value, fact_unit))

    for item in impacted:
        doc_id = item["doc_id"]
        # Fetch current content from branch
        doc_res = branch.ro_query(
            "MATCH (d:Document {id:$doc_id}) RETURN d.content, d.title",
            params={"doc_id": doc_id},
        )
        if not doc_res.result_set:
            continue

        content, title = doc_res.result_set[0]
        content = content or ""

        # Check if content contains primary fact literal or any derived literal
        has_literal = bool(literal_pattern(old_val, unit=fact_unit).search(content))
        if not has_literal and derived_replacements:
            for d_old, _, d_u in derived_replacements:
                if literal_pattern(d_old, unit=d_u).search(content):
                    has_literal = True
                    break
        if not has_literal and fact_unit in ("USD", "$") and isinstance(old_val, (int, float)):
            has_literal = bool(literal_pattern(int(old_val * 10), unit="USD").search(content))

        if has_literal:
            new_content = draft_content_replace(
                content,
                old_monthly=old_val,
                new_monthly=new_val_num,
                unit=fact_unit,
                extra_replacements=derived_replacements,
            )
            edit_id = f"edit_{uuid.uuid4().hex[:8]}"

            branch.query(
                """
                MATCH (d:Document {id:$doc_id})
                CREATE (e:ProposedEdit {
                    id: $id,
                    doc_id: $doc_id,
                    before: $before,
                    after: $after,
                    status: 'PROPOSED',
                    author: 'TruthBranch Agent',
                    created_at: $now
                })
                CREATE (e)-[:EDITS]->(d)
                """,
                params={
                    "id": edit_id,
                    "doc_id": doc_id,
                    "before": content,
                    "after": new_content,
                    "now": now,
                },
            )
            created_edits.append({
                "edit_id": edit_id,
                "doc_id": doc_id,
                "doc_title": title,
                "before": content,
                "after": new_content,
            })
        else:
            # Multi-hop derived document without literal -> mark NEEDS_REVIEW
            branch.query(
                "MATCH (d:Document {id:$doc_id}) SET d.status = 'NEEDS_REVIEW'",
                params={"doc_id": doc_id},
            )
            marked_stale_docs.append(doc_id)

    # Record audit event
    record_audit_event(
        cr_id,
        "EDITS_DRAFTED",
        {
            "edits_count": len(created_edits),
            "marked_stale_count": len(marked_stale_docs),
            "edited_docs": [e["doc_id"] for e in created_edits],
            "marked_stale_docs": marked_stale_docs,
        },
    )

    return {
        "cr_id": cr_id,
        "edits": created_edits,
        "marked_stale": marked_stale_docs,
    }

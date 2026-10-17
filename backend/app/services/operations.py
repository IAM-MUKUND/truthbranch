"""
Operations generator and execution engine for TruthBranch.
Supports replayable, deterministic operations:
- UPDATE_FACT
- ATTACH_SOURCE
- MARK_STALE
- PROPOSE_EDIT
- REPOINT_CITATION
"""
from __future__ import annotations

from typing import Any
import uuid

from falkordb import Graph
from backend.app.models import (
    DerivedRule,
    Operation,
    OpType,
    utc_now_iso,
)
from backend.app.schema import fact_id


def build_cr_operations(
    base_graph: Graph,
    fact_key: str,
    new_value: Any,
    source_id: str | None = None,
) -> list[Operation]:
    """Generate the explicit list of operations needed for a proposed change."""
    # 1. Fetch current active fact
    res = base_graph.ro_query(
        "MATCH (f:Fact {key:$key, status:'ACTIVE'}) RETURN f.id, f.version, f.value, f.unit",
        params={"key": fact_key},
    )
    if not res.result_set:
        raise ValueError(f"No ACTIVE fact found with key '{fact_key}' on base graph.")

    curr_id, curr_version, curr_val, curr_unit = res.result_set[0]
    next_version = curr_version + 1
    new_fact_identifier = fact_id(fact_key, next_version)

    ops: list[Operation] = []

    # Op 1: Primary fact update
    op_update = Operation(
        op_id=uuid.uuid4().hex[:8],
        op_type=OpType.UPDATE_FACT,
        key=fact_key,
        expected_version=curr_version,
        new_value=new_value,
        unit=curr_unit,
        old_fact_id=curr_id,
        new_fact_id=new_fact_identifier,
    )
    ops.append(op_update)

    # Op 2: Attach source to primary fact
    if source_id:
        ops.append(
            Operation(
                op_id=uuid.uuid4().hex[:8],
                op_type=OpType.ATTACH_SOURCE,
                fact_id=new_fact_identifier,
                source_id=source_id,
            )
        )

    # Op 3: Check for downstream derived facts (e.g. annual derived from monthly with rule 'x10')
    derived_res = base_graph.ro_query(
        """
        MATCH (down:Fact)-[r:DERIVED_FROM]->(f:Fact {id:$id})
        WHERE down.status = 'ACTIVE'
        RETURN down.id, down.key, down.version, down.unit, r.rule
        """,
        params={"id": curr_id},
    )

    for row in derived_res.result_set:
        down_id, down_key, down_version, down_unit, rule = row
        # Compute derived value (e.g. rule 'x10' -> multiply by 10)
        if rule == "x10":
            derived_new_val = int(new_value) * 10
        else:
            derived_new_val = new_value

        down_next_ver = down_version + 1
        down_new_id = fact_id(down_key, down_next_ver)

        ops.append(
            Operation(
                op_id=uuid.uuid4().hex[:8],
                op_type=OpType.UPDATE_FACT,
                key=down_key,
                expected_version=down_version,
                new_value=derived_new_val,
                unit=down_unit,
                derived=DerivedRule(from_key=fact_key, rule=rule or "x10"),
                old_fact_id=down_id,
                new_fact_id=down_new_id,
            )
        )
        if source_id:
            ops.append(
                Operation(
                    op_id=uuid.uuid4().hex[:8],
                    op_type=OpType.ATTACH_SOURCE,
                    fact_id=down_new_id,
                    source_id=source_id,
                )
            )

    return ops


def apply_operations_to_graph(graph: Graph, ops: list[Operation]) -> None:
    """Apply a list of operations to a graph (either a candidate branch or kb_main)."""
    now = utc_now_iso()

    for op in ops:
        if op.op_type == OpType.UPDATE_FACT:
            # 1. Supersede old and create new
            q = """
            MATCH (old:Fact {key:$key, status:'ACTIVE'})
            WHERE old.version = $expected_version
            CREATE (new:Fact {
                id: $new_id,
                key: $key,
                version: $new_version,
                subject: old.subject,
                attribute: old.attribute,
                value: $new_value,
                unit: old.unit,
                status: 'ACTIVE',
                created_at: $now
            })
            CREATE (new)-[:SUPERSEDES]->(old)
            SET old.status = 'SUPERSEDED'
            RETURN new.id
            """
            res = graph.query(
                q,
                params={
                    "key": op.key,
                    "expected_version": op.expected_version,
                    "new_id": op.new_fact_id,
                    "new_version": (op.expected_version or 1) + 1,
                    "new_value": op.new_value,
                    "now": now,
                },
            )
            if not res.result_set:
                raise ValueError(
                    f"Conflict on UPDATE_FACT for {op.key}: expected version {op.expected_version} not ACTIVE."
                )

            # 2. Carry over owner from old fact
            graph.query(
                """
                MATCH (old:Fact {id:$old_id})-[:OWNED_BY]->(p:Person), (new:Fact {id:$new_id})
                MERGE (new)-[:OWNED_BY]->(p)
                """,
                params={"old_id": op.old_fact_id, "new_id": op.new_fact_id},
            )

            # 3. If derived, link to the new base fact
            if op.derived:
                base_key = op.derived.from_key
                graph.query(
                    """
                    MATCH (new_derived:Fact {id:$derived_id})
                    MATCH (new_base:Fact {key:$base_key, status:'ACTIVE'})
                    MERGE (new_derived)-[r:DERIVED_FROM]->(new_base)
                    SET r.rule = $rule
                    """,
                    params={
                        "derived_id": op.new_fact_id,
                        "base_key": base_key,
                        "rule": op.derived.rule,
                    },
                )

        elif op.op_type == OpType.ATTACH_SOURCE:
            graph.query(
                """
                MATCH (f:Fact {id:$fact_id}), (s:Source {id:$source_id})
                MERGE (f)-[:SOURCED_FROM]->(s)
                """,
                params={"fact_id": op.fact_id, "source_id": op.source_id},
            )

        elif op.op_type == OpType.MARK_STALE:
            graph.query(
                """
                MATCH (n {id:$node_id})
                SET n.status = 'NEEDS_REVIEW'
                """,
                params={"node_id": op.node_id},
            )

        elif op.op_type == OpType.PROPOSE_EDIT:
            edit_id = f"edit_{uuid.uuid4().hex[:8]}"
            graph.query(
                """
                MATCH (d:Document {id:$doc_id})
                CREATE (e:ProposedEdit {
                    id: $id,
                    doc_id: $doc_id,
                    before: $before,
                    after: $after,
                    status: 'PROPOSED',
                    created_at: $now
                })
                CREATE (e)-[:EDITS]->(d)
                """,
                params={
                    "id": edit_id,
                    "doc_id": op.doc_id,
                    "before": op.before,
                    "after": op.after,
                    "now": now,
                },
            )

        elif op.op_type == OpType.REPOINT_CITATION:
            graph.query(
                """
                MATCH (d:Document {id:$doc_id})-[c:CITES]->(old:Fact {id:$old_id})
                MATCH (new:Fact {id:$new_id})
                DELETE c
                WITH d, new
                MERGE (d)-[:CITES]->(new)
                """,
                params={
                    "doc_id": op.doc_id,
                    "old_id": op.old_fact_id,
                    "new_id": op.new_fact_id,
                },
            )

"""
Agent tools layer for TruthBranch.
Defines Pydantic argument schemas, tool schemas for Groq / OpenAI-compatible tool calling,
and tool executor functions backed by real FalkorDB services.

Hard security boundaries:
1. No tool writes to kb_main (modifications happen exclusively in kb_branch_{cr_id}).
2. submit_for_approval refuses if any BLOCK check fails; refusal message is returned to the agent.
3. No merge and no approve tools exist in this catalog.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict
from pydantic import BaseModel, Field

from backend.app.db import get_falkordb, get_graph
from backend.app.models import CheckSeverity, CRStatus
from backend.app.schema import fact_id
from backend.app.services.checks import analyze_change_request, run_quality_checks
from backend.app.services.edits import propose_edits_for_cr
from backend.app.services.impact import impact_for_fact
from backend.app.services.merge import submit_change_request
from backend.app.services.meta import (
    get_change_request,
    record_audit_event,
)


# ===========================================================================
# Pydantic Argument Models
# ===========================================================================

class GetLineageArgs(BaseModel):
    fact_id: str = Field(..., description="The fact identifier (e.g. 'fact:pricing.pro.monthly@v1' or 'fact:pricing.pro.monthly@v2').")


class GetImpactArgs(BaseModel):
    cr_id: str = Field(..., description="The Change Request identifier (e.g. 'cr_202610_001').")


class RunChecksArgs(BaseModel):
    cr_id: str = Field(..., description="The Change Request identifier.")


class ProposeEditsArgs(BaseModel):
    cr_id: str = Field(..., description="The Change Request identifier.")
    doc_ids: list[str] | None = Field(default=None, description="Optional specific document IDs to draft edits for. If omitted, drafts for all impacted documents.")


class RequestVerificationArgs(BaseModel):
    cr_id: str = Field(..., description="The Change Request identifier.")
    reason: str = Field(..., description="Why verification is required (e.g. unverified source, dark literal leak).")
    person_id: str = Field(..., description="The person ID to notify (e.g. 'p:maya', 'p:lena').")


class SubmitForApprovalArgs(BaseModel):
    cr_id: str = Field(..., description="The Change Request identifier.")


# ===========================================================================
# Tool Implementations
# ===========================================================================

def get_lineage(fact_id: str) -> dict[str, Any]:
    """Inspect the lineage, version history, source provenance, and upstream facts."""
    client = get_falkordb()
    # Check both kb_main and any active branch containing this fact
    main = client.select_graph("kb_main")

    # 1. Version history (supersedes chain)
    versions_res = main.ro_query(
        """
        MATCH (f:Fact {id:$fact_id})-[:SUPERSEDES*0..10]->(old:Fact)
        RETURN old.id, old.version, old.value, old.status
        ORDER BY old.version DESC
        """,
        params={"fact_id": fact_id},
    )
    versions = [
        {"id": r[0], "version": r[1], "value": r[2], "status": r[3]}
        for r in versions_res.result_set
    ]

    # 2. Attached sources
    sources_res = main.ro_query(
        """
        MATCH (f:Fact {id:$fact_id})-[:SOURCED_FROM]->(s:Source)
        RETURN s.id, s.title, s.valid, s.trust
        """,
        params={"fact_id": fact_id},
    )
    sources = [
        {"id": r[0], "title": r[1], "valid": r[2], "trust": r[3]}
        for r in sources_res.result_set
    ]

    # If not on main yet (e.g. brand new fact on branch), check active branches
    if not versions and not sources:
        for g_name in client.list_graphs():
            if g_name.startswith("kb_branch_"):
                bg = client.select_graph(g_name)
                s_res = bg.ro_query(
                    """
                    MATCH (f:Fact {id:$fact_id})-[:SOURCED_FROM]->(s:Source)
                    RETURN s.id, s.title, s.valid, s.trust
                    """,
                    params={"fact_id": fact_id},
                )
                if s_res.result_set:
                    sources = [
                        {"id": r[0], "title": r[1], "valid": r[2], "trust": r[3]}
                        for r in s_res.result_set
                    ]
                    break

    # 3. Upstream derived facts
    derived_res = main.ro_query(
        """
        MATCH (f:Fact {id:$fact_id})-[:DERIVED_FROM*1..3]->(u:Fact)
        RETURN DISTINCT u.id, u.value
        """,
        params={"fact_id": fact_id},
    )
    upstream = [{"id": r[0], "value": r[1]} for r in derived_res.result_set]

    return {
        "fact_id": fact_id,
        "versions": versions,
        "sources": sources,
        "upstream_facts": upstream,
    }


def get_impact(cr_id: str) -> dict[str, Any]:
    """Identify all documents and facts impacted by the Change Request."""
    cr = get_change_request(cr_id)
    if not cr:
        return {"error": f"Change Request '{cr_id}' not found."}

    client = get_falkordb()
    main = client.select_graph("kb_main")

    old_fact_id = None
    for op in cr.ops:
        if op.key == cr.fact_key and op.old_fact_id:
            old_fact_id = op.old_fact_id
            break
    if not old_fact_id:
        old_fact_id = fact_id(cr.fact_key, 1)

    impacted = impact_for_fact(main, old_fact_id)
    return {
        "cr_id": cr_id,
        "fact_key": cr.fact_key,
        "base_fact_id": old_fact_id,
        "total_impacted_documents": len(impacted),
        "documents": [
            {
                "doc_id": item["doc_id"],
                "title": item["title"],
                "reason": item["reason"],
                "path": item["path"],
                "owner_id": item["owner_id"],
                "owner_name": item["owner_name"],
                "system_name": item["system_name"],
            }
            for item in impacted
        ],
    }


def run_checks(cr_id: str) -> dict[str, Any]:
    """Run all deterministic quality checks on the Change Request branch."""
    cr = get_change_request(cr_id)
    if not cr:
        return {"error": f"Change Request '{cr_id}' not found."}

    analysis = analyze_change_request(cr_id)
    return {
        "cr_id": cr_id,
        "status": analysis["status"],
        "checks": analysis["checks"],
        "all_passed": all(c["passed"] for c in analysis["checks"]),
        "has_blocking_failures": any(
            not c["passed"] and c["severity"] == CheckSeverity.BLOCK.value
            for c in analysis["checks"]
        ),
    }


def propose_edits_for_affected_docs(cr_id: str, doc_ids: list[str] | None = None) -> dict[str, Any]:
    """Draft deterministic edits and review flags for impacted documents on the branch."""
    cr = get_change_request(cr_id)
    if not cr:
        return {"error": f"Change Request '{cr_id}' not found."}

    result = propose_edits_for_cr(cr_id)
    return {
        "cr_id": cr_id,
        "edits_count": len(result["edits"]),
        "marked_stale_count": len(result["marked_stale"]),
        "edits": [
            {"doc_id": e["doc_id"], "title": e["doc_title"], "status": "PROPOSED"}
            for e in result["edits"]
        ],
        "marked_stale_docs": result["marked_stale"],
    }


def request_verification(cr_id: str, reason: str, person_id: str) -> dict[str, Any]:
    """Request human stakeholder verification for unverified sources or dark literal leaks."""
    cr = get_change_request(cr_id)
    if not cr:
        return {"error": f"Change Request '{cr_id}' not found."}

    record_audit_event(
        cr_id,
        "VERIFICATION_REQUESTED",
        {"person_id": person_id, "reason": reason},
    )

    return {
        "cr_id": cr_id,
        "verified": False,
        "status": "VERIFICATION_REQUESTED",
        "person_id": person_id,
        "reason": reason,
        "message": f"Verification request sent to {person_id}: {reason}",
    }


def submit_for_approval(cr_id: str) -> dict[str, Any]:
    """Submit the Change Request for human approval. Refuses if any BLOCK check fails."""
    cr = get_change_request(cr_id)
    if not cr:
        return {"error": f"Change Request '{cr_id}' not found."}

    # Verify checks on the branch
    analysis = analyze_change_request(cr_id)
    blocking_failures = [
        c for c in analysis["checks"]
        if not c["passed"] and c["severity"] == CheckSeverity.BLOCK.value
    ]

    if blocking_failures:
        return {
            "refused": True,
            "error": "Cannot submit for approval: one or more blocking quality checks failed.",
            "blocking_failures": [
                {"code": c["code"], "message": c["message"], "evidence": c.get("evidence")}
                for c in blocking_failures
            ],
            "current_status": cr.status.value,
        }

    try:
        res = submit_change_request(cr_id)
        return {
            "refused": False,
            "success": True,
            "new_status": res["status"],
            "message": f"Change Request '{cr_id}' successfully submitted for review.",
        }
    except Exception as e:
        return {
            "refused": True,
            "error": str(e),
            "current_status": cr.status.value,
        }


# ===========================================================================
# Tool Catalog & Schemas
# ===========================================================================

TOOL_FUNCTIONS: Dict[str, Callable[..., Any]] = {
    "get_lineage": get_lineage,
    "get_impact": get_impact,
    "run_checks": run_checks,
    "propose_edits_for_affected_docs": propose_edits_for_affected_docs,
    "request_verification": request_verification,
    "submit_for_approval": submit_for_approval,
}

TOOL_ARG_MODELS: Dict[str, type[BaseModel]] = {
    "get_lineage": GetLineageArgs,
    "get_impact": GetImpactArgs,
    "run_checks": RunChecksArgs,
    "propose_edits_for_affected_docs": ProposeEditsArgs,
    "request_verification": RequestVerificationArgs,
    "submit_for_approval": SubmitForApprovalArgs,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_lineage",
            "description": "Inspect the lineage, version history, source provenance, validity, and trust scores for a fact. Call this first to verify if sources are valid and trusted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact_id": {
                        "type": "string",
                        "description": "The fact identifier (e.g. 'fact:pricing.pro.monthly@v1' or 'fact:pricing.pro.monthly@v2').",
                    }
                },
                "required": ["fact_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_impact",
            "description": "Identify all documents, systems, and downstream facts impacted by a Change Request, including transitively derived documents and shortest provenance paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_id": {
                        "type": "string",
                        "description": "The Change Request identifier (e.g. 'cr_202610_001').",
                    }
                },
                "required": ["cr_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_checks",
            "description": "Run the deterministic quality check suite on the candidate branch. Evaluates SOURCE_MISSING, SOURCE_INVALID, STALE_DEPENDENCY, CONTRADICTION, and LITERAL_VALUE_LEAK.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_id": {
                        "type": "string",
                        "description": "The Change Request identifier.",
                    }
                },
                "required": ["cr_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_edits_for_affected_docs",
            "description": "Draft deterministic content updates for impacted documents on the candidate branch and flag multi-hop derived documents without literals as NEEDS_REVIEW.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_id": {
                        "type": "string",
                        "description": "The Change Request identifier.",
                    },
                    "doc_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of document IDs to draft edits for. If omitted, drafts for all impacted documents.",
                    },
                },
                "required": ["cr_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_verification",
            "description": "Request human verification for suspicious, low-trust, or unverified sources, or alert owners about dark literal leaks in unlinked documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_id": {
                        "type": "string",
                        "description": "The Change Request identifier.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Explanation of why stakeholder verification is required.",
                    },
                    "person_id": {
                        "type": "string",
                        "description": "The identifier of the person/owner to notify (e.g. 'p:maya', 'p:lena').",
                    },
                },
                "required": ["cr_id", "reason", "person_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_for_approval",
            "description": "Submit the Change Request to READY_FOR_REVIEW once all blocking quality checks have passed. Will refuse and return failures if blocking checks fail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cr_id": {
                        "type": "string",
                        "description": "The Change Request identifier.",
                    }
                },
                "required": ["cr_id"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    """Validate arguments with Pydantic and execute the specified tool."""
    # Security check: never execute merge or approve
    if name in ("merge", "approve", "merge_change_request", "approve_change_request"):
        return {"error": f"Security violation: tool '{name}' is not permitted in agent catalog."}

    if name not in TOOL_FUNCTIONS:
        return {"error": f"Tool '{name}' not found."}

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception as e:
            return {"error": f"Invalid JSON arguments: {str(e)}"}

    model_cls = TOOL_ARG_MODELS.get(name)
    if model_cls:
        try:
            validated = model_cls(**arguments)
            arguments = validated.model_dump()
        except Exception as e:
            return {"error": f"Argument validation error: {str(e)}"}

    return TOOL_FUNCTIONS[name](**arguments)

"""
Deterministic scripted agent runner for TruthBranch.
Executes the exact same tools in sequence without calling an external LLM.
Used for offline benchmarks, deterministic integration tests, and demo fallback.
"""
from __future__ import annotations

import json
from typing import Any

from backend.app.agent.tools import execute_tool
from backend.app.models import CheckSeverity, CRStatus
from backend.app.schema import fact_id
from backend.app.services.meta import (
    get_change_request,
    record_agent_step,
    save_change_request,
)


def run_scripted_agent(cr_id: str) -> dict[str, Any]:
    """Execute the deterministic agent evaluation workflow for a Change Request."""
    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    steps: list[dict[str, Any]] = []
    step_idx = 0

    def log_and_exec(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        nonlocal step_idx
        result = execute_tool(tool_name, args)
        summary = (
            f"Executed {tool_name}: "
            + (
                f"{result.get('total_impacted_documents', '')} impacted docs"
                if "total_impacted_documents" in result
                else f"passed={result.get('all_passed', '')}"
                if "all_passed" in result
                else result.get("message")
                or f"{len(result.get('edits', []))} edits"
                if "edits" in result
                else "done"
            )
        )
        record_agent_step(cr_id, step_idx, tool_name, args, summary)
        steps.append({
            "idx": step_idx,
            "tool": tool_name,
            "args": args,
            "result": result,
            "summary": summary,
        })
        step_idx += 1
        return result

    # 1. Step 1: get_lineage
    target_fact_id = fact_id(cr.fact_key, 1)
    for op in cr.ops:
        if op.key == cr.fact_key and op.old_fact_id:
            target_fact_id = op.old_fact_id
            break

    lineage_res = log_and_exec("get_lineage", {"fact_id": target_fact_id})

    # Check for invalid or untrusted sources (Scenario B)
    sources = lineage_res.get("sources", [])
    has_untrusted_source = False
    bad_source_detail = ""

    # Check attached source from CR or lineage
    if cr.source_id:
        from backend.app.db import get_falkordb
        g = get_falkordb().select_graph(cr.branch_graph)
        s_res = g.ro_query("MATCH (s:Source {id:$id}) RETURN s.valid, s.trust, s.title", params={"id": cr.source_id}).result_set
        if s_res and s_res[0]:
            valid, trust, title = s_res[0]
            if not valid or trust < 0.6:
                has_untrusted_source = True
                bad_source_detail = f"Source '{title}' ({cr.source_id}) has valid={valid}, trust={trust}"

    for s in sources:
        if not s.get("valid", True) or s.get("trust", 1.0) < 0.6:
            has_untrusted_source = True
            bad_source_detail = f"Source '{s.get('title')}' ({s.get('id')}) has valid={s.get('valid')}, trust={s.get('trust')}"

    if has_untrusted_source:
        # Refusal & Verification flow
        verif_res = log_and_exec(
            "request_verification",
            {
                "cr_id": cr_id,
                "reason": f"Suspicious or unverified source detected: {bad_source_detail}. Human approval required.",
                "person_id": "p:maya",
            },
        )
        report = (
            f"### Agent Review Verdict: VERIFICATION_REQUESTED\n\n"
            f"**Reason:** The proposed change relies on an untrusted or invalid source.\n"
            f"- Detail: {bad_source_detail}\n"
            f"- Action Taken: Refused to draft edits or submit for approval. Notification dispatched to stakeholder `p:maya`.\n"
            f"- Human Decision Required: Verify the source memo or provide a valid corporate announcement."
        )
        return {
            "cr_id": cr_id,
            "verdict": "VERIFICATION_REQUESTED",
            "steps": steps,
            "report": report,
            "submitted": False,
        }

    # 2. Step 2: get_impact
    impact_res = log_and_exec("get_impact", {"cr_id": cr_id})

    # 3. Step 3: run_checks (initial check)
    checks_res = log_and_exec("run_checks", {"cr_id": cr_id})

    # 4. Step 4: propose_edits_for_affected_docs
    edits_res = log_and_exec("propose_edits_for_affected_docs", {"cr_id": cr_id})

    # 5. Step 5: re-run checks
    checks2_res = log_and_exec("run_checks", {"cr_id": cr_id})

    # 6. Check for literal leaks / warnings
    for chk in checks2_res.get("checks", []):
        if chk.get("code") == "LITERAL_VALUE_LEAK" and not chk.get("passed"):
            evidence = chk.get("evidence", [])
            log_and_exec(
                "request_verification",
                {
                    "cr_id": cr_id,
                    "reason": f"Unlinked document(s) {evidence} contain old literal value. Verify if dark dependency exists.",
                    "person_id": "p:lena",
                },
            )

    # 7. Step 6: submit_for_approval
    submit_res = log_and_exec("submit_for_approval", {"cr_id": cr_id})
    submitted = not submit_res.get("refused", True)

    # Reload CR to reflect final status
    cr_final = get_change_request(cr_id)
    verdict = cr_final.status.value if cr_final else "UNKNOWN"

    report = (
        f"### Agent Review Verdict: {verdict}\n\n"
        f"**Impact Summary:**\n"
        f"- Total Impacted Documents: {impact_res.get('total_impacted_documents', 0)}\n"
        f"- Proposed Edits Generated: {edits_res.get('edits_count', 0)}\n"
        f"- Derived Documents Flagged for Review: {edits_res.get('marked_stale_count', 0)}\n\n"
        f"**Quality Checks:**\n"
        + "\n".join([
            f"- {c.get('code')}: {'PASS' if c.get('passed') else 'WARN' if c.get('severity') == 'WARN' else 'FAIL'}"
            for c in checks2_res.get("checks", [])
        ])
        + f"\n\n**Submission:** {'Successfully submitted for human approval (READY_FOR_REVIEW)' if submitted else 'Refused submission due to failing checks'}.\n"
    )

    return {
        "cr_id": cr_id,
        "verdict": verdict,
        "steps": steps,
        "report": report,
        "submitted": submitted,
    }

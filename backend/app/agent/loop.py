"""
Groq Agent Loop for TruthBranch.
Uses `openai/gpt-oss-120b` for heavy reasoning and tool execution,
and `openai/gpt-oss-20b` for text polish and concise report generation.
Includes 8-step cap, 4KB truncation, Pydantic argument validation, and step logging.
Falls back to scripted mode if configured or on network/API failure.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from groq import Groq

from backend.app.agent.groq_pool import groq_pool
from backend.app.agent.prompts import SYSTEM_PROMPT, user_prompt_for_cr
from backend.app.agent.scripted import run_scripted_agent
from backend.app.agent.tools import TOOL_DEFINITIONS, execute_tool
from backend.app.config import get_settings
from backend.app.services.meta import (
    get_agent_steps,
    get_change_request,
    record_agent_step,
)

logger = logging.getLogger(__name__)

MAX_STEPS = 8
MAX_TOOL_OUTPUT_CHARS = 4000


def run_groq_agent_review(cr_id: str) -> dict[str, Any]:
    """Execute the autonomous LLM agent review loop for a Change Request."""
    settings = get_settings()

    # If scripted mode is enabled or no keys in pool, run the deterministic engine directly
    if settings.agent_mode == "scripted" or not groq_pool.has_keys:
        return run_scripted_agent(cr_id)

    cr = get_change_request(cr_id)
    if not cr:
        raise ValueError(f"Change Request '{cr_id}' not found.")

    try:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt_for_cr(cr.model_dump())},
        ]

        step_records: list[dict[str, Any]] = []
        step_idx = 0
        final_report = ""

        for step in range(MAX_STEPS):
            resp = groq_pool.chat_completion(
                model=settings.groq_heavy_model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0,
            )

            msg = resp.choices[0].message
            # Append assistant message to conversation history
            messages.append(msg)

            if not msg.tool_calls:
                final_report = msg.content or ""
                break

            for call in msg.tool_calls:
                tool_name = call.function.name
                raw_args = call.function.arguments

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                result = execute_tool(tool_name, args)

                # Generate brief step summary for logging
                summary = (
                    f"Tool: {tool_name} | "
                    + (
                        f"{result.get('total_impacted_documents', '')} impacted docs"
                        if "total_impacted_documents" in result
                        else f"passed={result.get('all_passed', '')}"
                        if "all_passed" in result
                        else result.get("message")
                        or f"{len(result.get('edits', []))} edits"
                        if "edits" in result
                        else "completed"
                    )
                )

                # Persist step in kb_meta
                record_agent_step(cr_id, step_idx, tool_name, args, summary)
                step_records.append({
                    "idx": step_idx,
                    "tool": tool_name,
                    "args": args,
                    "result": result,
                    "summary": summary,
                })
                step_idx += 1

                # Truncate output to prevent context blowup
                result_str = json.dumps(result)
                if len(result_str) > MAX_TOOL_OUTPUT_CHARS:
                    result_str = result_str[:MAX_TOOL_OUTPUT_CHARS] + "... [TRUNCATED]"

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result_str,
                })

        # If no report was generated after tool calls, ask for final evaluation
        if not final_report:
            resp_summary = groq_pool.chat_completion(
                model=settings.groq_light_model or settings.groq_heavy_model,
                messages=messages + [
                    {
                        "role": "user",
                        "content": "Based on the tool results above, provide your final review report in the specified format with verdict, impact summary, check status, and human decision points.",
                    }
                ],
                temperature=0,
            )
            final_report = resp_summary.choices[0].message.content or ""

        # Reload CR to reflect any status change made by submit_for_approval
        cr_updated = get_change_request(cr_id)
        verdict = cr_updated.status.value if cr_updated else "UNKNOWN"

        return {
            "cr_id": cr_id,
            "verdict": verdict,
            "steps": step_records,
            "report": final_report,
            "submitted": verdict == "READY_FOR_REVIEW",
        }

    except Exception as e:
        logger.warning(f"Groq agent failed with error ({e}); falling back to scripted agent.")
        return run_scripted_agent(cr_id)

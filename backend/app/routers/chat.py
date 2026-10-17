"""
Public Chat router for TruthBranch.
Powers the customer-facing AI assistant grounded in the authoritative kb_main graph.
"""
from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel
from groq import Groq

from backend.app.config import get_settings
from backend.app.db import get_falkordb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def get_ground_truth_context() -> tuple[str, list[dict], list[dict]]:
    """Retrieve all active facts and documents from the currently active graph."""
    from backend.app.db import get_graph
    main = get_graph("kb_main")

    # Facts
    f_res = main.ro_query(
        "MATCH (f:Fact {status:'ACTIVE'}) RETURN f.key, f.value, f.unit, f.subject, f.attribute, f.version"
    ).result_set
    facts = [
        {"key": r[0], "value": r[1], "unit": r[2], "subject": r[3], "attribute": r[4], "version": r[5]}
        for r in f_res
    ]

    # Documents
    d_res = main.ro_query(
        "MATCH (d:Document) RETURN d.id, d.title, d.content LIMIT 25"
    ).result_set
    docs = [
        {"id": r[0], "title": r[1], "content": r[2]}
        for r in d_res
    ]

    lines = ["=== ACTIVE FACTS (SINGLE SOURCE OF TRUTH) ==="]
    for f in facts:
        lines.append(f"- Fact '{f['key']}': {f['value']} {f['unit']} (version {f['version']})")

    lines.append("\n=== OFFICIAL COMPANY DOCUMENTS ===")
    for d in docs:
        lines.append(f"Document [{d['id']}] - Title: {d['title']}\nContent Snippet: {(d['content'] or '')[:300]}")

    return "\n".join(lines), facts, docs


def scripted_chat_response(user_text: str, facts: list[dict], docs: list[dict]) -> tuple[str, list[str]]:
    """Intelligent graph-backed fallback when LLM is unavailable."""
    text_lower = user_text.lower()
    citations = []

    # 1. Pricing questions
    if any(k in text_lower for k in ("price", "pricing", "cost", "how much", "plan", "pro", "tier")):
        pro_m = next((f for f in facts if f["key"] == "pricing.pro.monthly"), None)
        pro_a = next((f for f in facts if f["key"] == "pricing.pro.annual"), None)

        citations.append("doc:pricing_page")
        if pro_m:
            citations.append(f"fact:pricing.pro.monthly@v{pro_m['version']}")
            monthly_val = pro_m["value"]
            annual_val = pro_a["value"] if pro_a else monthly_val * 10
            return (
                f"Welcome! Our **Pro plan** is currently **${monthly_val}/month** (or **${annual_val}/year** with annual billing). "
                f"It comes packed with real-time analytics, unlimited events, automated reporting, and priority customer support!\n\n"
                f"We also offer an Enterprise tier for large scale data pipelines. Would you like me to help you get started?",
                citations,
            )

        # Fallback to any active fact
        if facts:
            fact_summary = ", ".join([f"{f['key']}: {f['value']} {f['unit']}" for f in facts[:3]])
            return (
                f"Here are our active plans and values from our company database: {fact_summary}. "
                f"How can I assist you with your requirements?",
                citations,
            )

    # 2. Refund policy
    if any(k in text_lower for k in ("refund", "money back", "cancel")):
        ref_doc = next((d for d in docs if "refund" in d["id"]), None)
        citations.append("doc:refund_policy")
        snippet = ref_doc["content"] if ref_doc else "We offer a 30-day money-back guarantee on all standard subscriptions."
        return (
            f"Here is our official refund policy: {snippet}\n\n"
            f"If you need any help with your account or billing, our support team is available 24/7.",
            citations,
        )

    # 3. Enterprise / support / features
    if any(k in text_lower for k in ("enterprise", "support", "feature", "sales", "analytics")):
        citations.append("doc:faq")
        return (
            "We provide enterprise-grade real-time web and product analytics! Features include custom event tracking, "
            "sub-second dashboard queries, GDPR compliance, and dedicated account managers for enterprise teams. "
            "What specific use case are you looking to solve?",
            citations,
        )

    # Default friendly greeting
    citations.append("doc:pricing_page")
    citations.append("doc:faq")
    return (
        "Hello! I am your AI assistant. I can answer questions about our product features, subscription pricing, "
        "refund policies, and platform capabilities—grounded directly in our live company knowledge base. "
        "What would you like to know today?",
        citations,
    )


@router.post("")
def chat(req: ChatRequest) -> dict[str, Any]:
    """Process customer chat grounded in kb_main."""
    if not req.messages:
        return {"role": "assistant", "content": "How can I help you today?", "citations": []}

    context_str, facts, docs = get_ground_truth_context()
    user_latest = req.messages[-1].content
    settings = get_settings()

    # Try live Groq LLM if configured
    if settings.groq_api_key and settings.agent_mode != "scripted":
        try:
            client = Groq(api_key=settings.groq_api_key)
            system_prompt = f"""You are the friendly, professional, and knowledgeable AI Ambassador for the company described in the official knowledge base below.
Your goal is to converse naturally with the user, promote the company's products, explain plans/features, and answer questions.

{context_str}

CRITICAL RULES:
1. Always base all factual statements (especially prices, plan names, and numbers) strictly on the ACTIVE FACTS listed above.
2. If pricing was recently updated (check version), confidently state the current active price.
3. Be enthusiastic, helpful, and concise.
4. Do not invent facts or prices not supported by the knowledge base.
"""
            model_to_use = settings.groq_light_model or "openai/gpt-oss-20b"
            resp = client.chat.completions.create(
                model=model_to_use,
                messages=[{"role": "system", "content": system_prompt}] + [m.model_dump() for m in req.messages],
                temperature=0.3,
            )
            content = resp.choices[0].message.content or ""

            # Detect relevant citations
            citations = []
            for d in docs:
                if d["title"].lower() in content.lower() or d["id"] in content:
                    citations.append(d["id"])
            if "pricing" in user_latest.lower() or "$" in content:
                citations.append("doc:pricing_page")

            return {
                "role": "assistant",
                "content": content,
                "citations": list(set(citations)),
            }
        except Exception as e:
            logger.warning(f"Groq chat completion failed ({e}); using graph-backed scripted response.")

    # Graph-backed fallback
    content, citations = scripted_chat_response(user_latest, facts, docs)
    return {
        "role": "assistant",
        "content": content,
        "citations": citations,
    }

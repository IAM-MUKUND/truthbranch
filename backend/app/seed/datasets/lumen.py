"""
Lumen Analytics dataset builder.
Extracted from data.py into modular catalog.
"""
from __future__ import annotations

import copy

SEED_TIME = "2025-01-15T00:00:00Z"
REVIEWED = "2026-09-01"

PEOPLE = [
    {"id": "p:maya",  "name": "Maya Rao",     "role": "Product owner",     "email": "maya@lumen.example"},
    {"id": "p:arjun", "name": "Arjun Mehta",  "role": "Finance owner",     "email": "arjun@lumen.example"},
    {"id": "p:sofia", "name": "Sofia Khan",   "role": "Support owner",     "email": "sofia@lumen.example"},
    {"id": "p:ravi",  "name": "Ravi Iyer",    "role": "Sales lead",        "email": "ravi@lumen.example"},
    {"id": "p:lena",  "name": "Lena Fischer", "role": "Partnerships lead", "email": "lena@lumen.example"},
]

SYSTEMS = [
    {"id": "sys:website_cms",    "name": "Website CMS"},
    {"id": "sys:helpdesk",       "name": "Helpdesk"},
    {"id": "sys:crm",            "name": "CRM"},
    {"id": "sys:finance_sheet",  "name": "Finance sheet"},
    {"id": "sys:partner_portal", "name": "Partner portal"},
]

SOURCES = [
    {"id": "src:pricing_announcement_2025",      "title": "Pricing announcement 2025",
     "kind": "announcement", "valid": True,  "trust": 0.95},
    {"id": "src:pricing_committee_memo_2026_10", "title": "Pricing committee memo, Oct 2026",
     "kind": "memo",         "valid": True,  "trust": 0.95},
    {"id": "src:slack_rumor_2026_10",            "title": "Unverified Slack message",
     "kind": "chat",         "valid": False, "trust": 0.2},
    {"id": "src:regional_page_2024",             "title": "Regional landing page (2024)",
     "kind": "web",          "valid": True,  "trust": 0.5},
]

_FACTS_BASE = [
    {"id": "fact:pricing.pro.monthly@v1", "key": "pricing.pro.monthly", "version": 1,
     "subject": "pro_plan", "attribute": "monthly_price", "value": 49, "unit": "USD",
     "status": "ACTIVE", "created_at": SEED_TIME},
    {"id": "fact:pricing.pro.annual@v1", "key": "pricing.pro.annual", "version": 1,
     "subject": "pro_plan", "attribute": "annual_price", "value": 490, "unit": "USD",
     "status": "ACTIVE", "created_at": SEED_TIME},
    {"id": "fact:support.refund_days@v1", "key": "support.refund_days", "version": 1,
     "subject": "support", "attribute": "refund_window_days", "value": 30, "unit": "days",
     "status": "ACTIVE", "created_at": SEED_TIME},
]

_FACTS_CONTRADICTION = [
    {"id": "fact:pricing.pro.monthly.eu@v1", "key": "pricing.pro.monthly.eu", "version": 1,
     "subject": "pro_plan", "attribute": "monthly_price", "value": 45, "unit": "USD",
     "status": "ACTIVE", "created_at": SEED_TIME},
]

_FACT_SOURCED = [
    {"fact": "fact:pricing.pro.monthly@v1", "source": "src:pricing_announcement_2025"},
    {"fact": "fact:pricing.pro.annual@v1",  "source": "src:pricing_announcement_2025"},
    {"fact": "fact:support.refund_days@v1", "source": "src:pricing_announcement_2025"},
]
_FACT_SOURCED_CONTRADICTION = [
    {"fact": "fact:pricing.pro.monthly.eu@v1", "source": "src:regional_page_2024"},
]

_FACT_OWNED = [
    {"fact": "fact:pricing.pro.monthly@v1", "person": "p:maya"},
    {"fact": "fact:pricing.pro.annual@v1",  "person": "p:maya"},
    {"fact": "fact:support.refund_days@v1", "person": "p:sofia"},
]
_FACT_OWNED_CONTRADICTION = [
    {"fact": "fact:pricing.pro.monthly.eu@v1", "person": "p:ravi"},
]

FACT_DERIVED = [
    {"fact": "fact:pricing.pro.annual@v1", "from_fact": "fact:pricing.pro.monthly@v1", "rule": "x10"},
]

DOCUMENTS = [
    {"id": "doc:pricing_page", "title": "Pricing page", "kind": "page", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "Lumen Pro costs $49 per month, or $490 per year (two months free). Cancel anytime."},
    {"id": "doc:sales_deck", "title": "Sales deck", "kind": "deck", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "Slide 7: Lumen Pro at $49/month. Enterprise starts at $149/month with SSO and audit logs."},
    {"id": "doc:faq", "title": "Customer FAQ", "kind": "faq", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "How much is Pro? $49 per month. Refunds are available within 30 days of purchase."},
    {"id": "doc:support_macro_upgrade", "title": "Support macro: upgrade question", "kind": "macro",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Thanks for asking about upgrading. Pro is billed at the monthly list price shown "
                "in our FAQ, and you can switch plans at any time."},
    {"id": "doc:revenue_forecast_q4", "title": "Q4 revenue forecast", "kind": "forecast",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Q4 forecast assumes 1,200 Pro seats at $49 per month."},
    {"id": "doc:investor_update", "title": "Investor update draft", "kind": "update",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Pro revenue in Q4 is tracking to plan based on the current forecast and list pricing."},
    {"id": "doc:board_deck", "title": "Board deck", "kind": "deck", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "Appendix B: revenue projections follow the Q4 forecast model."},
    {"id": "doc:partner_faq", "title": "Partner FAQ", "kind": "faq", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "Partners can resell Lumen Pro at the public price of $49 per month and keep a 20% margin."},
    {"id": "doc:refund_policy", "title": "Refund policy", "kind": "policy", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "Customers may request a full refund within 30 days of purchase."},
    {"id": "doc:onboarding_guide", "title": "Onboarding guide", "kind": "guide", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "Within your first 30 days you can request a refund from Settings. Welcome to Lumen!"},
    {"id": "doc:careers_page", "title": "Careers page", "kind": "page", "status": "CURRENT",
     "last_reviewed": REVIEWED,
     "content": "Join our team of 49 engineers building analytics for everyone."},
]

DOC_CITES = [
    {"doc": "doc:pricing_page",         "fact": "fact:pricing.pro.monthly@v1"},
    {"doc": "doc:pricing_page",         "fact": "fact:pricing.pro.annual@v1"},
    {"doc": "doc:sales_deck",           "fact": "fact:pricing.pro.monthly@v1"},
    {"doc": "doc:faq",                  "fact": "fact:pricing.pro.monthly@v1"},
    {"doc": "doc:faq",                  "fact": "fact:support.refund_days@v1"},
    {"doc": "doc:revenue_forecast_q4",  "fact": "fact:pricing.pro.monthly@v1"},
    {"doc": "doc:refund_policy",        "fact": "fact:support.refund_days@v1"},
    {"doc": "doc:onboarding_guide",     "fact": "fact:support.refund_days@v1"},
]

DOC_DERIVED = [
    {"doc": "doc:sales_deck",           "from_doc": "doc:pricing_page"},
    {"doc": "doc:support_macro_upgrade","from_doc": "doc:faq"},
    {"doc": "doc:investor_update",      "from_doc": "doc:revenue_forecast_q4"},
    {"doc": "doc:board_deck",           "from_doc": "doc:investor_update"},
]

DOC_PUBLISHED = [
    {"doc": "doc:pricing_page",          "system": "sys:website_cms"},
    {"doc": "doc:sales_deck",            "system": "sys:crm"},
    {"doc": "doc:faq",                   "system": "sys:website_cms"},
    {"doc": "doc:support_macro_upgrade", "system": "sys:helpdesk"},
    {"doc": "doc:revenue_forecast_q4",   "system": "sys:finance_sheet"},
    {"doc": "doc:investor_update",       "system": "sys:finance_sheet"},
    {"doc": "doc:board_deck",            "system": "sys:finance_sheet"},
    {"doc": "doc:partner_faq",           "system": "sys:partner_portal"},
    {"doc": "doc:refund_policy",         "system": "sys:website_cms"},
    {"doc": "doc:onboarding_guide",      "system": "sys:website_cms"},
    {"doc": "doc:careers_page",          "system": "sys:website_cms"},
]

DOC_OWNED = [
    {"doc": "doc:pricing_page",          "person": "p:maya"},
    {"doc": "doc:sales_deck",            "person": "p:ravi"},
    {"doc": "doc:faq",                   "person": "p:sofia"},
    {"doc": "doc:support_macro_upgrade", "person": "p:sofia"},
    {"doc": "doc:revenue_forecast_q4",   "person": "p:arjun"},
    {"doc": "doc:investor_update",       "person": "p:arjun"},
    {"doc": "doc:board_deck",            "person": "p:arjun"},
    {"doc": "doc:partner_faq",           "person": "p:lena"},
    {"doc": "doc:refund_policy",         "person": "p:sofia"},
    {"doc": "doc:onboarding_guide",      "person": "p:maya"},
    {"doc": "doc:careers_page",          "person": "p:maya"},
]

META = [{"id": "main", "revision": 1}]

SCENARIOS = {
    "A": {"title": "Raise Pro monthly price to $59",
          "fact_key": "pricing.pro.monthly", "new_value": 59,
          "source_id": "src:pricing_committee_memo_2026_10", "with_contradiction": False},
    "B": {"title": "Raise Pro monthly price to $59 (unverified source)",
          "fact_key": "pricing.pro.monthly", "new_value": 59,
          "source_id": "src:slack_rumor_2026_10", "with_contradiction": False},
    "C": {"title": "Raise Pro monthly price to $59 (regional conflict)",
          "fact_key": "pricing.pro.monthly", "new_value": 59,
          "source_id": "src:pricing_committee_memo_2026_10", "with_contradiction": True},
}


def build_dataset(with_contradiction: bool = False) -> dict:
    facts = list(_FACTS_BASE)
    fact_sourced = list(_FACT_SOURCED)
    fact_owned = list(_FACT_OWNED)
    if with_contradiction:
        facts += _FACTS_CONTRADICTION
        fact_sourced += _FACT_SOURCED_CONTRADICTION
        fact_owned += _FACT_OWNED_CONTRADICTION
    return copy.deepcopy({
        "people": PEOPLE, "systems": SYSTEMS, "sources": SOURCES, "facts": facts,
        "documents": DOCUMENTS, "meta": META,
        "fact_sourced": fact_sourced, "fact_owned": fact_owned, "fact_derived": FACT_DERIVED,
        "doc_cites": DOC_CITES, "doc_derived": DOC_DERIVED,
        "doc_published": DOC_PUBLISHED, "doc_owned": DOC_OWNED,
    })

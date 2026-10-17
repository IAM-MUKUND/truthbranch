"""
Demo dataset for TruthBranch: the fictional company "CloudGrid Infrastructure".
Domain: Enterprise Cloud GPU Cluster & Infrastructure Provider.
"""
from __future__ import annotations

import copy

SEED_TIME = "2026-01-10T00:00:00Z"
REVIEWED = "2026-10-01"

# --------------------------------------------------------------------------- people
PEOPLE = [
    {"id": "p:sarah",  "name": "Sarah Lin",     "role": "VP Infrastructure",     "email": "sarah@cloudgrid.io"},
    {"id": "p:dave",   "name": "Dave Ross",     "role": "Billing Architect",     "email": "dave@cloudgrid.io"},
    {"id": "p:elena",  "name": "Elena Rostova", "role": "Customer Support Lead", "email": "elena@cloudgrid.io"},
    {"id": "p:marcus", "name": "Marcus Vance",  "role": "Enterprise Sales Lead", "email": "marcus@cloudgrid.io"},
    {"id": "p:tariq",  "name": "Tariq Mansour", "role": "Site Reliability Lead", "email": "tariq@cloudgrid.io"},
]

# --------------------------------------------------------------------------- systems
SYSTEMS = [
    {"id": "sys:cloud_portal",   "name": "Cloud Portal CMS"},
    {"id": "sys:helpdesk",       "name": "Service Desk"},
    {"id": "sys:crm",            "name": "Enterprise CRM"},
    {"id": "sys:billing_engine", "name": "Billing Engine"},
    {"id": "sys:status_page",    "name": "Public Status Page"},
]

# --------------------------------------------------------------------------- sources
SOURCES = [
    {"id": "src:infra_board_resolution_2026", "title": "Board Resolution: 2026 GPU Rates",
     "kind": "resolution", "valid": True,  "trust": 0.98},
    {"id": "src:cloud_sla_charter_2026",      "title": "CloudGrid SLA Charter 2026",
     "kind": "charter",    "valid": True,  "trust": 0.95},
    {"id": "src:discord_rumor_2026",          "title": "Unverified Discord Community Leak",
     "kind": "chat",       "valid": False, "trust": 0.15},
    {"id": "src:spot_market_memo_2025",       "title": "Spot Market Internal Proposal",
     "kind": "memo",       "valid": True,  "trust": 0.45},
]

# --------------------------------------------------------------------------- facts
_FACTS_BASE = [
    {"id": "fact:compute.h100.hourly@v1", "key": "compute.h100.hourly", "version": 1,
     "subject": "h100_instance", "attribute": "hourly_rate", "value": 3.85, "unit": "USD/hr",
     "status": "ACTIVE", "created_at": SEED_TIME},
    {"id": "fact:compute.h100.monthly_reserved@v1", "key": "compute.h100.monthly_reserved", "version": 1,
     "subject": "h100_instance", "attribute": "monthly_reserved_rate", "value": 2490, "unit": "USD/mo",
     "status": "ACTIVE", "created_at": SEED_TIME},
    {"id": "fact:sla.uptime_guarantee@v1", "key": "sla.uptime_guarantee", "version": 1,
     "subject": "service_level", "attribute": "monthly_uptime_percent", "value": 99.99, "unit": "%",
     "status": "ACTIVE", "created_at": SEED_TIME},
]

# Scenario C contradiction fact: conflicting spot market rate for the same subject/attribute
_FACTS_CONTRADICTION = [
    {"id": "fact:compute.h100.hourly.spot@v1", "key": "compute.h100.hourly.spot", "version": 1,
     "subject": "h100_instance", "attribute": "hourly_rate", "value": 2.95, "unit": "USD/hr",
     "status": "ACTIVE", "created_at": SEED_TIME},
]

_FACT_SOURCED = [
    {"fact": "fact:compute.h100.hourly@v1",           "source": "src:infra_board_resolution_2026"},
    {"fact": "fact:compute.h100.monthly_reserved@v1", "source": "src:infra_board_resolution_2026"},
    {"fact": "fact:sla.uptime_guarantee@v1",          "source": "src:cloud_sla_charter_2026"},
]
_FACT_SOURCED_CONTRADICTION = [
    {"fact": "fact:compute.h100.hourly.spot@v1", "source": "src:spot_market_memo_2025"},
]

_FACT_OWNED = [
    {"fact": "fact:compute.h100.hourly@v1",           "person": "p:dave"},
    {"fact": "fact:compute.h100.monthly_reserved@v1", "person": "p:dave"},
    {"fact": "fact:sla.uptime_guarantee@v1",          "person": "p:sarah"},
]
_FACT_OWNED_CONTRADICTION = [
    {"fact": "fact:compute.h100.hourly.spot@v1", "person": "p:marcus"},
]

FACT_DERIVED = [
    {"fact": "fact:compute.h100.monthly_reserved@v1", "from_fact": "fact:compute.h100.hourly@v1", "rule": "x647"},
]

# --------------------------------------------------------------------------- documents
DOCUMENTS = [
    {"id": "doc:gpu_pricing_sheet", "title": "Compute Pricing & Quotas", "kind": "page",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "CloudGrid dedicated NVIDIA H100 SXM5 instances are billed at $3.85 per hour, "
                "or $2490 per month on annual reservation. High-speed interconnect included."},
    {"id": "doc:enterprise_sales_deck", "title": "Enterprise Infrastructure Deck", "kind": "deck",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Slide 5: Dedicated AI Clusters. H100 instances start at $3.85/hr with 99.99% SLA guarantee."},
    {"id": "doc:cloud_faq", "title": "Cluster Operations FAQ", "kind": "faq",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "How much does an H100 instance cost? $3.85 per hour. We guarantee 99.99% monthly availability."},
    {"id": "doc:support_macro_quota", "title": "Support Macro: Cluster Sizing", "kind": "macro",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Thanks for your inquiry about multi-node H100 reservations. Pricing is fixed at the standard rate "
                "listed in our Operations FAQ, billed per active hour."},
    {"id": "doc:revenue_model_q4", "title": "Q4 Cloud Capacity Forecast", "kind": "forecast",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Model projects 50,000 active H100 compute hours at $3.85 per hour across tier-3 data centers."},
    {"id": "doc:investor_report", "title": "Quarterly Infrastructure Report", "kind": "update",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "GPU utilization targets are tracking in line with our Q4 capacity model and compute pricing."},
    {"id": "doc:board_infra_pack", "title": "Board Infrastructure Pack", "kind": "deck",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Executive Summary: Infrastructure expansion aligns with the Q4 capacity model."},
    {"id": "doc:partner_reseller_guide", "title": "Reseller Partner Guide", "kind": "guide",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "Authorized partners may resell CloudGrid H100 clusters at the public rate of $3.85 per hour."},
    {"id": "doc:enterprise_sla_policy", "title": "Enterprise SLA & Service Credits", "kind": "policy",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "CloudGrid guarantees 99.99% monthly cluster availability. In the event of an outage, service credits apply."},
    {"id": "doc:status_page_announcement", "title": "Network Reliability Standard", "kind": "page",
     "status": "CURRENT", "last_reviewed": REVIEWED,
     "content": "All multi-tenant nodes operate under our strict 99.99% uptime commitment."},
]

DOC_CITES = [
    {"doc": "doc:gpu_pricing_sheet",         "fact": "fact:compute.h100.hourly@v1"},
    {"doc": "doc:gpu_pricing_sheet",         "fact": "fact:compute.h100.monthly_reserved@v1"},
    {"doc": "doc:enterprise_sales_deck",     "fact": "fact:compute.h100.hourly@v1"},
    {"doc": "doc:enterprise_sales_deck",     "fact": "fact:sla.uptime_guarantee@v1"},
    {"doc": "doc:cloud_faq",                 "fact": "fact:compute.h100.hourly@v1"},
    {"doc": "doc:cloud_faq",                 "fact": "fact:sla.uptime_guarantee@v1"},
    {"doc": "doc:revenue_model_q4",          "fact": "fact:compute.h100.hourly@v1"},
    {"doc": "doc:enterprise_sla_policy",     "fact": "fact:sla.uptime_guarantee@v1"},
    {"doc": "doc:status_page_announcement",  "fact": "fact:sla.uptime_guarantee@v1"},
]

DOC_DERIVED = [
    {"doc": "doc:enterprise_sales_deck",     "from_doc": "doc:gpu_pricing_sheet"},
    {"doc": "doc:support_macro_quota",       "from_doc": "doc:cloud_faq"},
    {"doc": "doc:investor_report",           "from_doc": "doc:revenue_model_q4"},
    {"doc": "doc:board_infra_pack",          "from_doc": "doc:investor_report"},
]

DOC_PUBLISHED = [
    {"doc": "doc:gpu_pricing_sheet",         "system": "sys:cloud_portal"},
    {"doc": "doc:enterprise_sales_deck",     "system": "sys:crm"},
    {"doc": "doc:cloud_faq",                 "system": "sys:cloud_portal"},
    {"doc": "doc:support_macro_quota",       "system": "sys:helpdesk"},
    {"doc": "doc:revenue_model_q4",          "system": "sys:billing_engine"},
    {"doc": "doc:investor_report",           "system": "sys:billing_engine"},
    {"doc": "doc:board_infra_pack",          "system": "sys:billing_engine"},
    {"doc": "doc:partner_reseller_guide",    "system": "sys:cloud_portal"},
    {"doc": "doc:enterprise_sla_policy",     "system": "sys:cloud_portal"},
    {"doc": "doc:status_page_announcement",  "system": "sys:status_page"},
]

DOC_OWNED = [
    {"doc": "doc:gpu_pricing_sheet",         "person": "p:dave"},
    {"doc": "doc:enterprise_sales_deck",     "person": "p:marcus"},
    {"doc": "doc:cloud_faq",                 "person": "p:elena"},
    {"doc": "doc:support_macro_quota",       "person": "p:elena"},
    {"doc": "doc:revenue_model_q4",          "person": "p:dave"},
    {"doc": "doc:investor_report",           "person": "p:dave"},
    {"doc": "doc:board_infra_pack",          "person": "p:dave"},
    {"doc": "doc:partner_reseller_guide",    "person": "p:marcus"},
    {"doc": "doc:enterprise_sla_policy",     "person": "p:sarah"},
    {"doc": "doc:status_page_announcement",  "person": "p:tariq"},
]

META = [{"id": "main", "revision": 1}]

SCENARIOS = {
    "A": {"title": "Raise H100 hourly rate to $4.25",
          "fact_key": "compute.h100.hourly", "new_value": 4.25,
          "source_id": "src:infra_board_resolution_2026", "with_contradiction": False},
    "B": {"title": "Raise H100 hourly rate to $4.25 (unverified Discord leak)",
          "fact_key": "compute.h100.hourly", "new_value": 4.25,
          "source_id": "src:discord_rumor_2026", "with_contradiction": False},
    "C": {"title": "Raise H100 hourly rate to $4.25 (spot market conflict)",
          "fact_key": "compute.h100.hourly", "new_value": 4.25,
          "source_id": "src:infra_board_resolution_2026", "with_contradiction": True},
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

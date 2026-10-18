"""
Meridian Systems: a large, deterministic "company brain" dataset for TruthBranch.

~100 facts and ~350 documents across pricing, support/SLA, HR policy, compensation,
finance, security, privacy/legal, named clients, engineering/IT, sales/partners and
company facts. Built by a deterministic generator (fixed seed, no network, no LLM).

Design rules (all enforced by tests/test_meridian_dataset.py):
  * Document text is RENDERED from fact values ({{fact.key}} placeholders), so content
    and CITES edges can never drift apart.
  * Every fact's rendered literal ("$79", "24 days", "99.9%") is unique across facts.
  * A literal appears only in documents that cite the fact, plus annotated DARK
    dependencies (literal present, no CITES edge).
  * Fact derivation depth <= 3, document derivation depth <= 3, no cycles.
  * A document that cites ONLY a derived fact never has derived-document children
    (keeps the *1..3 impact queries complete).
"""
from __future__ import annotations

import copy
import random
import re

SEED_TIME = "2025-01-15T00:00:00Z"
_REVIEW_DATES = ["2026-03-01", "2026-05-15", "2026-07-01", "2026-08-20", "2026-09-10"]

# ------------------------------------------------------------------ literal rendering
_SINGULAR = {"days": "day", "hours": "hour", "weeks": "week", "months": "month",
             "years": "year", "minutes": "minute", "seats": "seat"}
_UNIT_FMT = {
    "USD": "${v}", "kUSD": "${v}k", "MUSD": "${v}M", "percent": "{v}%",
    "days": "{v} days", "hours": "{v} hours", "minutes": "{v} minutes",
    "weeks": "{v} weeks", "months": "{v} months", "years": "{v} years",
    "chars": "{v} characters", "seats": "{v} seats", "people": "{v} people",
    "employees": "{v} employees", "offices": "{v} offices", "ms": "{v} ms",
    "per_min": "{v} requests per minute", "codes": "{v} backup codes", "year": "{v}",
}


def render_literal(unit: str, value) -> str:
    """The exact string a document prints for a fact. Used by the generator AND by tests."""
    if value == 1 and unit in _SINGULAR:
        return f"1 {_SINGULAR[unit]}"
    return _UNIT_FMT[unit].format(v=value)


# ------------------------------------------------------------------ people / systems
_P = lambda i, n, r: {"id": f"p:{i}", "name": n, "role": r, "email": f"{i}@meridian.example"}
PEOPLE = [
    _P("anika", "Anika Sharma", "Head of People"), _P("daniel", "Daniel Okafor", "HR Business Partner"),
    _P("meera", "Meera Nair", "Payroll & Benefits Lead"), _P("tara", "Tara Lindqvist", "Recruiting Lead"),
    _P("chloe", "Chloe Martin", "Learning & Development Lead"),
    _P("rohan", "Rohan Verma", "Head of Finance"), _P("rhea", "Rhea Kapoor", "Finance Controller"),
    _P("elena", "Elena Petrova", "Procurement Manager"),
    _P("tomas", "Tomas Weber", "Head of Security"), _P("grace", "Grace Liu", "Compliance Officer"),
    _P("ivan", "Ivan Novak", "Data Protection Officer"),
    _P("victor", "Victor Alvarez", "General Counsel"), _P("oscar", "Oscar Bennett", "Commercial Counsel"),
    _P("neha", "Neha Gupta", "Head of Product"), _P("samir", "Samir Qureshi", "Pricing Manager"),
    _P("lucy", "Lucy Evans", "Head of Support"), _P("omar", "Omar Haddad", "Support Operations Lead"),
    _P("diego", "Diego Fernandes", "Head of Sales"), _P("hana", "Hana Sato", "Partnerships Manager"),
    _P("noor", "Noor Rahman", "Revenue Operations Lead"),
    _P("kavya", "Kavya Menon", "Customer Success Director"),
    _P("ben", "Ben Carter", "Enterprise Account Manager"), _P("ines", "Ines Duarte", "Banking Account Manager"),
    _P("arun", "Arun Pillai", "VP Engineering"), _P("sara", "Sara Johansson", "SRE Lead"),
    _P("lars", "Lars Eriksen", "IT Operations Manager"), _P("felix", "Felix Wagner", "Developer Relations Lead"),
    _P("mia", "Mia Thompson", "Head of Marketing"), _P("yusuf", "Yusuf Demir", "Facilities Manager"),
    _P("jamal", "Jamal Brooks", "Internal Communications Lead"),
]

SYSTEMS = [
    {"id": "sys:handbook_wiki", "name": "Handbook wiki"}, {"id": "sys:hris", "name": "HRIS"},
    {"id": "sys:website_cms", "name": "Website CMS"}, {"id": "sys:helpdesk", "name": "Helpdesk"},
    {"id": "sys:crm", "name": "CRM"}, {"id": "sys:finance_sheet", "name": "Finance sheet"},
    {"id": "sys:contract_repo", "name": "Contract repository"}, {"id": "sys:trust_center", "name": "Trust center"},
    {"id": "sys:eng_wiki", "name": "Engineering wiki"}, {"id": "sys:partner_portal", "name": "Partner portal"},
    {"id": "sys:intranet", "name": "Intranet"}, {"id": "sys:slack_bot", "name": "Slack assistant"},
]

# ------------------------------------------------------------------ sources
_S = lambda i, t, k, v, tr: {"id": f"src:{i}", "title": t, "kind": k, "valid": v, "trust": tr}
SOURCES = [
    _S("pricing_announcement_2025", "Pricing announcement 2025", "announcement", True, 0.95),
    _S("pricing_committee_memo_2026_10", "Pricing committee memo, Oct 2026", "memo", True, 0.95),
    _S("hr_policy_handbook_2026", "HR policy handbook 2026", "policy", True, 0.95),
    _S("board_resolution_2026_09", "Board resolution, Sep 2026", "board", True, 0.98),
    _S("security_policy_v7", "Information security policy v7", "policy", True, 0.95),
    _S("soc2_report_2026", "SOC 2 Type II report 2026", "audit", True, 0.97),
    _S("legal_counsel_memo_2026_10", "General Counsel memo, Oct 2026", "memo", True, 0.93),
    _S("sla_schedule_2026", "SLA schedule 2026", "contract", True, 0.95),
    _S("finance_policy_2026", "Finance policy 2026", "policy", True, 0.92),
    _S("works_council_agreement_2025", "Works council agreement 2025", "agreement", True, 0.90),
    _S("engineering_standards_2026", "Engineering standards 2026", "policy", True, 0.90),
    _S("sales_comp_plan_2026", "Sales compensation plan 2026", "policy", True, 0.92),
    _S("company_all_hands_2026_10", "All-hands announcement, Oct 2026", "announcement", True, 0.85),
    _S("slack_rumor_2026_10", "Unverified Slack message", "chat", False, 0.2),
    _S("outdated_wiki_2022", "Outdated wiki page (2022)", "wiki", False, 0.35),
    _S("forwarded_email_unverified", "Forwarded email, sender unverified", "email", False, 0.25),
    _S("regional_page_2024", "Regional landing page (2024)", "web", True, 0.5),
    _S("northwind_amendment_2026_10", "Northwind contract amendment, Oct 2026", "contract", True, 0.96),
]

# ------------------------------------------------------------------ clients
# (slug, name, account owner, discount %, payment days, committed seats)
CLIENTS = [
    ("acme", "Acme Logistics", "p:ben", 12, 50, 450),
    ("northwind", "Northwind Bank", "p:ines", 15, 38, 1200),
    ("helios", "Helios Energy", "p:ben", 11, 55, 300),
    ("globex", "Globex Retail", "p:ben", 18, 65, 850),
    ("initech", "Initech Health", "p:ines", 6, 42, 150),
    ("umbra", "Umbra Telecom", "p:kavya", 22, 33, 600),
]
for _slug, _n, *_ in CLIENTS:
    SOURCES.append(_S(f"contract_{_slug}", f"{_n} master agreement", "contract", True, 0.96))

# ------------------------------------------------------------------ facts
# (key, value, unit, owner, source, sentence with {L})        value None => derived (see DERIVED)
_PA, _PM = "src:pricing_announcement_2025", "src:pricing_committee_memo_2026_10"
_HR, _SEC, _FIN = "src:hr_policy_handbook_2026", "src:security_policy_v7", "src:finance_policy_2026"
_LEG, _SLA, _ENG = "src:legal_counsel_memo_2026_10", "src:sla_schedule_2026", "src:engineering_standards_2026"
_SAL, _CO, _BRD = "src:sales_comp_plan_2026", "src:company_all_hands_2026_10", "src:board_resolution_2026_09"
FACTS_SPEC = [
    # pricing
    ("pricing.team.monthly", 39, "USD", "p:samir", _PA, "The Team plan costs {L} per seat per month."),
    ("pricing.team.annual", None, "USD", "p:samir", _PA, "The Team plan costs {L} per seat per year when billed annually."),
    ("pricing.business.monthly", 79, "USD", "p:samir", _PA, "The Business plan costs {L} per seat per month."),
    ("pricing.business.annual", None, "USD", "p:samir", _PA, "The Business plan costs {L} per seat per year when billed annually."),
    ("pricing.enterprise.monthly", 149, "USD", "p:samir", _PA, "Enterprise plans start at {L} per seat per month."),
    ("pricing.trial.days", 14, "days", "p:samir", _PA, "Every plan includes a free trial of {L}."),
    ("pricing.startup_discount.percent", 20, "percent", "p:diego", _PA, "Eligible startups receive {L} off the first year."),
    ("pricing.nonprofit_discount.percent", 30, "percent", "p:diego", _PA, "Registered nonprofits receive {L} off all plans."),
    ("pricing.seats.minimum", 5, "seats", "p:samir", _PA, "Paid plans require a minimum of {L}."),
    ("pricing.api.rate_limit", 600, "per_min", "p:felix", _ENG, "The public API allows {L} per workspace."),
    # support and SLA
    ("support.refund.days", 30, "days", "p:lucy", _PA, "Customers can request a full refund within {L} of purchase."),
    ("support.p1.response_hours", 1, "hours", "p:lucy", _SLA, "Priority 1 tickets receive a first response within {L}."),
    ("support.p2.response_hours", 4, "hours", "p:lucy", _SLA, "Priority 2 tickets receive a first response within {L}."),
    ("support.chat.first_reply_minutes", 5, "minutes", "p:omar", _SLA, "Live chat targets a first reply within {L}."),
    ("support.csat.target_percent", 92, "percent", "p:lucy", _SLA, "The support team targets a satisfaction score of {L}."),
    ("support.escalation.minutes", 45, "minutes", "p:omar", _SLA, "Unanswered urgent tickets are escalated after {L}."),
    ("sla.uptime.percent", 99.9, "percent", "p:sara", _SLA, "Meridian commits to monthly platform uptime of {L}."),
    ("sla.credit.percent", 10, "percent", "p:oscar", _SLA, "Missed uptime earns a service credit of {L} of monthly fees."),
    # HR policy
    ("hr.pto.annual_days", 24, "days", "p:anika", _HR, "Full-time employees receive {L} of paid time off each year."),
    ("hr.pto.max_balance_days", None, "days", "p:anika", _HR, "Unused paid time off is capped at {L}."),
    ("hr.sick.days", 12, "days", "p:anika", _HR, "Employees may take up to {L} of paid sick leave each year."),
    ("hr.parental.primary_weeks", 20, "weeks", "p:anika", _HR, "Primary caregivers receive {L} of paid parental leave."),
    ("hr.parental.secondary_weeks", 8, "weeks", "p:anika", _HR, "Secondary caregivers receive {L} of paid parental leave."),
    ("hr.remote.days_per_week", 3, "days", "p:daniel", _HR, "Employees may work remotely up to {L} per week."),
    ("hr.probation.months", 6, "months", "p:daniel", _HR, "New hires serve a probation period of {L}."),
    ("hr.notice.days", 60, "days", "p:daniel", _HR, "Either party must give a notice period of {L}."),
    ("hr.work.hours_per_week", 40, "hours", "p:anika", _HR, "The standard working week is {L}."),
    ("hr.holidays.company_days", 11, "days", "p:meera", _HR, "Meridian observes {L} of company holidays."),
    ("hr.referral.bonus_usd", 500, "USD", "p:tara", _HR, "Employees earn a referral bonus of {L} for each successful hire."),
    ("hr.learning.budget_usd", 800, "USD", "p:chloe", _HR, "Each employee has a learning budget of {L} per year."),
    ("hr.wellness.stipend_usd", 40, "USD", "p:meera", _HR, "Employees receive a wellness stipend of {L} per month."),
    ("hr.onboarding.buddy_weeks", 4, "weeks", "p:chloe", _HR, "New hires are paired with a buddy for {L}."),
    ("hr.sabbatical.years", 5, "years", "p:anika", _HR, "Employees with {L} of service may apply for a paid sabbatical."),
    # compensation
    ("comp.band.l3.min", 95, "kUSD", "p:meera", _BRD, "The L3 salary band starts at {L}."),
    ("comp.band.l3.max", 125, "kUSD", "p:meera", _BRD, "The L3 salary band tops out at {L}."),
    ("comp.band.l4.min", 120, "kUSD", "p:meera", _BRD, "The L4 salary band starts at {L}."),
    ("comp.equity.vesting_years", 4, "years", "p:meera", _BRD, "Equity grants vest over {L}."),
    ("comp.equity.cliff_months", 12, "months", "p:meera", _BRD, "Equity grants have a vesting cliff of {L}."),
    # finance
    ("finance.expense.approval_limit", 250, "USD", "p:rhea", _FIN, "Expenses above {L} need manager approval."),
    ("finance.expense.receipt_threshold", 25, "USD", "p:rhea", _FIN, "Receipts are required for expenses above {L}."),
    ("finance.expense.submission_days", 15, "days", "p:rhea", _FIN, "Expense claims must be submitted within {L}."),
    ("finance.travel.hotel_cap", 180, "USD", "p:rhea", _FIN, "Hotel stays are capped at {L} per night."),
    ("finance.travel.meal_per_diem", 45, "USD", "p:rhea", _FIN, "The travel meal allowance is {L} per day."),
    ("finance.po.threshold", 900, "USD", "p:elena", _FIN, "Purchases above {L} require a purchase order."),
    ("finance.vendor.payment_days", 45, "days", "p:elena", _FIN, "Approved vendors are paid within {L}."),
    ("finance.card.monthly_limit", 700, "USD", "p:rhea", _FIN, "The corporate card has a monthly limit of {L}."),
    ("finance.invoice.payment_terms_days", 21, "days", "p:rohan", _FIN, "Standard customer invoices are due within {L}."),
    # security
    ("security.password.min_length", 14, "chars", "p:tomas", _SEC, "Passwords must be at least {L} long."),
    ("security.session.timeout_hours", 12, "hours", "p:tomas", _SEC, "Authenticated sessions expire after {L}."),
    ("security.access_review.months", 3, "months", "p:grace", _SEC, "Privileged access is reviewed every {L}."),
    ("security.log.retention_days", 365, "days", "p:tomas", _SEC, "Security logs are retained for {L}."),
    ("security.pentest.interval_months", 9, "months", "p:tomas", "src:soc2_report_2026", "Independent penetration tests run every {L}."),
    ("security.incident.notify_hours", 72, "hours", "p:grace", _SEC, "Affected customers are notified of a breach within {L}."),
    ("security.training.hours", 3, "hours", "p:grace", _SEC, "Annual security awareness training takes {L}."),
    ("security.vendor.review_months", 18, "months", "p:grace", _SEC, "Critical vendors are reassessed every {L}."),
    ("security.mfa.backup_codes", 10, "codes", "p:tomas", _SEC, "Each user receives {L}."),
    ("security.patch.critical_days", 7, "days", "p:tomas", _SEC, "Critical vulnerabilities are patched within {L}."),
    # privacy and legal
    ("privacy.dsar.response_days", 28, "days", "p:ivan", _LEG, "Data subject requests are answered within {L}."),
    ("privacy.data.retention_months", 24, "months", "p:ivan", _LEG, "Customer data is deleted {L} after contract termination."),
    ("legal.signature.limit_kusd", 50, "kUSD", "p:victor", _LEG, "Contracts above {L} need CFO sign-off."),
    ("legal.contract.review_days", 5, "days", "p:oscar", _LEG, "Legal reviews standard contracts within {L}."),
    ("legal.nda.term_months", 48, "months", "p:oscar", _LEG, "Mutual NDAs run for {L}."),
    ("legal.msa.renewal_notice_days", 90, "days", "p:oscar", _LEG, "Either party must give {L} of renewal notice."),
    ("legal.dpa.subprocessor_notice_days", 10, "days", "p:ivan", _LEG, "Customers get {L} of notice before a new subprocessor is added."),
    # engineering and IT
    ("eng.oncall.rotation_weeks", 1, "weeks", "p:sara", _ENG, "On-call rotations last {L}."),
    ("eng.deploy.freeze_hours", 48, "hours", "p:arun", _ENG, "Deploy freezes start {L} before major holidays."),
    ("eng.slo.latency_ms", 300, "ms", "p:sara", _ENG, "The API p95 latency objective is {L}."),
    ("eng.postmortem.due_days", 4, "days", "p:sara", _ENG, "Incident postmortems are due within {L}."),
    ("eng.api.deprecation_notice_days", 180, "days", "p:felix", _ENG, "API deprecations are announced {L} in advance."),
    ("eng.backup.retention_days", 35, "days", "p:sara", _ENG, "Database backups are kept for {L}."),
    ("eng.incident.sev1_ack_minutes", 10, "minutes", "p:sara", _ENG, "Severity 1 incidents must be acknowledged within {L}."),
    ("eng.release.cadence_weeks", 2, "weeks", "p:arun", _ENG, "Production releases ship every {L}."),
    ("it.laptop.refresh_months", 36, "months", "p:lars", _ENG, "Laptops are refreshed every {L}."),
    ("it.vpn.session_hours", 10, "hours", "p:lars", _ENG, "VPN sessions last {L}."),
    ("it.helpdesk.sla_hours", 6, "hours", "p:lars", _ENG, "IT helpdesk tickets are answered within {L}."),
    # sales and partners
    ("sales.commission.percent", 8, "percent", "p:diego", _SAL, "Account executives earn {L} commission on new ARR."),
    ("sales.discount.rep_limit_percent", 14, "percent", "p:diego", _SAL, "Sales reps may approve discounts up to {L}."),
    ("sales.discount.manager_limit_percent", 25, "percent", "p:diego", _SAL, "Sales managers may approve discounts up to {L}."),
    ("sales.trial_extension.days", 9, "days", "p:noor", _SAL, "Trials can be extended once by {L}."),
    ("partner.reseller.margin_percent", 28, "percent", "p:hana", _SAL, "Resellers keep {L} of list price."),
    ("partner.referral.fee_percent", 5, "percent", "p:hana", _SAL, "Referral partners earn {L} of first-year revenue."),
    # company
    ("company.headcount.total", 640, "employees", "p:anika", _CO, "Meridian has {L} worldwide."),
    ("company.headcount.engineering", 210, "employees", "p:arun", _CO, "The engineering organisation has {L}."),
    ("company.office.capacity", 120, "people", "p:yusuf", _CO, "The headquarters seats {L}."),
    ("company.office.count", 4, "offices", "p:yusuf", _CO, "Meridian operates {L}."),
]
for _slug, _n, _own, _disc, _pay, _seats in CLIENTS:
    _c = f"src:contract_{_slug}"
    FACTS_SPEC += [
        (f"client.{_slug}.discount_percent", _disc, "percent", _own, _c, f"{_n} receives a contractual discount of {{L}}."),
        (f"client.{_slug}.payment_days", _pay, "days", _own, _c, f"{_n} pays invoices within {{L}}."),
        (f"client.{_slug}.seats", _seats, "seats", _own, _c, f"{_n} has committed to {{L}}."),
    ]

# orphan facts: no document mentions them (a change here must flag NOTHING)
ORPHAN_SPEC = [
    ("finance.audit.fee_kusd", 85, "kUSD", "p:rohan", _FIN, "The annual external audit fee is {L}."),
    ("legal.insurance.cyber_cover_musd", 5, "MUSD", "p:victor", _LEG, "Cyber insurance cover is {L}."),
    ("company.founded.year", 2014, "year", "p:jamal", _CO, "Meridian was founded in {L}."),
]

# derived facts: key -> (base key, multiplier). Rule string on the edge is f"x{multiplier}".
DERIVED = {
    "pricing.team.annual": ("pricing.team.monthly", 10),
    "pricing.business.annual": ("pricing.business.monthly", 10),
    "hr.pto.max_balance_days": ("hr.pto.annual_days", 2),
}

# the regional price (only with with_contradiction=True): same subject+attribute, own key
EU_FACT = ("pricing.business.monthly.eu", 75, "USD", "p:diego", "src:regional_page_2024",
           "The Business plan costs {L} per seat per month in the EU region.")

DOMAIN_OF = {"pricing": "pricing", "support": "support", "sla": "support", "hr": "hr",
             "comp": "comp", "finance": "finance", "security": "security", "privacy": "legal",
             "legal": "legal", "client": "client", "eng": "eng", "it": "eng", "sales": "sales",
             "partner": "sales", "company": "company"}
# domain -> (label, doc kind, system, alt owner, alt system, families?)
DOMAINS = {
    "pricing": ("Pricing", "page", "sys:website_cms", "p:diego", "sys:crm", False),
    "support": ("Support", "kb_article", "sys:helpdesk", "p:omar", "sys:website_cms", True),
    "hr": ("People policy", "policy", "sys:handbook_wiki", "p:daniel", "sys:intranet", True),
    "comp": ("Compensation", "policy", "sys:hris", "p:meera", "sys:handbook_wiki", True),
    "finance": ("Finance policy", "policy", "sys:intranet", "p:rhea", "sys:handbook_wiki", True),
    "security": ("Security", "policy", "sys:trust_center", "p:grace", "sys:eng_wiki", True),
    "legal": ("Legal", "policy", "sys:contract_repo", "p:oscar", "sys:intranet", True),
    "client": ("Client", "account_plan", "sys:crm", "p:kavya", "sys:crm", False),
    "eng": ("Engineering", "runbook", "sys:eng_wiki", "p:sara", "sys:intranet", True),
    "sales": ("Sales", "playbook", "sys:crm", "p:noor", "sys:intranet", True),
    "company": ("Company", "notice", "sys:intranet", "p:jamal", "sys:handbook_wiki", True),
}

# ------------------------------------------------------------------ hand-written documents
# (slug, title, kind, system, owner, derived_from slug | None, template)
# Every {{fact.key}} in a template becomes a CITES edge unless the doc is listed in DARK.
_A = []
def A(slug, title, kind, system, owner, template="", derived=None):
    _A.append((slug, title, kind, f"sys:{system}", f"p:{owner}", derived, template))

# --- pricing and sales (the wide blast radius for pricing.business.monthly)
A("pricing_page", "Pricing page", "page", "website_cms", "samir",
  "Meridian Business costs {{pricing.business.monthly}} per seat per month, or {{pricing.business.annual}} per seat per year. Team costs {{pricing.team.monthly}} per seat. Enterprise starts at {{pricing.enterprise.monthly}}.")
A("order_form_template", "Order form template", "template", "contract_repo", "oscar",
  "Order Form. Business plan list price: {{pricing.business.monthly}} per seat per month. Minimum commitment: {{pricing.seats.minimum}}. Payment terms follow the signed MSA.")
A("sales_deck", "Sales deck", "deck", "crm", "diego",
  "Slide 9: Business at {{pricing.business.monthly}} per seat per month. Slide 10: Enterprise from {{pricing.enterprise.monthly}}.", "pricing_page")
A("quote_tool_notes", "Quote tool defaults", "runbook", "crm", "noor",
  "Quote tool defaults: Business list {{pricing.business.monthly}}, startup discount {{pricing.startup_discount.percent}}, nonprofit discount {{pricing.nonprofit_discount.percent}}.")
A("customer_faq", "Customer FAQ", "faq", "website_cms", "lucy",
  "How much is Business? {{pricing.business.monthly}} per seat per month. Is there a free trial? Yes, {{pricing.trial.days}}. Can I get a refund? Yes, within {{support.refund.days}}.")
A("billing_help_center", "Billing help center", "kb_article", "helpdesk", "omar",
  "Business is billed at {{pricing.business.monthly}} per seat per month or {{pricing.business.annual}} per seat per year. Refunds are available within {{support.refund.days}}.")
A("upgrade_email_template", "Upgrade email template", "template", "crm", "mia",
  "Upgrade to Business for {{pricing.business.monthly}} per seat per month and keep your {{pricing.trial.days}} of trial data.")
A("competitor_comparison", "Competitor comparison page", "page", "website_cms", "mia",
  "Meridian Business at {{pricing.business.monthly}} per seat includes SSO and audit logs. Meridian Team at {{pricing.team.monthly}} per seat covers small teams.")
A("revenue_forecast", "FY27 Q1 revenue forecast", "forecast", "finance_sheet", "rohan",
  "The Q1 forecast assumes 4200 Business seats at {{pricing.business.monthly}} per seat per month and 900 Team seats at {{pricing.team.monthly}}.")
A("arr_model", "ARR model", "model", "finance_sheet", "rhea",
  "ARR model inputs: Business {{pricing.business.monthly}} monthly or {{pricing.business.annual}} annual per seat; Team {{pricing.team.monthly}} monthly or {{pricing.team.annual}} annual.")
A("renewal_playbook", "Renewal playbook", "playbook", "crm", "kavya",
  "Renewals: Business list price is {{pricing.business.monthly}} per seat. Reps may discount up to {{sales.discount.rep_limit_percent}}; managers up to {{sales.discount.manager_limit_percent}}.")
A("discount_matrix", "Discount approval matrix", "policy", "crm", "diego",
  "Discount approvals: up to {{sales.discount.rep_limit_percent}} by reps, up to {{sales.discount.manager_limit_percent}} by sales managers. Nonprofits receive {{pricing.nonprofit_discount.percent}}.")
A("partner_price_list", "Partner price list", "price_list", "partner_portal", "hana",
  "Partner price list: Business {{pricing.business.monthly}} per seat list. Resellers keep {{partner.reseller.margin_percent}}; referral partners earn {{partner.referral.fee_percent}}.")
A("support_macro_pricing", "Support macro: pricing question", "macro", "helpdesk", "omar",
  "Thanks for your interest. Our current Business price is shown in the customer FAQ.", "customer_faq")
A("support_macro_upgrade", "Support macro: upgrade", "macro", "helpdesk", "omar",
  "To upgrade, open Billing and choose Business. The current price is listed in the billing help centre.", "billing_help_center")
A("support_macro_discounts", "Support macro: discounts", "macro", "helpdesk", "omar",
  "Discounts depend on your segment. See the discount approval matrix for what we can offer.", "discount_matrix")
A("sales_training_deck", "Sales onboarding deck", "deck", "intranet", "diego",
  "Module 3 walks new reps through our pricing narrative, following the sales deck.", "sales_deck")
A("sales_battlecard", "Competitive battlecard", "deck", "crm", "mia",
  "Battlecard: position Business against rivals using the comparison page.", "competitor_comparison")
A("cs_renewal_email", "Customer success renewal email", "template", "crm", "kavya",
  "Hello, your renewal is coming up. We will confirm pricing as described in the renewal playbook.", "renewal_playbook")
A("partner_enablement_deck", "Partner enablement deck", "deck", "partner_portal", "hana",
  "Partner kickoff slides: how to quote customers using the partner price list.", "partner_price_list")
A("investor_update", "Investor update draft", "update", "finance_sheet", "rohan",
  "Business revenue is tracking to plan based on the current forecast and list pricing.", "revenue_forecast")
A("board_deck", "Board deck", "deck", "finance_sheet", "rohan",
  "Appendix B: revenue projections follow the Q1 forecast model.", "investor_update")
A("board_appendix_pack", "Board appendix pack", "deck", "finance_sheet", "rohan",
  "Pre-read pack assembled from the board deck for non-executive directors.", "board_deck")
A("qbr_template", "QBR template", "template", "crm", "kavya",
  "Quarterly business review structure, with revenue slides driven by the ARR model.", "arr_model")
A("localisation_brief", "Website localisation brief", "brief", "website_cms", "mia",
  "Translators should mirror the pricing page, including plan names.", "pricing_page")
A("analyst_briefing", "Analyst briefing notes", "brief", "intranet", "mia",
  "Talking points for industry analysts, based on the sales deck narrative.", "sales_deck")
A("pricing_faq_widget", "Website pricing FAQ widget", "widget", "website_cms", "mia",
  "Business is {{pricing.business.monthly}} per seat per month. Start with a {{pricing.trial.days}} free trial.")
A("rfp_pricing_response", "RFP pricing response", "kb_article", "crm", "noor",
  "Standard RFP answer: Business is {{pricing.business.monthly}} per seat per month and Enterprise starts at {{pricing.enterprise.monthly}}.")
A("commission_calculator", "Commission calculator notes", "model", "finance_sheet", "noor",
  "Calculator assumes Business list price of {{pricing.business.monthly}} per seat and commission of {{sales.commission.percent}} on new ARR.")
A("sales_enablement_quiz", "Sales enablement quiz", "quiz", "intranet", "diego",
  "Quiz questions on pricing and packaging, built from the sales onboarding deck.", "sales_training_deck")
A("partner_certification_course", "Partner certification course", "course", "partner_portal", "hana",
  "Certification modules for partners, extending the partner enablement deck.", "partner_enablement_deck")
A("qbr_executive_summary", "QBR executive summary", "report", "crm", "kavya",
  "One-page summary distilled from the QBR template for executives.", "qbr_template")
# --- HR and employees
A("employee_handbook", "Employee handbook", "handbook", "handbook_wiki", "anika",
  "Time off: {{hr.pto.annual_days}} of paid leave each year, capped at {{hr.pto.max_balance_days}} carried over. Sick leave: {{hr.sick.days}}. Remote work: up to {{hr.remote.days_per_week}} per week. Working week: {{hr.work.hours_per_week}}.")
A("benefits_guide", "Benefits guide", "guide", "hris", "meera",
  "Benefits: wellness stipend {{hr.wellness.stipend_usd}} per month, learning budget {{hr.learning.budget_usd}} per year, {{hr.holidays.company_days}} of company holidays, parental leave of {{hr.parental.primary_weeks}} for primary and {{hr.parental.secondary_weeks}} for secondary caregivers.")
A("offer_letter_template", "Offer letter template", "template", "hris", "tara",
  "Your offer includes {{hr.pto.annual_days}} of paid leave, a probation period of {{hr.probation.months}}, a notice period of {{hr.notice.days}}, and equity vesting over {{comp.equity.vesting_years}} with a cliff of {{comp.equity.cliff_months}}.")
A("onboarding_checklist", "New hire onboarding checklist", "checklist", "handbook_wiki", "daniel",
  "Week one: complete security training ({{security.training.hours}}), set a password of at least {{security.password.min_length}}, meet your buddy for {{hr.onboarding.buddy_weeks}}, and plan your {{hr.pto.annual_days}} of leave.")
A("payroll_calendar", "Payroll calendar", "calendar", "hris", "meera",
  "Referral bonuses of {{hr.referral.bonus_usd}} are paid after the referred hire completes a probation of {{hr.probation.months}}.")
A("comp_bands_sheet", "Compensation bands", "sheet", "hris", "meera",
  "L3 band: {{comp.band.l3.min}} to {{comp.band.l3.max}}. L4 band starts at {{comp.band.l4.min}}.")
A("recruiting_faq", "Recruiting FAQ", "faq", "website_cms", "tara",
  "Candidates ask: yes, we offer {{hr.pto.annual_days}} of paid leave and up to {{hr.remote.days_per_week}} of remote work per week.")
A("hr_leave_form", "Leave request form", "form", "hris", "meera",
  "Your leave balance cannot exceed {{hr.pto.max_balance_days}}. Submit requests through the portal.")
A("sabbatical_policy", "Sabbatical policy", "policy", "handbook_wiki", "anika",
  "After {{hr.sabbatical.years}} of service, employees may apply for a sabbatical. Learning budget of {{hr.learning.budget_usd}} remains available.")
A("manager_handbook", "Manager handbook", "handbook", "handbook_wiki", "daniel",
  "Guidance for managers on leave approvals and team scheduling; see the employee handbook for entitlements.", "employee_handbook")
A("hr_slack_bot_answers", "HR Slack assistant answers", "bot", "slack_bot", "daniel",
  "Canned answers about leave and working arrangements, sourced from the employee handbook.", "employee_handbook")
A("new_hire_welcome_slides", "New hire welcome slides", "deck", "intranet", "chloe",
  "Welcome deck for week one, following the onboarding checklist.", "onboarding_checklist")
A("benefits_webinar_deck", "Benefits webinar deck", "deck", "intranet", "meera",
  "Webinar slides summarising the benefits guide.", "benefits_guide")
A("hiring_manager_kit", "Hiring manager kit", "guide", "handbook_wiki", "tara",
  "Interview and offer process; use the offer letter template for terms.", "offer_letter_template")
A("exec_people_report", "Executive people report", "report", "intranet", "anika",
  "Quarterly people metrics, drawing on the manager handbook for policy context.", "manager_handbook")
A("org_chart", "Org chart 2026", "chart", "intranet", "jamal",
  "Meridian has {{company.headcount.total}} across {{company.office.count}}, with {{company.headcount.engineering}} in engineering.")
A("office_guide", "Office guide", "guide", "intranet", "yusuf",
  "Our headquarters seats {{company.office.capacity}}. Remote staff may visit up to {{hr.remote.days_per_week}} of the week by agreement.")
A("all_hands_deck", "All-hands deck", "deck", "intranet", "jamal",
  "Company update slides based on the org chart.", "org_chart")
# --- finance
A("expense_policy", "Expense policy", "policy", "intranet", "rhea",
  "Expenses above {{finance.expense.approval_limit}} need manager approval. Receipts are required above {{finance.expense.receipt_threshold}}. Submit claims within {{finance.expense.submission_days}}.")
A("travel_policy", "Travel policy", "policy", "intranet", "rhea",
  "Hotel cap: {{finance.travel.hotel_cap}} per night. Meals: {{finance.travel.meal_per_diem}} per day.")
A("procurement_guide", "Procurement guide", "guide", "intranet", "elena",
  "Purchase orders are required above {{finance.po.threshold}}. Approved vendors are paid within {{finance.vendor.payment_days}}.")
A("corporate_card_guide", "Corporate card guide", "guide", "intranet", "rhea",
  "Monthly card limit: {{finance.card.monthly_limit}}. Keep receipts for anything above {{finance.expense.receipt_threshold}}.")
A("invoice_template", "Invoice template", "template", "finance_sheet", "rhea",
  "Invoice payment terms: {{finance.invoice.payment_terms_days}} from the issue date.")
A("expense_claim_macro", "Expense claim assistant answers", "bot", "slack_bot", "rhea",
  "Answers to common expense questions, drawn from the expense policy.", "expense_policy")
A("travel_booking_bot", "Travel booking assistant", "bot", "slack_bot", "rhea",
  "Helps staff book travel within policy; see the travel policy.", "travel_policy")
A("finance_training_deck", "Finance onboarding deck", "deck", "intranet", "rhea",
  "Training slides for new managers on procurement, based on the procurement guide.", "procurement_guide")
A("vendor_onboarding_form", "Vendor onboarding form", "form", "intranet", "elena",
  "Forms and checks for adding a vendor, following the procurement guide.", "procurement_guide")
# --- security, privacy, legal
A("security_policy", "Information security policy", "policy", "trust_center", "tomas",
  "Passwords must be at least {{security.password.min_length}}. Sessions expire after {{security.session.timeout_hours}}. Access reviews occur every {{security.access_review.months}}. Logs are retained for {{security.log.retention_days}}.")
A("trust_center_page", "Trust center page", "page", "trust_center", "grace",
  "Penetration tests run every {{security.pentest.interval_months}}. Customers are notified of incidents within {{security.incident.notify_hours}}. Logs are retained for {{security.log.retention_days}}.")
A("security_answer_bank", "Security questionnaire answer bank", "kb_article", "trust_center", "grace",
  "Password length: {{security.password.min_length}}. Incident notification: {{security.incident.notify_hours}}. Vendor reviews every {{security.vendor.review_months}}.")
A("dpa_template", "Data processing agreement template", "contract", "contract_repo", "ivan",
  "The processor will notify the controller of a personal data breach within {{security.incident.notify_hours}}. Subprocessor changes are notified {{legal.dpa.subprocessor_notice_days}} in advance. Data is deleted {{privacy.data.retention_months}} after termination.")
A("it_setup_guide", "IT setup guide", "guide", "eng_wiki", "lars",
  "Set a password of at least {{security.password.min_length}}. VPN sessions last {{it.vpn.session_hours}}. Laptops are refreshed every {{it.laptop.refresh_months}}. Generate {{security.mfa.backup_codes}} and store them safely.")
A("incident_runbook", "Incident response runbook", "runbook", "eng_wiki", "sara",
  "Acknowledge Sev1 incidents within {{eng.incident.sev1_ack_minutes}}. Notify affected customers within {{security.incident.notify_hours}}. Postmortems are due within {{eng.postmortem.due_days}}.")
A("patching_standard", "Vulnerability patching standard", "policy", "eng_wiki", "tomas",
  "Critical vulnerabilities are patched within {{security.patch.critical_days}}. Pentest cadence: every {{security.pentest.interval_months}}.")
A("privacy_policy", "Privacy policy", "policy", "website_cms", "ivan",
  "We answer data subject requests within {{privacy.dsar.response_days}}. Customer data is deleted {{privacy.data.retention_months}} after termination. Security logs are kept for {{security.log.retention_days}}.")
A("contract_signing_guide", "Contract signing guide", "guide", "contract_repo", "oscar",
  "Contracts above {{legal.signature.limit_kusd}} need CFO sign-off. Legal review takes {{legal.contract.review_days}}. NDAs run for {{legal.nda.term_months}}.")
A("dsar_runbook", "DSAR runbook", "runbook", "intranet", "ivan",
  "Respond to every data subject request within {{privacy.dsar.response_days}}.")
A("subprocessor_notice", "Subprocessor notice page", "notice", "trust_center", "ivan",
  "We notify customers {{legal.dpa.subprocessor_notice_days}} before adding a subprocessor.")
A("security_awareness_deck", "Security awareness deck", "deck", "intranet", "grace",
  "Annual training slides based on the information security policy.", "security_policy")
A("phishing_training_module", "Phishing training module", "deck", "intranet", "chloe",
  "Interactive module built from the security awareness deck.", "security_awareness_deck")
A("customer_security_whitepaper", "Customer security whitepaper", "report", "trust_center", "grace",
  "Whitepaper for prospects, expanded from the trust center page.", "trust_center_page")
A("rfp_security_response", "RFP security response", "kb_article", "crm", "noor",
  "Standard RFP security answers drawn from the answer bank.", "security_answer_bank")
A("vendor_security_checklist", "Vendor security checklist", "checklist", "intranet", "elena",
  "Checklist for onboarding vendors, aligned with the DPA template.", "dpa_template")
A("it_welcome_email", "IT welcome email", "template", "intranet", "lars",
  "Welcome email pointing new joiners to the IT setup guide.", "it_setup_guide")
A("postmortem_template", "Postmortem template", "template", "eng_wiki", "sara",
  "Blameless postmortem structure; follow the incident response runbook for deadlines.", "incident_runbook")
A("legal_intake_macro", "Legal intake assistant answers", "bot", "slack_bot", "oscar",
  "Answers to legal intake questions, from the contract signing guide.", "contract_signing_guide")
A("privacy_faq_macro", "Privacy FAQ macro", "macro", "helpdesk", "ivan",
  "Support replies about privacy, referring to the privacy policy.", "privacy_policy")
A("dsar_training", "DSAR training deck", "deck", "intranet", "ivan",
  "Training for the support team, based on the DSAR runbook.", "dsar_runbook")
# --- SLA and support
A("sla_schedule", "SLA schedule", "contract", "contract_repo", "oscar",
  "Uptime commitment: {{sla.uptime.percent}}. Service credit: {{sla.credit.percent}} of monthly fees. P1 response within {{support.p1.response_hours}}; P2 within {{support.p2.response_hours}}.")
A("support_handbook", "Support handbook", "handbook", "helpdesk", "lucy",
  "P1 tickets: first response within {{support.p1.response_hours}}. P2: {{support.p2.response_hours}}. Live chat first reply within {{support.chat.first_reply_minutes}}. CSAT target: {{support.csat.target_percent}}. Escalate after {{support.escalation.minutes}}.")
A("status_page_template", "Status page template", "template", "website_cms", "sara",
  "We target {{sla.uptime.percent}} uptime every month.")
A("msa_template", "Master services agreement template", "contract", "contract_repo", "victor",
  "Provider commits to {{sla.uptime.percent}} uptime with service credits of {{sla.credit.percent}}. Renewal notice: {{legal.msa.renewal_notice_days}}. Standard contracts are reviewed within {{legal.contract.review_days}}.")
A("refund_policy_page", "Refund policy", "policy", "website_cms", "lucy",
  "Full refunds are available within {{support.refund.days}} of purchase.")
A("support_training_deck", "Support onboarding deck", "deck", "intranet", "lucy",
  "New agent training, following the support handbook.", "support_handbook")
A("escalation_macro", "Escalation macro", "macro", "helpdesk", "omar",
  "Escalating your ticket now, as described in the support handbook.", "support_handbook")
A("sla_summary_for_sales", "SLA summary for sales", "brief", "crm", "diego",
  "One-page summary of our service commitments for prospects.", "sla_schedule")
A("rfp_sla_answer", "RFP SLA answer", "kb_article", "crm", "noor",
  "Standard answers on service levels, taken from the MSA template.", "msa_template")
A("customer_sla_email", "Customer SLA email", "template", "crm", "kavya",
  "Email explaining service levels to customers, per the SLA schedule.", "sla_schedule")
A("trust_center_sla_blurb", "Trust center SLA blurb", "page", "trust_center", "grace",
  "Short public summary derived from the sales SLA brief.", "sla_summary_for_sales")
# --- engineering
A("oncall_handbook", "On-call handbook", "runbook", "eng_wiki", "sara",
  "Rotations last {{eng.oncall.rotation_weeks}}. Sev1 acknowledgement within {{eng.incident.sev1_ack_minutes}}. Postmortems due within {{eng.postmortem.due_days}}.")
A("release_process", "Release process", "runbook", "eng_wiki", "arun",
  "Releases ship every {{eng.release.cadence_weeks}}. Deploy freezes start {{eng.deploy.freeze_hours}} before major holidays. Backups are kept {{eng.backup.retention_days}}.")
A("api_deprecation_policy", "API deprecation policy", "policy", "eng_wiki", "felix",
  "Deprecations are announced {{eng.api.deprecation_notice_days}} in advance. API limit: {{pricing.api.rate_limit}}. Latency objective: {{eng.slo.latency_ms}}.")
A("developer_portal_page", "Developer portal page", "page", "website_cms", "felix",
  "Public API: {{pricing.api.rate_limit}}, p95 latency under {{eng.slo.latency_ms}}.")
A("it_helpdesk_guide", "IT helpdesk guide", "guide", "eng_wiki", "lars",
  "IT tickets are answered within {{it.helpdesk.sla_hours}}.")
A("sre_training_deck", "SRE training deck", "deck", "intranet", "sara",
  "Training slides for new on-call engineers, from the on-call handbook.", "oncall_handbook")
A("release_comms_template", "Release communications template", "template", "eng_wiki", "felix",
  "Announcement template following the release process.", "release_process")
A("api_changelog_macro", "API changelog macro", "macro", "helpdesk", "omar",
  "Support replies on API changes, per the deprecation policy.", "api_deprecation_policy")
A("sdk_readme", "SDK readme", "doc", "eng_wiki", "felix",
  "Getting-started notes mirroring the developer portal page.", "developer_portal_page")
# --- dark dependencies: the literal is printed but there is NO citation (graph cannot see it)
DARK = {
    "partner_portal_faq": ("Partner portal FAQ", "faq", "partner_portal", "hana",
        "Resellers can quote the public Business price of {{pricing.business.monthly}} per seat per month."),
    "old_pricing_blog": ("Pricing announcement blog post", "blog", "website_cms", "mia",
        "We are proud to offer Business at {{pricing.business.monthly}} per seat."),
    "reseller_onboarding_pdf": ("Reseller onboarding PDF", "pdf", "partner_portal", "hana",
        "Standard Business pricing is {{pricing.business.monthly}} per seat per month; trials last {{pricing.trial.days}}."),
    "conference_booth_script": ("Conference booth script", "script", "intranet", "mia",
        "Say: Business starts at {{pricing.business.monthly}} per seat."),
    "careers_benefits_page": ("Careers benefits page", "page", "website_cms", "tara",
        "Enjoy {{hr.pto.annual_days}} of paid leave and a {{hr.learning.budget_usd}} learning budget."),
    "candidate_welcome_email": ("Candidate welcome email", "template", "intranet", "tara",
        "We offer up to {{hr.remote.days_per_week}} of remote work per week."),
    "team_offsite_wiki": ("Team offsite wiki", "wiki", "intranet", "jamal",
        "Hotel budget for offsites is {{finance.travel.hotel_cap}} per night."),
    "northwind_security_questionnaire": ("Northwind security questionnaire", "questionnaire", "crm", "ines",
        "Passwords require at least {{security.password.min_length}} and breaches are reported within {{security.incident.notify_hours}}."),
    "enterprise_proposal_pdf": ("Enterprise proposal PDF", "pdf", "crm", "diego",
        "We guarantee {{sla.uptime.percent}} uptime and a P1 response within {{support.p1.response_hours}}."),
    "partner_api_guide": ("Partner API guide", "guide", "partner_portal", "hana",
        "Partners may call the API up to {{pricing.api.rate_limit}}."),
    "legacy_vendor_contract": ("Legacy vendor contract template", "contract", "contract_repo", "oscar",
        "Subprocessor notice period: {{legal.dpa.subprocessor_notice_days}}."),
    "northwind_proposal_pdf": ("Northwind renewal proposal PDF", "pdf", "crm", "ines",
        "Proposed payment terms for Northwind remain {{client.northwind.payment_days}}."),
}
# --- near-miss distractors: contain the same digits, but NOT the rendered literal
NEAR_MISS = {
    "careers_page": ("Careers page", "page", "website_cms", "anika",
        "Join our team of 79 engineers building workflow software for 14 industries."),
    "customers_page": ("Customers page", "page", "website_cms", "mia",
        "Trusted by 149 enterprise customers across 30 countries, with 39 integrations."),
    "workplace_award_post": ("Workplace award post", "post", "website_cms", "jamal",
        "Ranked among the top 24 workplaces, with staff in 12 cities."),
    "status_history_blog": ("Status history blog", "blog", "website_cms", "sara",
        "We served 72 regions last year and stored 365 million events."),
    "security_champions_post": ("Security champions post", "post", "intranet", "grace",
        "Our 14 champions ran 3 workshops and reviewed 9 apps."),
    "support_milestone_post": ("Support milestone post", "post", "intranet", "lucy",
        "The team handled 92 thousand tickets across 4 languages."),
}
# --- unrelated documents (no figures at all)
UNRELATED = {
    "brand_guidelines": ("Brand guidelines", "guide", "website_cms", "mia", "Use the blue wordmark on light backgrounds and keep clear space around the logo."),
    "press_kit": ("Press kit", "kit", "website_cms", "mia", "Boilerplate, logos and executive headshots for media use."),
    "values_statement": ("Company values", "page", "intranet", "anika", "We value clarity, ownership and kindness in how we work together."),
    "meeting_etiquette": ("Meeting etiquette", "guide", "handbook_wiki", "daniel", "Share an agenda in advance and end with clear owners for each action."),
    "slack_etiquette": ("Slack etiquette", "guide", "handbook_wiki", "jamal", "Prefer threads, use channels by topic and mute when focusing."),
    "holiday_party_invite": ("Holiday party invite", "post", "intranet", "yusuf", "Join us for the annual celebration at the headquarters atrium."),
    "design_principles": ("Design principles", "guide", "eng_wiki", "neha", "Make the common path obvious and the rare path possible."),
    "coding_conventions": ("Coding conventions", "guide", "eng_wiki", "arun", "Prefer small pull requests, clear names and tests for every change."),
    "open_source_policy": ("Open source policy", "policy", "eng_wiki", "felix", "Contributions are welcome after a licence check by Legal."),
    "customer_story_template": ("Customer story template", "template", "website_cms", "mia", "Outline: challenge, solution, outcome, quote."),
}

# annotations exported for tests (ground-truth the oracle does NOT use)
DARK_DEPENDENCIES: dict[str, list[str]] = {}
NEAR_MISS_DOCS = [f"doc:{s}" for s in NEAR_MISS]
UNRELATED_DOCS = [f"doc:{s}" for s in UNRELATED]
ORPHAN_FACTS = [f"fact:{k}@v1" for k, *_ in ORPHAN_SPEC]

_PH = re.compile(r"\{\{([a-z0-9_.]+)\}\}")


def _fid(key: str, v: int = 1) -> str:
    return f"fact:{key}@v{v}"


def _assemble() -> dict:
    rng = random.Random(42)
    spec = {s[0]: s for s in FACTS_SPEC + ORPHAN_SPEC + [EU_FACT]}
    values: dict[str, float] = {}
    for key, (base, mult) in DERIVED.items():
        values[key] = spec[base][1] * mult
    for key, s in spec.items():
        values.setdefault(key, s[1])
    unit = {k: s[2] for k, s in spec.items()}
    lit = {k: render_literal(unit[k], values[k]) for k in spec}

    def fact_row(k):
        s = spec[k]
        parts = k.split(".")
        subject, attribute = "_".join(parts[:-1]), parts[-1]
        if k == "pricing.business.monthly.eu":
            subject, attribute = "pricing_business", "monthly"
        if k == "pricing.business.monthly":
            subject, attribute = "pricing_business", "monthly"
        return {"id": _fid(k), "key": k, "version": 1, "subject": subject, "attribute": attribute,
                "value": values[k], "unit": unit[k], "status": "ACTIVE", "created_at": SEED_TIME}

    main_keys = [s[0] for s in FACTS_SPEC] + [s[0] for s in ORPHAN_SPEC]
    facts = [fact_row(k) for k in main_keys]
    fact_sourced = [{"fact": _fid(k), "source": spec[k][4]} for k in main_keys]
    fact_owned = [{"fact": _fid(k), "person": spec[k][3]} for k in main_keys]
    fact_derived = [{"fact": _fid(k), "from_fact": _fid(b), "rule": f"x{m}"} for k, (b, m) in DERIVED.items()]

    docs, cites, derived, published, owned = {}, [], [], [], []

    def add_doc(slug, title, kind, system, owner, content, cite_keys=(), parent=None):
        did = f"doc:{slug}"
        assert did not in docs, did
        docs[did] = {"id": did, "title": title, "kind": kind, "status": "CURRENT",
                     "last_reviewed": rng.choice(_REVIEW_DATES), "content": content}
        for k in dict.fromkeys(cite_keys):
            cites.append({"doc": did, "fact": _fid(k)})
        if parent:
            derived.append({"doc": did, "from_doc": f"doc:{parent}"})
        published.append({"doc": did, "system": system})
        owned.append({"doc": did, "person": owner})

    def render(tpl):
        keys = _PH.findall(tpl)
        for k in keys:
            assert k in spec, f"unknown fact in template: {k}"
        return _PH.sub(lambda m: lit[m.group(1)], tpl), keys

    # clients first (named accounts)
    for slug, name, owner, *_ in CLIENTS:
        d, p, s = f"client.{slug}.discount_percent", f"client.{slug}.payment_days", f"client.{slug}.seats"
        c, ck = render(f"{name} has committed to {{{{{s}}}}} with a negotiated discount of {{{{{d}}}}} and payment terms of {{{{{p}}}}}.")
        add_doc(f"account_plan_{slug}", f"{name} account plan", "account_plan", "sys:crm", owner, c, ck)
        add_doc(f"qbr_deck_{slug}", f"{name} QBR deck", "deck", "sys:crm", owner,
                f"Quarterly review slides for {name}, based on the account plan.", (), f"account_plan_{slug}")
        c, ck = render(f"Renewal brief for {name}: current discount {{{{{d}}}}}, payment terms {{{{{p}}}}}.")
        add_doc(f"renewal_brief_{slug}", f"{name} renewal brief", "brief", "sys:crm", owner, c, ck)
        add_doc(f"renewal_email_{slug}", f"{name} renewal email", "template", "sys:crm", owner,
                f"Draft renewal email for {name}, following the renewal brief.", (), f"renewal_brief_{slug}")
    # hand-written documents
    for slug, title, kind, system, owner, parent, tpl in _A:
        c, ck = render(tpl)
        add_doc(slug, title, kind, system, owner, c, ck, parent)
    # dark dependencies and distractors
    for slug, (title, kind, system, owner, tpl) in DARK.items():
        c, ck = render(tpl)
        add_doc(slug, title, kind, f"sys:{system}", f"p:{owner}", c, ())
        for k in ck:
            DARK_DEPENDENCIES.setdefault(_fid(k), []).append(f"doc:{slug}")
    for table in (NEAR_MISS, UNRELATED):
        for slug, (title, kind, system, owner, text) in table.items():
            add_doc(slug, title, kind, f"sys:{system}", f"p:{owner}", text)
    # per-fact document families for policy-style domains
    for idx, (k, *_rest) in enumerate(FACTS_SPEC):
        dom = DOMAIN_OF[k.split(".")[0]]
        label, kind, system, alt_owner, alt_system, families = DOMAINS[dom]
        if not families:
            continue
        slug, name = k.replace(".", "_"), " ".join(k.split(".")[1:]).replace("_", " ")
        sentence = spec[k][5].replace("{L}", lit[k])
        owner = spec[k][3]
        add_doc(f"{slug}_page", f"{label}: {name}", kind, system, owner, sentence, [k])
        add_doc(f"{slug}_faq", f"FAQ: {name}", "faq", alt_system, alt_owner,
                f"Q: What is the rule for {name}? A: {sentence}", [k])
        if k in DERIVED:
            continue                      # derived facts: page + FAQ only (see module docstring)
        add_doc(f"{slug}_brief", f"Manager briefing: {name}", "brief", "sys:slack_bot", alt_owner,
                f"Briefing for managers on {name}. Check the official page for the current figure before answering.",
                (), f"{slug}_page")
        if idx % 3 == 0:
            add_doc(f"{slug}_slide", f"Training slide: {name}", "slide", "sys:intranet", owner,
                    f"Training slide on {name}, based on the manager briefing.", (), f"{slug}_brief")

    # drop dangling annotation keys (should be none) and sort for determinism
    nodes = {
        "people": PEOPLE, "systems": SYSTEMS, "sources": SOURCES, "facts": facts,
        "documents": list(docs.values()), "meta": [{"id": "main", "revision": 1}],
    }
    edges = {
        "fact_sourced": fact_sourced, "fact_owned": fact_owned, "fact_derived": fact_derived,
        "doc_cites": cites, "doc_derived": derived, "doc_published": published, "doc_owned": owned,
    }
    out = {**nodes, **edges}
    out["_eu"] = {  # contradiction extras
        "fact": fact_row("pricing.business.monthly.eu"),
        "sourced": {"fact": _fid("pricing.business.monthly.eu"), "source": EU_FACT[4]},
        "owned": {"fact": _fid("pricing.business.monthly.eu"), "person": EU_FACT[3]},
        "doc": {"id": "doc:eu_pricing_page", "title": "EU pricing page", "kind": "page", "status": "CURRENT",
                "last_reviewed": "2026-06-01",
                "content": EU_FACT[5].replace("{L}", lit["pricing.business.monthly.eu"])},
    }
    out["_literals"] = lit
    return out


_BASE = _assemble()
LITERALS = _BASE["_literals"]

SCENARIOS = {
    "A": {"title": "Raise Business monthly price to $89",
          "fact_key": "pricing.business.monthly", "new_value": 89,
          "source_id": "src:pricing_committee_memo_2026_10", "with_contradiction": False},
    "B": {"title": "Cut breach notification window to 24 hours (unverified source)",
          "fact_key": "security.incident.notify_hours", "new_value": 24,
          "source_id": "src:slack_rumor_2026_10", "with_contradiction": False},
    "C": {"title": "Raise Business monthly price to $89 (EU price conflict)",
          "fact_key": "pricing.business.monthly", "new_value": 89,
          "source_id": "src:pricing_committee_memo_2026_10", "with_contradiction": True},
    "D": {"title": "Increase annual paid leave to 27 days",
          "fact_key": "hr.pto.annual_days", "new_value": 27,
          "source_id": "src:board_resolution_2026_09", "with_contradiction": False},
    "E": {"title": "Extend Northwind payment terms to 45 days",
          "fact_key": "client.northwind.payment_days", "new_value": 45,
          "source_id": "src:northwind_amendment_2026_10", "with_contradiction": False},
    "F": {"title": "Tighten live chat first reply target to 3 minutes",
          "fact_key": "support.chat.first_reply_minutes", "new_value": 3,
          "source_id": "src:sla_schedule_2026", "with_contradiction": False},
    "G": {"title": "Update external audit fee (no documents mention it)",
          "fact_key": "finance.audit.fee_kusd", "new_value": 90,
          "source_id": "src:finance_policy_2026", "with_contradiction": False},
    "H": {"title": "Raise remote days to 5 (outdated wiki source)",
          "fact_key": "hr.remote.days_per_week", "new_value": 5,
          "source_id": "src:outdated_wiki_2022", "with_contradiction": False},
}


def build_dataset(with_contradiction: bool = False) -> dict:
    ds = {k: v for k, v in _BASE.items() if not k.startswith("_")}
    ds = copy.deepcopy(ds)
    if with_contradiction:
        eu = copy.deepcopy(_BASE["_eu"])
        ds["facts"].append(eu["fact"])
        ds["fact_sourced"].append(eu["sourced"])
        ds["fact_owned"].append(eu["owned"])
        ds["documents"].append(eu["doc"])
        ds["doc_cites"].append({"doc": eu["doc"]["id"], "fact": eu["fact"]["id"]})
        ds["doc_published"].append({"doc": eu["doc"]["id"], "system": "sys:website_cms"})
        ds["doc_owned"].append({"doc": eu["doc"]["id"], "person": "p:diego"})
    return ds
"""
Dataset Catalog Registry for TruthBranch.
Supports multi-tenant company knowledge switching.
"""
from __future__ import annotations

from typing import Any, Callable
from backend.app.seed.datasets import lumen, cloudgrid

CATALOG: dict[str, dict[str, Any]] = {
    "lumen": {
        "id": "lumen",
        "name": "Lumen Analytics",
        "domain": "Product Analytics & B2B SaaS",
        "description": "B2B SaaS product analytics platform (pricing plans, refund policies, sales decks, customer FAQs).",
        "builder": lumen.build_dataset,
        "scenarios": lumen.SCENARIOS,
        "default_graph": "kb_main",
    },
    "cloudgrid": {
        "id": "cloudgrid",
        "name": "CloudGrid Infrastructure",
        "domain": "Enterprise Cloud & AI Compute",
        "description": "Enterprise cloud GPU cluster provider (H100 hourly rates, uptime SLA guarantees, cluster sizing macros).",
        "builder": cloudgrid.build_dataset,
        "scenarios": cloudgrid.SCENARIOS,
        "default_graph": "kb_dataset_cloudgrid",
    },
}


def get_catalog_entry(dataset_id: str) -> dict[str, Any] | None:
    return CATALOG.get(dataset_id)


def list_catalog_entries() -> list[dict[str, Any]]:
    return [
        {
            "id": entry["id"],
            "name": entry["name"],
            "domain": entry["domain"],
            "description": entry["description"],
            "default_graph": entry["default_graph"],
        }
        for entry in CATALOG.values()
    ]

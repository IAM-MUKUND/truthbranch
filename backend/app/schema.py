"""
Schema constants and ID generation helpers for TruthBranch.
"""

# --------------------------------------------------------------------------- Node Labels
LABEL_FACT = "Fact"
LABEL_SOURCE = "Source"
LABEL_DOCUMENT = "Document"
LABEL_SYSTEM = "System"
LABEL_PERSON = "Person"
LABEL_PROPOSED_EDIT = "ProposedEdit"
LABEL_META = "Meta"

# --------------------------------------------------------------------------- Relationship Types
REL_SOURCED_FROM = "SOURCED_FROM"
REL_SUPERSEDES = "SUPERSEDES"
REL_DERIVED_FROM = "DERIVED_FROM"
REL_OWNED_BY = "OWNED_BY"
REL_CITES = "CITES"
REL_PUBLISHED_IN = "PUBLISHED_IN"
REL_EDITS = "EDITS"

# --------------------------------------------------------------------------- Fact & Doc Status
FACT_STATUS_ACTIVE = "ACTIVE"
FACT_STATUS_SUPERSEDED = "SUPERSEDED"
FACT_STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"

DOC_STATUS_CURRENT = "CURRENT"
DOC_STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"

# --------------------------------------------------------------------------- ID Helpers
def fact_id(key: str, version: int = 1) -> str:
    return f"fact:{key}@v{version}"

def doc_id(slug: str) -> str:
    return f"doc:{slug}" if not slug.startswith("doc:") else slug

def person_id(slug: str) -> str:
    return f"p:{slug}" if not slug.startswith("p:") else slug

def source_id(slug: str) -> str:
    return f"src:{slug}" if not slug.startswith("src:") else slug

def system_id(slug: str) -> str:
    return f"sys:{slug}" if not slug.startswith("sys:") else slug

def branch_graph_name(cr_id: str) -> str:
    return f"kb_{cr_id}" if not cr_id.startswith("kb_") else cr_id

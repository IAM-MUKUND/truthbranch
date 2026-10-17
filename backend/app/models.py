"""
Data models and state machine for TruthBranch.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- Enums
class CRStatus(str, Enum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"
    CHECKS_PASSED = "CHECKS_PASSED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MERGED = "MERGED"
    CONFLICT = "CONFLICT"


class CheckSeverity(str, Enum):
    BLOCK = "BLOCK"
    WARN = "WARN"


class CheckCode(str, Enum):
    SOURCE_MISSING = "SOURCE_MISSING"
    SOURCE_INVALID = "SOURCE_INVALID"
    STALE_DEPENDENCY = "STALE_DEPENDENCY"
    CONTRADICTION = "CONTRADICTION"
    LITERAL_VALUE_LEAK = "LITERAL_VALUE_LEAK"
    STALE_OWNER = "STALE_OWNER"


class OpType(str, Enum):
    UPDATE_FACT = "UPDATE_FACT"
    ATTACH_SOURCE = "ATTACH_SOURCE"
    MARK_STALE = "MARK_STALE"
    PROPOSE_EDIT = "PROPOSE_EDIT"
    REPOINT_CITATION = "REPOINT_CITATION"


# --------------------------------------------------------------------------- Operations
class DerivedRule(BaseModel):
    from_key: str
    rule: str = "x10"


class Operation(BaseModel):
    op_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    op_type: OpType
    key: str | None = None
    expected_version: int | None = None
    new_value: Any | None = None
    unit: str | None = None
    derived: DerivedRule | None = None
    fact_id: str | None = None
    source_id: str | None = None
    node_id: str | None = None
    reason: str | None = None
    doc_id: str | None = None
    before: str | None = None
    after: str | None = None
    old_fact_id: str | None = None
    new_fact_id: str | None = None


# --------------------------------------------------------------------------- Proposed Edits
class ProposedEdit(BaseModel):
    id: str = Field(default_factory=lambda: f"edit_{uuid.uuid4().hex[:8]}")
    doc_id: str
    before: str
    after: str
    status: str = "PROPOSED"
    author: str = "TruthBranch Agent"
    created_at: str = Field(default_factory=utc_now_iso)


# --------------------------------------------------------------------------- Audit Event
class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    cr_id: str
    event_type: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now_iso)


# --------------------------------------------------------------------------- Quality Check Results
class CheckResult(BaseModel):
    code: CheckCode
    severity: CheckSeverity
    passed: bool
    message: str
    evidence: list[Any] = Field(default_factory=list)


# --------------------------------------------------------------------------- Change Request
class ChangeRequestCreate(BaseModel):
    title: str
    fact_key: str
    new_value: Any
    source_id: str | None = None
    created_by: str = "user"


class ChangeRequest(BaseModel):
    id: str
    title: str
    fact_key: str
    new_value: Any
    source_id: str | None = None
    status: CRStatus = CRStatus.DRAFT
    branch_graph: str
    base_revision: int = 1
    ops: list[Operation] = Field(default_factory=list)
    created_by: str = "user"
    created_at: str = Field(default_factory=utc_now_iso)
    approved_by: str | None = None
    merged_at: str | None = None
    rejected_reason: str | None = None


# --------------------------------------------------------------------------- State Machine
LEGAL_TRANSITIONS: dict[CRStatus, set[CRStatus]] = {
    CRStatus.DRAFT: {CRStatus.BLOCKED, CRStatus.CHECKS_PASSED},
    CRStatus.BLOCKED: {CRStatus.BLOCKED, CRStatus.CHECKS_PASSED, CRStatus.REJECTED},
    CRStatus.CHECKS_PASSED: {CRStatus.BLOCKED, CRStatus.READY_FOR_REVIEW, CRStatus.REJECTED},
    CRStatus.READY_FOR_REVIEW: {CRStatus.APPROVED, CRStatus.REJECTED, CRStatus.BLOCKED},
    CRStatus.APPROVED: {CRStatus.MERGED, CRStatus.CONFLICT},
    CRStatus.MERGED: set(),
    CRStatus.REJECTED: set(),
    CRStatus.CONFLICT: set(),
}


def can_transition(current: CRStatus, target: CRStatus) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, set())


def transition(cr: ChangeRequest, target: CRStatus, reason: str | None = None) -> ChangeRequest:
    """Validate and transition change request status."""
    if not can_transition(cr.status, target):
        raise ValueError(
            f"Illegal state transition from {cr.status.value} to {target.value}. "
            f"Legal targets: {[s.value for s in LEGAL_TRANSITIONS.get(cr.status, set())]}"
        )
    cr.status = target
    if reason and target == CRStatus.REJECTED:
        cr.rejected_reason = reason
    return cr


# --------------------------------------------------------------------------- Dataset Ingestion
class PersonCreate(BaseModel):
    id: str
    name: str
    role: str
    email: str


class SystemCreate(BaseModel):
    id: str
    name: str


class SourceCreate(BaseModel):
    id: str
    title: str
    kind: str
    valid: bool = True
    trust: float = 1.0


class FactCreate(BaseModel):
    id: str
    key: str
    version: int = 1
    subject: str
    attribute: str
    value: Any
    unit: str
    status: str = "ACTIVE"
    created_at: str = Field(default_factory=utc_now_iso)


class DocumentCreate(BaseModel):
    id: str
    title: str
    kind: str
    status: str = "CURRENT"
    last_reviewed: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    content: str


class FactSourcedEdge(BaseModel):
    fact: str
    source: str


class FactOwnedEdge(BaseModel):
    fact: str
    person: str


class FactDerivedEdge(BaseModel):
    fact: str
    from_fact: str
    rule: str = "x10"


class DocCitesEdge(BaseModel):
    doc: str
    fact: str


class DocDerivedEdge(BaseModel):
    doc: str
    from_doc: str


class DocPublishedEdge(BaseModel):
    doc: str
    system: str


class DocOwnedEdge(BaseModel):
    doc: str
    person: str


class DatasetIngestPayload(BaseModel):
    id: str = Field(..., description="Unique dataset identifier slug (e.g. 'fintech')")
    name: str = Field(..., description="Human-readable company name")
    domain: str = Field(default="", description="Industry domain")
    description: str = Field(default="", description="Detailed description")
    people: list[PersonCreate] = Field(default_factory=list)
    systems: list[SystemCreate] = Field(default_factory=list)
    sources: list[SourceCreate] = Field(default_factory=list)
    facts: list[FactCreate] = Field(default_factory=list)
    documents: list[DocumentCreate] = Field(default_factory=list)
    fact_sourced: list[FactSourcedEdge] = Field(default_factory=list)
    fact_owned: list[FactOwnedEdge] = Field(default_factory=list)
    fact_derived: list[FactDerivedEdge] = Field(default_factory=list)
    doc_cites: list[DocCitesEdge] = Field(default_factory=list)
    doc_derived: list[DocDerivedEdge] = Field(default_factory=list)
    doc_published: list[DocPublishedEdge] = Field(default_factory=list)
    doc_owned: list[DocOwnedEdge] = Field(default_factory=list)

    def validate_referential_integrity(self) -> None:
        """Ensure no dangling edges point to non-existent nodes."""
        fact_ids = {f.id for f in self.facts}
        doc_ids = {d.id for d in self.documents}
        person_ids = {p.id for p in self.people}
        source_ids = {s.id for s in self.sources}
        system_ids = {s.id for s in self.systems}

        for edge in self.fact_sourced:
            if edge.fact not in fact_ids:
                raise ValueError(f"Dangling edge: fact '{edge.fact}' in fact_sourced does not exist in facts")
            if edge.source not in source_ids:
                raise ValueError(f"Dangling edge: source '{edge.source}' in fact_sourced does not exist in sources")

        for edge in self.fact_owned:
            if edge.fact not in fact_ids:
                raise ValueError(f"Dangling edge: fact '{edge.fact}' in fact_owned does not exist in facts")
            if edge.person not in person_ids:
                raise ValueError(f"Dangling edge: person '{edge.person}' in fact_owned does not exist in people")

        for edge in self.fact_derived:
            if edge.fact not in fact_ids:
                raise ValueError(f"Dangling edge: fact '{edge.fact}' in fact_derived does not exist in facts")
            if edge.from_fact not in fact_ids:
                raise ValueError(f"Dangling edge: from_fact '{edge.from_fact}' in fact_derived does not exist in facts")

        for edge in self.doc_cites:
            if edge.doc not in doc_ids:
                raise ValueError(f"Dangling edge: doc '{edge.doc}' in doc_cites does not exist in documents")
            if edge.fact not in fact_ids:
                raise ValueError(f"Dangling edge: fact '{edge.fact}' in doc_cites does not exist in facts")

        for edge in self.doc_derived:
            if edge.doc not in doc_ids:
                raise ValueError(f"Dangling edge: doc '{edge.doc}' in doc_derived does not exist in documents")
            if edge.from_doc not in doc_ids:
                raise ValueError(f"Dangling edge: from_doc '{edge.from_doc}' in doc_derived does not exist in documents")

        for edge in self.doc_published:
            if edge.doc not in doc_ids:
                raise ValueError(f"Dangling edge: doc '{edge.doc}' in doc_published does not exist in documents")
            if edge.system not in system_ids:
                raise ValueError(f"Dangling edge: system '{edge.system}' in doc_published does not exist in systems")

        for edge in self.doc_owned:
            if edge.doc not in doc_ids:
                raise ValueError(f"Dangling edge: doc '{edge.doc}' in doc_owned does not exist in documents")
            if edge.person not in person_ids:
                raise ValueError(f"Dangling edge: person '{edge.person}' in doc_owned does not exist in people")


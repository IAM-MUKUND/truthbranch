"""
Unit tests for ChangeRequest state machine and legal/illegal transitions (Checklist 9.2 / Block 2.1).
"""
import pytest
from backend.app.models import (
    ChangeRequest,
    CRStatus,
    transition,
    can_transition,
    LEGAL_TRANSITIONS,
)


def make_cr(status: CRStatus = CRStatus.DRAFT) -> ChangeRequest:
    return ChangeRequest(
        id="cr_test123",
        title="Test CR",
        fact_key="pricing.pro.monthly",
        new_value=59,
        status=status,
        branch_graph="kb_cr_test123",
    )


def test_draft_legal_transitions():
    cr = make_cr(CRStatus.DRAFT)
    assert can_transition(CRStatus.DRAFT, CRStatus.BLOCKED)
    assert can_transition(CRStatus.DRAFT, CRStatus.CHECKS_PASSED)
    assert not can_transition(CRStatus.DRAFT, CRStatus.APPROVED)
    assert not can_transition(CRStatus.DRAFT, CRStatus.MERGED)
    assert not can_transition(CRStatus.DRAFT, CRStatus.READY_FOR_REVIEW)


def test_blocked_transitions():
    cr = make_cr(CRStatus.BLOCKED)
    assert can_transition(CRStatus.BLOCKED, CRStatus.CHECKS_PASSED)
    assert can_transition(CRStatus.BLOCKED, CRStatus.REJECTED)
    assert not can_transition(CRStatus.BLOCKED, CRStatus.APPROVED)
    assert not can_transition(CRStatus.BLOCKED, CRStatus.MERGED)


def test_checks_passed_transitions():
    cr = make_cr(CRStatus.CHECKS_PASSED)
    assert can_transition(CRStatus.CHECKS_PASSED, CRStatus.READY_FOR_REVIEW)
    assert can_transition(CRStatus.CHECKS_PASSED, CRStatus.BLOCKED)
    assert can_transition(CRStatus.CHECKS_PASSED, CRStatus.REJECTED)
    assert not can_transition(CRStatus.CHECKS_PASSED, CRStatus.APPROVED)
    assert not can_transition(CRStatus.CHECKS_PASSED, CRStatus.MERGED)


def test_ready_for_review_transitions():
    cr = make_cr(CRStatus.READY_FOR_REVIEW)
    assert can_transition(CRStatus.READY_FOR_REVIEW, CRStatus.APPROVED)
    assert can_transition(CRStatus.READY_FOR_REVIEW, CRStatus.REJECTED)
    assert can_transition(CRStatus.READY_FOR_REVIEW, CRStatus.BLOCKED)
    assert not can_transition(CRStatus.READY_FOR_REVIEW, CRStatus.MERGED)


def test_approved_transitions():
    cr = make_cr(CRStatus.APPROVED)
    assert can_transition(CRStatus.APPROVED, CRStatus.MERGED)
    assert can_transition(CRStatus.APPROVED, CRStatus.CONFLICT)
    assert not can_transition(CRStatus.APPROVED, CRStatus.READY_FOR_REVIEW)


def test_terminal_states():
    for terminal in (CRStatus.MERGED, CRStatus.REJECTED, CRStatus.CONFLICT):
        assert len(LEGAL_TRANSITIONS[terminal]) == 0
        cr = make_cr(terminal)
        with pytest.raises(ValueError, match="Illegal state transition"):
            transition(cr, CRStatus.DRAFT)


def test_transition_helper_modifies_status():
    cr = make_cr(CRStatus.DRAFT)
    transition(cr, CRStatus.CHECKS_PASSED)
    assert cr.status == CRStatus.CHECKS_PASSED
    transition(cr, CRStatus.READY_FOR_REVIEW)
    assert cr.status == CRStatus.READY_FOR_REVIEW
    transition(cr, CRStatus.APPROVED)
    assert cr.status == CRStatus.APPROVED
    transition(cr, CRStatus.MERGED)
    assert cr.status == CRStatus.MERGED


def test_reject_records_reason():
    cr = make_cr(CRStatus.READY_FOR_REVIEW)
    transition(cr, CRStatus.REJECTED, reason="Executive denied price hike")
    assert cr.status == CRStatus.REJECTED
    assert cr.rejected_reason == "Executive denied price hike"

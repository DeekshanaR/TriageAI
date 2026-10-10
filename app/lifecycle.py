"""Ticket lifecycle state machine: defines which status changes are legal."""

ALLOWED_TRANSITIONS = {
    "NEW": {"TRIAGED", "CANCELLED"},
    "TRIAGED": {"ASSIGNED", "CANCELLED"},
    "ASSIGNED": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"RESOLVED", "ASSIGNED"},
    "RESOLVED": {"CLOSED", "IN_PROGRESS"},
    "CLOSED": set(),
    "CANCELLED": set(),
}

STATUSES = list(ALLOWED_TRANSITIONS)


class InvalidTransition(ValueError):
    """Raised when a ticket is moved to a status it cannot reach."""


def can_transition(current: str, new: str) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, set())


def validate_transition(current: str, new: str) -> None:
    if new not in ALLOWED_TRANSITIONS:
        raise InvalidTransition(f"Unknown status '{new}'. Valid: {STATUSES}")
    if not can_transition(current, new):
        allowed = sorted(ALLOWED_TRANSITIONS.get(current, set())) or "none (final state)"
        raise InvalidTransition(f"Cannot move {current} -> {new}. Allowed: {allowed}")

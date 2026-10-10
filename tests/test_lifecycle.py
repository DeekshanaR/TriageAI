import pytest

from app.lifecycle import InvalidTransition, can_transition, validate_transition


def test_valid_path():
    path = ["NEW", "TRIAGED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]
    for a, b in zip(path, path[1:]):
        assert can_transition(a, b)


def test_cannot_skip_states():
    with pytest.raises(InvalidTransition):
        validate_transition("NEW", "RESOLVED")


def test_final_states_are_final():
    with pytest.raises(InvalidTransition):
        validate_transition("CLOSED", "IN_PROGRESS")


def test_unknown_status():
    with pytest.raises(InvalidTransition):
        validate_transition("NEW", "BANANA")

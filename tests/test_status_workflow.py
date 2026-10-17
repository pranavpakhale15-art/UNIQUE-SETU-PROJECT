from app.api.v1.applications import STATUSES, TRANSITIONS

def test_all_transitions_reference_known_statuses():
    assert set(TRANSITIONS.keys()) == STATUSES
    for current, targets in TRANSITIONS.items():
        assert targets <= STATUSES
        assert current not in targets

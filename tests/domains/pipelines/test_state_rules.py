import pytest

from app.domains.pipelines.rules.state_rules import InvalidStateTransition, assert_transition
from app.models.enums import NodeRunStatus


def test_pending_to_running_ok():
    assert_transition(NodeRunStatus.PENDING, NodeRunStatus.RUNNING)


def test_pending_to_succeeded_rejected():
    with pytest.raises(InvalidStateTransition):
        assert_transition(NodeRunStatus.PENDING, NodeRunStatus.SUCCEEDED)

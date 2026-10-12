"""NodeRun 상태 전이 규칙을 검증하는 순수 함수. DB를 모른다."""
from app.models.enums import NodeRunStatus

_ALLOWED: dict[NodeRunStatus, set[NodeRunStatus]] = {
    NodeRunStatus.PENDING: {NodeRunStatus.RUNNING},
    NodeRunStatus.RUNNING: {NodeRunStatus.SUCCEEDED, NodeRunStatus.FAILED},
}


class InvalidStateTransition(Exception):
    pass


def assert_transition(current: NodeRunStatus, new: NodeRunStatus) -> None:
    if new not in _ALLOWED.get(current, set()):
        raise InvalidStateTransition(f"{current} -> {new}")

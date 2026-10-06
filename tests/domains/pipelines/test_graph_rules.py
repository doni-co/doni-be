"""DB 없이 돌아가는 순수 로직 테스트. service._has_cycle을 직접 검증한다."""
from app.domains.pipelines.service import _has_cycle


def test_no_cycle():
    assert _has_cycle({1, 2, 3}, [(1, 2), (2, 3)]) is False


def test_cycle_detected():
    assert _has_cycle({1, 2, 3}, [(1, 2), (2, 3), (3, 1)]) is True

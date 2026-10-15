"""DB 없이 돌아가는 순수 로직 테스트. service._has_cycle을 직접 검증한다."""
import pytest

from app.domains.pipelines.rules.graph_rules import PipelineValidationError, has_cycle, validate_new_edge


def test_no_cycle():
    assert has_cycle({1, 2, 3}, [(1, 2), (2, 3)]) is False


def test_cycle_detected():
    assert has_cycle({1, 2, 3}, [(1, 2), (2, 3), (3, 1)]) is True


def test_validate_new_edge_rejects_cycle():
    with pytest.raises(PipelineValidationError):
        validate_new_edge({1, 2}, [(1, 2)], (2, 1))


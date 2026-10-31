
import pytest

from app.verification import _coverage_status,_completeness_status


@pytest.mark.parametrize(
    ("expected", "missing", "status"),
    [
        (10, 0, "PASS"),
        (10, 1, "FAIL"),
        (10, 10, "FAIL"),
        (0, 0, "INFO"),
    ],
)
def test_coverage_status(expected, missing, status):
    assert _coverage_status(expected, missing) == status

@pytest.mark.parametrize(
    ("total", "missing", "status"),
    [
        (10, 0, "PASS"),
        (10, 1, "INFO"),
        (10, 10, "INFO"),
        (0, 0, "INFO"),
    ],
)
def test_completeness_status(total, missing, status):
    assert _completeness_status(total, missing) == status
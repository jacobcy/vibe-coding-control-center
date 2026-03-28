"""Tests for DependencyChecker."""

from unittest.mock import MagicMock, patch

from vibe3.orchestra.dependency_checker import DependencyChecker, parse_blocked_by

# --- parse_blocked_by ---


def test_parse_blocked_by_simple():
    body = "This issue is blocked by #42"
    assert parse_blocked_by(body) == [42]


def test_parse_blocked_by_depends_on():
    body = "depends on #100 to be merged first"
    assert parse_blocked_by(body) == [100]


def test_parse_blocked_by_requires():
    body = "Requires #7 and requires #8"
    assert parse_blocked_by(body) == [7, 8]


def test_parse_blocked_by_hyphenated():
    body = "blocked-by: #55"
    assert parse_blocked_by(body) == [55]


def test_parse_blocked_by_none():
    body = "No dependencies here, just a plain description."
    assert parse_blocked_by(body) == []


def test_parse_blocked_by_case_insensitive():
    body = "BLOCKED BY #99"
    assert parse_blocked_by(body) == [99]


def test_parse_blocked_by_deduplicates():
    body = "blocked by #10 and also blocked by #10"
    assert parse_blocked_by(body) == [10]


def test_parse_blocked_by_multiple():
    body = "Blocked by #3. Also depends on #5."
    assert parse_blocked_by(body) == [3, 5]


# --- DependencyChecker.is_closed ---


def _make_checker() -> DependencyChecker:
    return DependencyChecker(repo=None)


def test_is_closed_returns_true_for_closed_issue():
    checker = _make_checker()
    mock_result = MagicMock(returncode=0, stdout='{"state":"CLOSED"}')
    with patch("subprocess.run", return_value=mock_result):
        assert checker.is_closed(42) is True


def test_is_closed_returns_false_for_open_issue():
    checker = _make_checker()
    mock_result = MagicMock(returncode=0, stdout='{"state":"OPEN"}')
    with patch("subprocess.run", return_value=mock_result):
        assert checker.is_closed(42) is False


def test_is_closed_returns_false_on_gh_error():
    checker = _make_checker()
    mock_result = MagicMock(returncode=1, stderr="Not found", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        assert checker.is_closed(999) is False


# --- DependencyChecker.all_resolved ---


def test_all_resolved_empty_list():
    checker = _make_checker()
    assert checker.all_resolved([]) is True


def test_all_resolved_all_closed():
    checker = _make_checker()
    with patch.object(checker, "is_closed", return_value=True):
        assert checker.all_resolved([1, 2, 3]) is True


def test_all_resolved_one_open():
    checker = _make_checker()
    responses = {1: True, 2: False, 3: True}
    with patch.object(checker, "is_closed", side_effect=lambda n: responses[n]):
        assert checker.all_resolved([1, 2, 3]) is False


# --- DependencyChecker.check ---


def test_check_no_blockers():
    checker = _make_checker()
    with patch.object(checker, "fetch_body", return_value="No dependencies"):
        resolved, blockers = checker.check(10)
    assert resolved is True
    assert blockers == []


def test_check_all_blockers_closed():
    checker = _make_checker()
    with patch.object(checker, "fetch_body", return_value="blocked by #5"):
        with patch.object(checker, "is_closed", return_value=True):
            resolved, blockers = checker.check(10)
    assert resolved is True
    assert blockers == [5]


def test_check_blocker_still_open():
    checker = _make_checker()
    with patch.object(checker, "fetch_body", return_value="depends on #7"):
        with patch.object(checker, "is_closed", return_value=False):
            resolved, blockers = checker.check(10)
    assert resolved is False
    assert blockers == [7]

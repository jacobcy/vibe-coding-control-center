# tests/vibe3/test_exceptions.py
from vibe3.exceptions import InvalidBranchLinkError, SystemError


def test_invalid_branch_link_error_has_error_code() -> None:
    error = InvalidBranchLinkError("Invalid branch 'main' linked to issue #123")
    assert error.error_code == "E_INVALID_BRANCH_LINK"
    assert "main" in str(error)
    assert "#123" in str(error)


def test_invalid_branch_link_error_inheritance() -> None:
    error = InvalidBranchLinkError("test")
    assert isinstance(error, SystemError)

"""Tests that check --all and --fix-all cover blocked flows."""

from unittest.mock import MagicMock

from vibe3.commands.check_support import execute_check_mode


def test_check_all_includes_blocked_status():
    """check --all must query blocked flows, not just active."""
    svc = MagicMock()
    svc.verify_all_flows.return_value = []

    execute_check_mode(service=svc, mode="all", show_progress=False)

    # "blocked" must appear in verify_all_flows status argument
    call_args = svc.verify_all_flows.call_args
    assert call_args is not None, "verify_all_flows was never called"

    status = call_args[1].get("status", call_args[0][0] if call_args[0] else None)
    assert "blocked" in status or (
        isinstance(status, list) and "blocked" in status
    ), f"'blocked' not in verify_all_flows call.status={status}"


def test_check_fix_all_includes_blocked_status():
    """check --fix-all must query blocked flows, not just active+stale."""
    svc = MagicMock()
    svc.verify_all_flows.return_value = []

    execute_check_mode(service=svc, mode="fix_all", show_progress=False)

    call_args = svc.verify_all_flows.call_args
    assert call_args is not None, "verify_all_flows was never called"

    status = call_args[1].get("status", call_args[0][0] if call_args[0] else None)
    assert (
        isinstance(status, list) and "blocked" in status
    ), f"'blocked' not in fix_all verify_all_flows call.status={status}"

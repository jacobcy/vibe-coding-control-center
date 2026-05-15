"""Tests for check_cleanup_service with live session filtering."""

from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.check_cleanup_service import (
    CheckCleanupService,
    LiveSessionQueryError,
)


def test_clean_residual_branches_filters_live_sessions_before_cleanup() -> None:
    """Live session branches should be skipped before cleanup attempts."""
    store = MagicMock()
    git_client = MagicMock()

    # Mock terminal flows
    store.get_all_flows.return_value = [
        {
            "branch": "task/issue-123",
            "flow_status": "aborted",
        },
        {
            "branch": "task/issue-456",
            "flow_status": "done",
        },
        {
            "branch": "task/issue-789",
            "flow_status": "aborted",
        },
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock: issue-123 and issue-789 have live sessions
    with patch.object(
        service,
        "_get_branches_with_live_sessions",
        return_value={"task/issue-123", "task/issue-789"},
    ):
        with patch.object(service, "_process_terminal_flow") as mock_process:
            result = service.clean_residual_branches()

            # Verify: only issue-456 was processed (no live session)
            assert mock_process.call_count == 1
            mock_process.assert_called_once()

            # Verify result structure
            assert "skipped_live" in result
            skipped_live = cast(list[str], result["skipped_live"])
            assert set(skipped_live) == {
                "task/issue-123",
                "task/issue-789",
            }
            assert "task/issue-456" not in skipped_live


def test_clean_residual_branches_logs_skipped_branches() -> None:
    """Should log which branches were skipped due to live sessions."""
    store = MagicMock()
    git_client = MagicMock()

    store.get_all_flows.return_value = [
        {"branch": "task/issue-123", "flow_status": "aborted"},
        {"branch": "task/issue-456", "flow_status": "aborted"},
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    with (
        patch("vibe3.agents.backends.codeagent.CodeagentBackend"),
        patch("vibe3.environment.session_registry.SessionRegistryService") as registry,
    ):
        registry.return_value._store.list_live_runtime_sessions.return_value = [
            {
                "branch": "task/issue-123",
                "tmux_session": "vibe3-run-issue-123",
            },
        ]

        # Mock backend to say issue-123 has live session
        with patch.object(service, "_get_branches_with_live_sessions") as mock_get_live:
            mock_get_live.return_value = {"task/issue-123"}

            with patch.object(service, "_process_terminal_flow"):
                result = service.clean_residual_branches()

                # Verify summary includes skipped count
                assert "skipped 1 branches with live sessions" in str(result["summary"])


def test_get_branches_with_live_sessions_queries_once() -> None:
    """Should query live sessions only once, not per branch."""
    store = MagicMock()
    git_client = MagicMock()
    service = CheckCleanupService(store=store, git_client=git_client)

    with (
        patch("vibe3.agents.backends.codeagent.CodeagentBackend"),
        patch(
            "vibe3.environment.session_registry.SessionRegistryService"
        ) as registry_cls,
    ):
        registry = registry_cls.return_value
        # Mock the new method
        registry.get_all_branches_with_live_sessions.return_value = {
            "task/issue-123",
            "task/issue-456",
        }

        result = service._get_branches_with_live_sessions()

        # Verify: called once, not per branch
        registry.get_all_branches_with_live_sessions.assert_called_once()

        # Verify: both branches returned
        assert result == {"task/issue-123", "task/issue-456"}


def test_clean_residual_branches_handles_no_live_sessions() -> None:
    """Should work correctly when no live sessions exist."""
    store = MagicMock()
    git_client = MagicMock()

    store.get_all_flows.return_value = [
        {"branch": "task/issue-123", "flow_status": "aborted"},
        {"branch": "task/issue-456", "flow_status": "done"},
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock: no live sessions
    with patch.object(service, "_get_branches_with_live_sessions", return_value=set()):
        with patch.object(service, "_process_terminal_flow") as mock_process:
            result = service.clean_residual_branches()

            # All flows should be processed
            assert mock_process.call_count == 2
            assert result["skipped_live"] == []


def test_clean_residual_branches_raises_on_live_session_query_failure() -> None:
    """Should raise LiveSessionQueryError when batch query fails (fail-fast)."""
    store = MagicMock()
    git_client = MagicMock()

    store.get_all_flows.return_value = [
        {"branch": "task/issue-123", "flow_status": "aborted"},
    ]

    service = CheckCleanupService(store=store, git_client=git_client)

    # Mock: batch query raises exception (simulates SessionRegistryService failure)
    with patch.object(
        service,
        "_get_branches_with_live_sessions",
        side_effect=LiveSessionQueryError("Query failed"),
    ):
        with pytest.raises(LiveSessionQueryError, match="Query failed"):
            service.clean_residual_branches()


def test_session_registry_injection() -> None:
    """Should use injected SessionRegistryService instead of lazy init."""
    store = MagicMock()
    git_client = MagicMock()
    mock_registry = MagicMock()

    # Inject mock registry
    service = CheckCleanupService(
        store=store,
        git_client=git_client,
        session_registry=mock_registry,
    )

    # Mock: return some live sessions
    mock_registry.get_all_branches_with_live_sessions.return_value = {"task/issue-123"}

    result = service._get_branches_with_live_sessions()

    # Verify: injected registry was called
    mock_registry.get_all_branches_with_live_sessions.assert_called_once()
    assert result == {"task/issue-123"}


def test_session_registry_lazy_initialization() -> None:
    """Should lazy-initialize SessionRegistryService when not injected."""
    store = MagicMock()
    git_client = MagicMock()

    # No injection
    service = CheckCleanupService(store=store, git_client=git_client)

    with (
        patch("vibe3.agents.backends.codeagent.CodeagentBackend") as mock_backend,
        patch(
            "vibe3.environment.session_registry.SessionRegistryService"
        ) as mock_registry_cls,
    ):
        mock_registry_instance = MagicMock()
        mock_registry_cls.return_value = mock_registry_instance
        mock_registry_instance.get_all_branches_with_live_sessions.return_value = set()

        # Access the property
        registry = service.session_registry

        # Verify: backend and registry were created
        mock_backend.assert_called_once()
        mock_registry_cls.assert_called_once_with(
            store=store, backend=mock_backend.return_value
        )
        assert registry == mock_registry_instance

"""Regression tests for #3184: no-op block survives auto recovery and rebuild."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibe3.models import IssueState


class TestNoOpBlockSurvivesAutoRecovery:
    """Tests that no-op block with durable reason survives auto recovery and rebuild."""

    def test_no_op_block_survives_health_check(self) -> None:
        """No-op block with human reason survives health-check unchanged."""
        # This test verifies that a blocked flow with a human reason
        # is NOT auto-cleared by health-check reconciliation
        with patch(
            "vibe3.services.flow.blocked_state_service.BlockedStateIO"
        ) as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock GitHub body with human reason
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked reason**: Waiting for external dependency review

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            from vibe3.services.flow.blocked_state_service import BlockedStateService

            service = BlockedStateService(
                github_client=MagicMock(),
                store=MagicMock(),
            )

            # Call sync_blocked_state (used by health check)
            result = service.sync_blocked_state(
                issue_number=123,
                branch="task/issue-123",
                actor="check:blocked_label_sync",
            )

            # Should return None (no state inference)
            assert result is None
            # Should NOT write a new projection (no mutation)
            # The service should only sync label to blocked, not clear reason
            assert mock_io.write_projection.call_count == 0

    def test_auto_rebuild_preserves_blocked_state(self) -> None:
        """Auto rebuild preserves blocked state by not having clearance logic."""
        # This test verifies that FlowRebuildUsecase does NOT have _default_label_resume
        from vibe3.services.flow.rebuild import FlowRebuildUsecase

        # Verify the method was removed
        assert not hasattr(FlowRebuildUsecase, "_default_label_resume")

        # Verify label_resume parameter was removed from __init__
        import inspect

        sig = inspect.signature(FlowRebuildUsecase.__init__)
        params = list(sig.parameters.keys())
        assert "label_resume" not in params

    def test_scene_rebuild_does_not_claim_cleared_markers(self) -> None:
        """Scene rebuild does not claim 'cleared blocked markers'."""
        # This test verifies that rebuild detail message does not falsely claim
        # that blocked markers were cleared
        from vibe3.services.flow.recovery import FlowRecoveryService

        with patch.object(FlowRecoveryService, "_do_rebuild") as mock_rebuild:
            with patch.object(FlowRecoveryService, "_do_resume") as mock_resume:
                mock_store = MagicMock()
                mock_store.get_flow_state.return_value = None  # No flow record

                service = FlowRecoveryService(
                    store=mock_store,
                    git_client=MagicMock(),
                    github_client=MagicMock(),
                )

                result = service.recover(
                    branch="task/issue-123",
                    issue_number=123,
                    reason="Health check auto-recover",
                )

                # Verify the detail does NOT claim "cleared blocked markers"
                # Now it should say "synced blocked state" instead
                if result.success:
                    assert "cleared blocked markers" not in result.detail.lower()
                    assert "synced blocked state" in result.detail.lower()


class TestAutoRebuildPreservesBlockedReason:
    """Tests that auto rebuild never clears blocked_reason."""

    def test_rebuild_does_not_call_reconcile_blocked(self) -> None:
        """FlowRebuildUsecase does not call reconcile_blocked or _default_label_resume."""
        # Verify that the _default_label_resume method was removed
        from vibe3.services.flow.rebuild import FlowRebuildUsecase

        # Verify method does not exist
        assert not hasattr(FlowRebuildUsecase, "_default_label_resume")

        # Verify label_resume is not in __init__ signature
        import inspect

        sig = inspect.signature(FlowRebuildUsecase.__init__)
        params = list(sig.parameters.keys())
        assert "label_resume" not in params

    def test_blocked_state_service_has_no_auto_clear_path(self) -> None:
        """BlockedStateService.sync_blocked_state does not clear blocked_reason."""
        with patch(
            "vibe3.services.flow.blocked_state_service.BlockedStateIO"
        ) as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock GitHub body with human reason and no dependencies
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked reason**: Human review required

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            from vibe3.services.flow.blocked_state_service import BlockedStateService

            service = BlockedStateService(
                github_client=MagicMock(),
                store=MagicMock(),
            )

            # Call sync_blocked_state
            result = service.sync_blocked_state(
                issue_number=123,
                branch="task/issue-123",
                actor="check:blocked_label_sync",
            )

            # Should return None (no state inference, no unblock)
            assert result is None

            # Should NOT write projection with cleared reason
            # The sync should only ensure label matches blocked state
            if mock_io.write_projection.called:
                # If called, verify it doesn't clear the reason
                call_args = mock_io.write_projection.call_args
                if call_args:
                    projection = call_args[0][1]
                    # Should preserve the human reason
                    assert projection.blocked_reason == "Human review required"


class TestManualResumeVsAutoRebuild:
    """Tests verifying manual resume vs auto rebuild separation."""

    def test_manual_resume_api_requires_explicit_authorization(self) -> None:
        """manual_resume API requires actor and reason parameters."""
        import inspect

        from vibe3.services.flow.resume_api import manual_resume

        sig = inspect.signature(manual_resume)
        params = list(sig.parameters.keys())

        # Verify required params
        assert "actor" in params
        assert "reason" in params

    def test_auto_resume_api_has_no_authorization_params(self) -> None:
        """evaluate_auto_resume and apply_auto_resume have no actor/reason params."""
        import inspect

        from vibe3.services.flow.resume_api import (
            apply_auto_resume,
            evaluate_auto_resume,
        )

        # evaluate_auto_resume
        eval_sig = inspect.signature(evaluate_auto_resume)
        eval_params = list(eval_sig.parameters.keys())
        assert "actor" not in eval_params
        assert "reason" not in eval_params

        # apply_auto_resume
        apply_sig = inspect.signature(apply_auto_resume)
        apply_params = list(apply_sig.parameters.keys())
        assert "actor" not in apply_params
        assert "reason" not in apply_params

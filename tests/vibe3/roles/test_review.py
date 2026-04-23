"""Tests for reviewer role audit artifact helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.roles.review import _create_minimal_audit_artifact


class TestReviewerFailed:
    """场景 1: reviewer 执行报错 → state/failed"""

    def test_reviewer_failed_calls_fail_reviewer_issue(
        self,
    ) -> None:
        """Reviewer 执行报错 → 调用 fail_reviewer_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import fail_reviewer_issue

            fail_reviewer_issue(
                issue_number=300,
                reason="review execution crashed",
                actor="agent:review",
            )

            # Verify: _ensure_flow_state_for_issue called with "fail" action
            mock_ensure.assert_called_once_with(
                300,
                "fail",  # ← action 参数
                "review execution crashed",  # ← reason
                "agent:review",  # ← actor
            )


class TestReviewerBlockedNoAuditRef:
    """场景 2: reviewer 无行动 → state/blocked"""

    def test_reviewer_blocked_no_audit_ref_calls_block_reviewer(
        self,
    ) -> None:
        """Reviewer 无行动 → 调用 block_reviewer_noop_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_reviewer_noop_issue

            block_reviewer_noop_issue(
                issue_number=301,
                repo="jacobcy/vibe-coding-control-center",
                reason="state unchanged",
                actor="agent:review",
            )

            # Verify: _ensure_flow_state_for_issue called with "block" action
            mock_ensure.assert_called_once_with(
                301,
                "block",  # ← action 参数
                "state unchanged",  # ← reason
                "agent:review",  # ← actor
            )


class TestReviewerBlockedNoStateChange:
    """场景 3: reviewer 有产出但无推进 → state/blocked"""

    def test_reviewer_blocked_no_state_change_calls_block_reviewer(
        self,
    ) -> None:
        """Reviewer 有 audit_ref 但 state 未变 → block"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_reviewer_noop_issue

            block_reviewer_noop_issue(
                issue_number=302,
                repo="jacobcy/vibe-coding-control-center",
                reason="no state change",
                actor="agent:review",
            )

            # Verify: block reason
            mock_ensure.assert_called_once_with(
                302,
                "block",
                "no state change",  # ← reason
                "agent:review",
            )


class TestReviewerNoOpGate:
    """场景 4: reviewer state 未变 → blocked"""

    def test_reviewer_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Reviewer state/review 未变 → blocked"""
        from unittest.mock import patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/review"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=303,
                branch="task/issue-303",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
            )

        mock_block.assert_called_once()

    def test_reviewer_pass_when_state_changed(
        self,
    ) -> None:
        """Reviewer state/review → state/handoff → pass"""
        from unittest.mock import patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/handoff"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=303,
                branch="task/issue-303",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
            )

        mock_block.assert_not_called()


def test_create_minimal_audit_artifact_prefers_worktree_reports_dir(
    tmp_path: Path,
) -> None:
    with patch("vibe3.roles.review.GitClient") as mock_git_cls:
        mock_git = mock_git_cls.return_value
        mock_git.get_worktree_root.return_value = None
        mock_git.find_worktree_path_for_branch.return_value = tmp_path
        artifact_path = _create_minimal_audit_artifact(
            "LGTM - The implementation looks good",
            "UNKNOWN",
            "task/issue-340",
        )

    assert artifact_path.parent == tmp_path / "docs" / "reports"
    assert artifact_path.name.startswith("task-issue-340-audit-auto-")
    assert artifact_path.read_text(encoding="utf-8").startswith(
        "# Minimal Review Audit"
    )


class TestFinalizeReviewOutputVerdictSource:
    """回归测试: finalize_review_output 在不同 audit 来源下正确选择 verdict 来源。

    核心断言:
    - reviewer 主动写了 handoff_audit → verdict 从 audit 文件读取（不跟 stdout 走）
    - 系统 auto-generated audit → verdict 从 stdout 读取（等价于 audit 内容）
    - audit 文件存在但不可读 → fallback 到 stdout
    """

    def _make_mock_handoff_service(self) -> MagicMock:
        svc = MagicMock()
        svc.record_audit.return_value = Path("/tmp/current.md")
        return svc

    @patch("vibe3.roles.review.HandoffService")
    @patch("vibe3.roles.review._load_existing_audit_ref")
    def test_reviewer_written_audit_overrides_stdout_verdict(
        self,
        mock_load_audit_ref: MagicMock,
        mock_handoff_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """当 reviewer 主动执行 `handoff audit`，audit 文件内容与 stdout 不一致时，
        finalize_review_output 必须以 audit 文件为权威来源，不受 stdout 影响。"""
        from vibe3.roles.review import finalize_review_output

        # reviewer stdout 说 PASS，但主动写的 audit 文件说 BLOCK
        stdout_output = "The implementation looks good\nVERDICT: PASS"
        audit_file = tmp_path / "issue-42-review-audit.md"
        audit_file.write_text(
            "# Authoritative Audit\n\n## Verdict\nVERDICT: BLOCK\n\n"
            "## Findings\n- Critical security issue found\n",
            encoding="utf-8",
        )

        # Simulate: reviewer ran `handoff audit <path>`
        # -> audit_ref already in flow state
        mock_load_audit_ref.return_value = str(audit_file)
        mock_handoff_svc = self._make_mock_handoff_service()
        mock_handoff_cls.return_value = mock_handoff_svc

        audit_ref, verdict = finalize_review_output(
            review_output=stdout_output,
            branch="task/issue-42",
            actor="claude/claude-sonnet-4-6",
        )

        # Verdict MUST come from the audit file (BLOCK), NOT stdout (PASS)
        assert verdict == "BLOCK", (
            f"Expected BLOCK from audit file, got {verdict!r}. "
            "finalize_review_output must prefer reviewer-written audit over stdout."
        )
        assert audit_ref == str(audit_file)
        # HandoffService.record_audit called with BLOCK
        mock_handoff_svc.record_audit.assert_called_once_with(
            audit_ref=str(audit_file),
            actor="claude/claude-sonnet-4-6",
            verdict="BLOCK",
            is_system_auto=False,
        )

    @patch("vibe3.roles.review.HandoffService")
    @patch("vibe3.roles.review._load_existing_audit_ref")
    def test_system_auto_audit_uses_stdout_verdict(
        self,
        mock_load_audit_ref: MagicMock,
        mock_handoff_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """当没有 reviewer-written audit（系统 auto 路径），
        verdict 来自 stdout（等价于 audit）。"""
        from vibe3.roles.review import finalize_review_output

        stdout_output = "All checks pass\nVERDICT: PASS"

        # No reviewer-written audit → system will create minimal audit from stdout
        mock_load_audit_ref.return_value = None

        mock_handoff_svc = self._make_mock_handoff_service()
        # record_audit returns a path (system auto creates it)
        auto_audit = tmp_path / "auto-audit.md"
        auto_audit.write_text("# Minimal Review Audit\nVERDICT: PASS\n")
        mock_handoff_svc.record_audit.return_value = auto_audit
        mock_handoff_cls.return_value = mock_handoff_svc

        with patch(
            "vibe3.roles.review._create_minimal_audit_artifact",
            return_value=auto_audit,
        ):
            _, verdict = finalize_review_output(
                review_output=stdout_output,
                branch="task/issue-42",
                actor="claude/claude-sonnet-4-6",
            )

        # System auto path: verdict comes from stdout
        assert verdict == "PASS"
        mock_handoff_svc.record_audit.assert_called_once_with(
            audit_ref=str(auto_audit),
            actor="claude/claude-sonnet-4-6",
            verdict="PASS",
            is_system_auto=True,
        )

    @patch("vibe3.roles.review.HandoffService")
    @patch("vibe3.roles.review._load_existing_audit_ref")
    def test_reviewer_written_audit_unreadable_falls_back_to_stdout(
        self,
        mock_load_audit_ref: MagicMock,
        mock_handoff_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """即使 reviewer 写了 handoff_audit，但 audit 文件不可读，
        应 fallback 到 stdout 而非崩溃。"""
        from vibe3.roles.review import finalize_review_output

        stdout_output = "Partial review\nVERDICT: MAJOR"
        # Point to a file that does not exist
        non_existent_audit = tmp_path / "missing-audit.md"
        mock_load_audit_ref.return_value = str(non_existent_audit)
        mock_handoff_svc = self._make_mock_handoff_service()
        mock_handoff_cls.return_value = mock_handoff_svc

        _, verdict = finalize_review_output(
            review_output=stdout_output,
            branch="task/issue-42",
            actor="claude/claude-sonnet-4-6",
        )

        # File missing → fallback to stdout → MAJOR
        assert (
            verdict == "MAJOR"
        ), f"Expected MAJOR fallback from stdout, got {verdict!r}."
        mock_handoff_svc.record_audit.assert_called_once_with(
            audit_ref=str(non_existent_audit),
            actor="claude/claude-sonnet-4-6",
            verdict="MAJOR",
            is_system_auto=False,
        )

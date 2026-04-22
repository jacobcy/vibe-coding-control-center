"""Tests for reviewer role audit artifact helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.roles.review import (
    _create_minimal_audit_artifact,
    _resolve_authoritative_audit_ref,
    _resolve_review_verdict,
)


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


class TestReviewerParserErrorTolerance:
    """场景 5: reviewer 输出格式错误 → audit_ref 仍然写入（容错性）"""

    def test_reviewer_output_written_even_if_parser_fails(
        self,
    ) -> None:
        """即使 parser 失败，audit_ref 也应该写入"""
        # Setup: reviewer 输出 "LGTM"（不符合 VERDICT 格式）

        mock_output = "LGTM - The implementation looks good"
        mock_branch = "task/issue-303"

        # Create audit_ref from raw output
        with patch("vibe3.roles.review._create_minimal_audit_artifact") as mock_create:
            mock_audit_path = Path("/tmp/audit-auto-2026-04-16T12:30:00Z.md")
            mock_create.return_value = mock_audit_path

            audit_ref = _resolve_authoritative_audit_ref(
                handoff_file=None,  # ← 无 handoff file
                review_output=mock_output,  # ← 直接使用原始输出
                verdict="UNKNOWN",  # ← parser 失败，verdict 为空
                branch=mock_branch,
            )

            # Verify: _create_minimal_audit_artifact called
            mock_create.assert_called_once_with(
                mock_output,
                "UNKNOWN",  # ← verdict 标记为 UNKNOWN
                mock_branch,
            )

            # Verify: audit_ref returned
            assert audit_ref == str(mock_audit_path)

    def test_reviewer_verdict_prefers_stdout_over_audit_file(
        self, tmp_path: Path
    ) -> None:
        audit_path = tmp_path / "audit.md"
        audit_path.write_text("VERDICT: BLOCK\n", encoding="utf-8")

        verdict = _resolve_review_verdict(
            review_output="Looks good\nVERDICT: PASS",
            audit_ref=str(audit_path),
        )

        assert verdict == "PASS"

    def test_reviewer_verdict_falls_back_to_audit_file_when_stdout_invalid(
        self, tmp_path: Path
    ) -> None:
        audit_path = tmp_path / "audit.md"
        audit_path.write_text("# Audit\nVERDICT: MAJOR\n", encoding="utf-8")

        verdict = _resolve_review_verdict(
            review_output="LGTM without parseable verdict",
            audit_ref=str(audit_path),
        )

        assert verdict == "MAJOR"

    def test_authoritative_audit_ref_prefers_existing_agent_written_ref(
        self,
    ) -> None:
        with patch("vibe3.roles.review._create_minimal_audit_artifact") as mock_create:
            audit_ref = _resolve_authoritative_audit_ref(
                handoff_file=None,
                review_output="VERDICT: PASS",
                verdict="PASS",
                branch="task/issue-303",
                existing_audit_ref="docs/reports/issue-303-review.md",
            )

        mock_create.assert_not_called()
        assert audit_ref == "docs/reports/issue-303-review.md"

    def test_reviewer_parser_error_does_not_raise_exception(
        self,
    ) -> None:
        """Parser 失败时不应该抛异常，而是 verdict=None"""
        from vibe3.agents.review_parser import ReviewParserError, parse_codex_review

        # Setup: output without VERDICT format
        invalid_output = "LGTM - looks good"

        # Execute: parser should raise ReviewParserError
        with pytest.raises(ReviewParserError):
            parse_codex_review(invalid_output)

        # Expected behavior in actual code:
        # try:
        #     review = parse_codex_review(output)
        #     verdict = review.verdict
        # except ReviewParserError:
        #     verdict = None  # ← 不抛异常，继续写 audit_ref


def test_create_minimal_audit_artifact_prefers_worktree_reports_dir(
    tmp_path: Path,
) -> None:
    with patch("vibe3.roles.review.GitClient") as mock_git_cls:
        mock_git = mock_git_cls.return_value
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

    @patch("vibe3.roles.review.VerdictService")
    @patch("vibe3.roles.review._build_handoff_service")
    @patch("vibe3.roles.review._load_existing_audit_ref")
    def test_reviewer_written_audit_overrides_stdout_verdict(
        self,
        mock_load_audit_ref: MagicMock,
        mock_build_service: MagicMock,
        mock_verdict_cls: MagicMock,
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
        mock_build_service.return_value = self._make_mock_handoff_service()
        mock_verdict_cls.return_value.write_verdict.return_value = MagicMock()

        audit_ref, verdict = finalize_review_output(
            review_output=stdout_output,
            handoff_file=None,
            branch="task/issue-42",
            actor="claude/claude-sonnet-4-6",
        )

        # Verdict MUST come from the audit file (BLOCK), NOT stdout (PASS)
        assert verdict == "BLOCK", (
            f"Expected BLOCK from audit file, got {verdict!r}. "
            "finalize_review_output must prefer reviewer-written audit over stdout."
        )
        assert audit_ref == str(audit_file)
        # VerdictService.write_verdict called with BLOCK
        mock_verdict_cls.return_value.write_verdict.assert_called_once_with(
            verdict="BLOCK",
            branch="task/issue-42",
        )

    @patch("vibe3.roles.review.VerdictService")
    @patch("vibe3.roles.review._build_handoff_service")
    @patch("vibe3.roles.review._load_existing_audit_ref")
    def test_system_auto_audit_uses_stdout_verdict(
        self,
        mock_load_audit_ref: MagicMock,
        mock_build_service: MagicMock,
        mock_verdict_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """当没有 reviewer-written audit（系统 auto 路径），
        verdict 来自 stdout（等价于 audit）。"""
        from vibe3.roles.review import finalize_review_output

        stdout_output = "All checks pass\nVERDICT: PASS"

        # No reviewer-written audit → system will create minimal audit from stdout
        mock_load_audit_ref.return_value = None

        mock_svc = self._make_mock_handoff_service()
        # record_audit returns a path (system auto creates it)
        auto_audit = tmp_path / "auto-audit.md"
        auto_audit.write_text("# Minimal Review Audit\nVERDICT: PASS\n")
        mock_svc.record_audit.return_value = auto_audit
        mock_build_service.return_value = mock_svc
        mock_verdict_cls.return_value.write_verdict.return_value = MagicMock()

        with patch(
            "vibe3.roles.review._create_minimal_audit_artifact",
            return_value=auto_audit,
        ):
            _, verdict = finalize_review_output(
                review_output=stdout_output,
                handoff_file=None,
                branch="task/issue-42",
                actor="claude/claude-sonnet-4-6",
            )

        # System auto path: verdict comes from stdout
        assert verdict == "PASS"

    @patch("vibe3.roles.review.VerdictService")
    @patch("vibe3.roles.review._build_handoff_service")
    @patch("vibe3.roles.review._load_existing_audit_ref")
    def test_reviewer_written_audit_unreadable_falls_back_to_stdout(
        self,
        mock_load_audit_ref: MagicMock,
        mock_build_service: MagicMock,
        mock_verdict_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """即使 reviewer 写了 handoff_audit，但 audit 文件不可读，
        应 fallback 到 stdout 而非崩溃。"""
        from vibe3.roles.review import finalize_review_output

        stdout_output = "Partial review\nVERDICT: MAJOR"
        # Point to a file that does not exist
        non_existent_audit = tmp_path / "missing-audit.md"
        mock_load_audit_ref.return_value = str(non_existent_audit)
        mock_build_service.return_value = self._make_mock_handoff_service()
        mock_verdict_cls.return_value.write_verdict.return_value = MagicMock()

        _, verdict = finalize_review_output(
            review_output=stdout_output,
            handoff_file=None,
            branch="task/issue-42",
            actor="claude/claude-sonnet-4-6",
        )

        # File missing → fallback to stdout → MAJOR
        assert (
            verdict == "MAJOR"
        ), f"Expected MAJOR fallback from stdout, got {verdict!r}."

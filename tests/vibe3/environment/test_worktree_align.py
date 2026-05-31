"""Tests for align_auto_scene_to_base best-effort fetch semantics.

Regression coverage for issue #1729 真因: a best-effort ``git fetch`` failure
must NOT mark an otherwise-valid worktree as unusable. After a reviewer
finishes (verdict recorded) the flow enters HANDOFF and manager is dispatched
to the SAME permanent worktree. A transient fetch failure there used to bubble
up as ``E_DISPATCH_FAILURE: worktree_unavailable`` even though the worktree was
perfectly usable. Only destructive alignment (checkout/reset/clean) on an empty
branch may gate worktree usability.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.environment.worktree_support import align_auto_scene_to_base


def _git_runner(
    *, has_commits: bool = True, fetch_ok: bool = True, destructive_ok: bool = True
):
    """Build a subprocess.run side_effect keyed on the git subcommand."""

    def _run(cmd, **_kwargs):
        sub = cmd[1] if len(cmd) > 1 else ""
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""
        if sub == "log":
            result.returncode = 0 if has_commits else 1
            result.stdout = "abc123 commit\n" if has_commits else ""
        elif sub == "fetch":
            result.returncode = 0 if fetch_ok else 1
            result.stderr = "" if fetch_ok else "fatal: unable to access remote"
        else:  # checkout / reset / clean
            result.returncode = 0 if destructive_ok else 1
            result.stderr = "" if destructive_ok else "error: alignment failed"
        return result

    return _run


CONFIG = MagicMock()
CONFIG.scene_base_ref = "origin/main"
WT = Path("/fake/worktree")
TASK_BRANCH = "task/issue-1678"


class TestAlignBestEffortFetch:
    """Best-effort fetch must not gate worktree usability."""

    def test_fetch_failure_with_existing_commits_returns_true(self):
        """核心回归 (#1729): reviewer 已提交的分支 fetch 失败,worktree 仍可用。"""
        with patch(
            "vibe3.environment.worktree_support.subprocess.run",
            side_effect=_git_runner(has_commits=True, fetch_ok=False),
        ):
            assert align_auto_scene_to_base(CONFIG, WT, TASK_BRANCH) is True

    def test_fetch_success_with_existing_commits_skips_destructive(self):
        """has_commits=True 时不执行 destructive 对齐 (不动 reviewer 的产出)。"""
        with patch(
            "vibe3.environment.worktree_support.subprocess.run",
            side_effect=_git_runner(has_commits=True, fetch_ok=True),
        ) as mock_run:
            assert align_auto_scene_to_base(CONFIG, WT, TASK_BRANCH) is True
        called_subs = [call.args[0][1] for call in mock_run.call_args_list]
        assert "reset" not in called_subs
        assert "clean" not in called_subs

    def test_fetch_failure_empty_branch_still_aligns(self):
        """has_commits=False + fetch 失败,destructive 成功 → True。"""
        with patch(
            "vibe3.environment.worktree_support.subprocess.run",
            side_effect=_git_runner(
                has_commits=False, fetch_ok=False, destructive_ok=True
            ),
        ):
            assert align_auto_scene_to_base(CONFIG, WT, TASK_BRANCH) is True

    def test_destructive_failure_returns_false(self):
        """destructive 对齐失败仍判定不可用 (保护 scene 正确性)。"""
        with patch(
            "vibe3.environment.worktree_support.subprocess.run",
            side_effect=_git_runner(
                has_commits=False, fetch_ok=True, destructive_ok=False
            ),
        ):
            assert align_auto_scene_to_base(CONFIG, WT, TASK_BRANCH) is False

    def test_non_task_branch_returns_true_without_git(self):
        """非 task/issue 分支直接返回 True,不触碰 git。"""
        with patch(
            "vibe3.environment.worktree_support.subprocess.run",
        ) as mock_run:
            assert align_auto_scene_to_base(CONFIG, WT, "dev/issue-1678") is True
        mock_run.assert_not_called()

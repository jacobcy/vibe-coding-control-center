"""Tests for orchestra serve command wiring and toggles."""

from typer.testing import CliRunner

from vibe3.orchestra.config import (
    AssigneeDispatchConfig,
    CommentReplyConfig,
    OrchestraConfig,
    PRReviewDispatchConfig,
)
from vibe3.orchestra.serve import _build_server, app


def test_build_server_registers_only_enabled_services() -> None:
    cfg = OrchestraConfig(
        assignee_dispatch=AssigneeDispatchConfig(enabled=False),
        comment_reply=CommentReplyConfig(enabled=False),
        pr_review_dispatch=PRReviewDispatchConfig(enabled=True),
    )
    heartbeat, _ = _build_server(cfg)
    assert heartbeat.service_names == ["PRReviewDispatchService"]


def test_start_exits_when_orchestra_disabled(monkeypatch) -> None:
    import vibe3.orchestra.serve as serve_module

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(lambda cls: OrchestraConfig(enabled=False)),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["start"])

    assert result.exit_code == 1
    assert "disabled" in result.stdout.lower()

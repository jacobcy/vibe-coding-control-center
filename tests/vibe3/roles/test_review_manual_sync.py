"""Regression tests for manual review sync execution."""

from __future__ import annotations

from vibe3.models import ReviewRequest, ReviewScope
from vibe3.roles.review import ReviewRunResult


def test_execute_manual_review_sync_imports_session_service_from_execution(
    monkeypatch,
) -> None:
    from vibe3.roles import review as review_module

    monkeypatch.setattr(
        "vibe3.execution.session_service.load_session_id",
        lambda _role, branch=None: "session-1",
    )

    captured: dict[str, object] = {}

    class FakeExecutionService:
        def __init__(self, _config: object) -> None:
            pass

        def execute_sync(self, command: object) -> object:
            captured["session_id"] = getattr(command, "session_id")
            return type(
                "Result",
                (),
                {"stdout": "", "success": True, "backend": None, "model": None},
            )()

    monkeypatch.setattr(
        review_module,
        "CodeagentExecutionService",
        FakeExecutionService,
    )
    monkeypatch.setattr(
        review_module,
        "VibeConfig",
        type("FakeConfig", (), {"get_defaults": staticmethod(lambda: object())}),
    )

    result = review_module.execute_manual_review_sync(
        request=ReviewRequest(scope=ReviewScope.for_base("main"), changed_symbols={}),
        dry_run=True,
        instructions="smoke",
        branch="task/issue-2023",
        context_builder=lambda _request, _config, **_: (lambda: "context"),
        agent="reviewer-fast",
        backend="codex",
        model="gpt-5.4",
    )

    assert result == ReviewRunResult("DRY_RUN", None, None, backend=None, model=None)
    assert captured["session_id"] == "session-1"

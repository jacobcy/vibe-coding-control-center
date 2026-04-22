"""Low-level rendering primitives shared across flow UI modules.

这些 primitive 函数被 flow_ui.py 和 flow_ui_timeline.py 共同使用。
提取到独立模块避免两个文件之间的循环依赖（原来 flow_ui_timeline 用
函数体内 lazy import 绕过，属于代码坏味道）。
"""

from rich.text import Text

from vibe3.ui.console import console

_STATUS_COLOR: dict[str, str] = {
    "active": "green",
    "done": "dim",
    "blocked": "red",  # Execution blocked (internal issue, needs manual intervention)
    "waiting": "yellow",  # Waiting for dependencies (external, auto-recoverable)
    "stale": "yellow",
}


def status_text(status: str) -> Text:
    """返回带颜色的状态 Text 对象。"""
    color = _STATUS_COLOR.get(status.lower(), "white")
    return Text(status, style=color)


def kv(key: str, value: object, indent: int = 0) -> None:
    """以 YAML 风格打印键值对。"""
    pad = "  " * indent
    console.print(f"{pad}[dim]{key}:[/] {value}")


def display_actor(actor: str | None) -> tuple[str, bool]:
    """Resolve actor for display.

    Returns (display_value, is_worktree_fallback).
    - If actor is set and normalizes to a meaningful value → (normalized, False)
    - Else → (worktree git user.name, True)

    Uses ``SignatureService.normalize_actor`` which maps legacy aliases and
    filters placeholders, giving consistent output across PR body and UI.
    """
    from vibe3.services.signature_service import SignatureService

    normalized = SignatureService.normalize_actor(actor)
    if normalized is not None:
        return normalized, False

    # Fallback: worktree git user.name
    try:
        from vibe3.clients.git_client import GitClient

        name = GitClient().get_config("user.name") or "unknown"
    except Exception:
        name = "unknown"
    return name, True


def resolve_ref_path(
    ref_value: str | None,
    worktree_root: str | None = None,
    absolute: bool = False,
) -> str:
    """Resolve a reference path for display.

    Redirects to vibe3.utils.path_helpers.resolve_ref_path.
    """
    from vibe3.utils.path_helpers import resolve_ref_path as _resolve

    return _resolve(ref_value, worktree_root, absolute=absolute)

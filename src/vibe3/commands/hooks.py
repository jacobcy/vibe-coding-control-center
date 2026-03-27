"""Hooks command - 管理 Git hooks 的启用与禁用."""

import os
import shutil
import subprocess
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console

from vibe3.exceptions import HookManagerError
from vibe3.services.metrics_service import MetricsError, collect_metrics

_ROOT = Path(__file__).parent.parent.parent.parent
_VALID_HOOKS = ["pre-commit", "pre-push", "commit-msg", "post-commit"]

app = typer.Typer(
    name="hooks",
    help=(
        "Manage Git hooks (enable/disable).\n\n"
        f"Available hooks: {', '.join(_VALID_HOOKS)}\n\n"
        "Examples:\n"
        "  vibe hooks list\n"
        "  vibe hooks enable commit-msg\n"
        "  vibe hooks enable --all\n"
        "  vibe hooks disable pre-push\n"
        "  vibe hooks disable --all"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _get_hooks_dir() -> Path:
    """获取真实的 Git hooks 目录，兼容 worktree 场景."""
    try:
        cwd = _ROOT
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        git_common_dir = Path(result.stdout.strip())
        if not git_common_dir.is_absolute():
            git_common_dir = cwd / git_common_dir
        return git_common_dir / "hooks"
    except subprocess.CalledProcessError:
        return _ROOT / ".git" / "hooks"


def _enable_hook(hook_name: str) -> None:
    """启用单个 hook 的核心逻辑."""
    if hook_name in ["pre-commit", "pre-push"]:
        subprocess.run(
            ["pre-commit", "install", "--hook-type", hook_name],
            check=True,
        )
    else:
        source = _ROOT / "scripts" / "hooks" / hook_name
        target = _get_hooks_dir() / hook_name
        if not source.exists():
            raise HookManagerError(
                operation="enable", details=f"Hook script not found: {source}"
            )
        shutil.copy2(source, target)
        target.chmod(0o755)
        if not os.access(target, os.X_OK):
            raise RuntimeError("Permission verification failed: hook is not executable")


def _disable_hook(hook_name: str) -> None:
    """禁用单个 hook 的核心逻辑."""
    target = _get_hooks_dir() / hook_name
    if target.exists():
        target.unlink()


@app.command("list")
def list_hooks() -> None:
    """List all Git hooks and their status.

    Example: vibe hooks list
    """
    console = Console()
    hooks_dir = _get_hooks_dir()
    enabled = {h for h in _VALID_HOOKS if (hooks_dir / h).exists()}

    console.print("\n[bold]Git hooks status:[/]\n")
    for hook in _VALID_HOOKS:
        if hook in enabled:
            console.print(f"  [green]✓[/green] {hook}")
        else:
            console.print(
                f"  [red]✗[/red] {hook}"
                f" [dim](disabled — vibe hooks enable {hook})[/dim]"
            )

    # Pre-commit 检查项
    console.print("\n[bold]Pre-commit checks[/] (fast, <5s):")
    if "pre-commit" in enabled:
        for check in [
            "shellcheck (bash/sh)",
            "lint-sh (custom)",
            "ruff (Python linter)",
            "black (Python formatter)",
            "mypy (Python type checker)",
            "check-shell-loc",
            "check-python-loc",
            "check-per-file-loc",
            "check-test-file-loc",
        ]:
            console.print(f"  [green]•[/green] {check}")
    else:
        console.print("  [dim](not active — pre-commit hook disabled)[/dim]")

    # Commit-msg 检查项
    console.print("\n[bold]Commit-msg checks[/] (<2s):")
    if "commit-msg" in enabled:
        for check in [
            "commit message format (Conventional Commits)",
            "AST change analysis (automatic attachment)",
        ]:
            console.print(f"  [green]•[/green] {check}")
    else:
        console.print("  [dim](not active — commit-msg hook disabled)[/dim]")

    # Pre-push 检查项（含动态 LOC）
    console.print("\n[bold]Pre-push checks[/] (~30-60s):")
    if "pre-push" in enabled:
        try:
            report = collect_metrics()
            s_ok = report.shell.total_ok
            p_ok = report.python.total_ok
            shell_icon = "[green]✅[/green]" if s_ok else "[red]❌[/red]"
            python_icon = "[green]✅[/green]" if p_ok else "[red]❌[/red]"
            shell_loc = report.shell.total_loc
            shell_lim = report.shell.limit_total
            py_loc = report.python.total_loc
            py_lim = report.python.limit_total
            console.print(
                f"  [green]•[/green] Shell LOC  :"
                f" {shell_loc} / {shell_lim} {shell_icon}"
            )
            console.print(
                f"  [green]•[/green] Python LOC : {py_loc} / {py_lim} {python_icon}"
            )
        except MetricsError:
            console.print(
                "  [green]•[/green] LOC check [dim](metrics unavailable)[/dim]"
            )
        console.print("  [green]•[/green] coverage check (mandatory)")
        console.print("  [green]•[/green] risk assessment → conditional review")
    else:
        console.print("  [dim](not active — pre-push hook disabled)[/dim]")

    # Post-commit 检查项
    console.print("\n[bold]Post-commit hook[/] (<1s):")
    if "post-commit" in enabled:
        console.print("  [green]•[/green] commit creation notification")
    else:
        console.print("  [dim](not active — post-commit hook disabled)[/dim]")


@app.command("enable")
def enable_hook(
    hook_name: str | None = typer.Argument(
        None, help=f"Hook to enable: {', '.join(_VALID_HOOKS)}"
    ),
    all_hooks: bool = typer.Option(False, "--all", help="Enable all hooks at once"),
) -> None:
    """Enable a Git hook (activates it by copying script to .git/hooks/).

    Available hooks: pre-commit, pre-push, commit-msg, post-commit

    Examples:
        vibe hooks enable commit-msg
        vibe hooks enable pre-push
        vibe hooks enable --all
    """
    if all_hooks:
        console = Console()
        console.print("\n[bold]Enabling all Git hooks...[/]\n")
        for name in _VALID_HOOKS:
            try:
                _enable_hook(name)
                console.print(f"  [green]✓[/green] {name}")
            except Exception as e:
                console.print(f"  [red]✗[/red] {name}: {e}")
        console.print(
            "\n[green]Done.[/green] Run [bold]vibe hooks list[/bold] to verify."
        )
        return

    if not hook_name:
        raise typer.BadParameter("Provide a hook name or use --all")
    if hook_name not in _VALID_HOOKS:
        raise typer.BadParameter(
            f"Invalid hook: {hook_name}. Valid: {', '.join(_VALID_HOOKS)}"
        )

    log = logger.bind(domain="hook_manager", action="enable", hook=hook_name)
    try:
        _enable_hook(hook_name)
        typer.echo(f"✓ {hook_name} enabled")
        log.success(f"{hook_name} hook enabled")
    except HookManagerError:
        raise
    except Exception as e:
        raise HookManagerError(operation="enable", details=str(e)) from e


@app.command("disable")
def disable_hook(
    hook_name: str | None = typer.Argument(
        None, help=f"Hook to disable: {', '.join(_VALID_HOOKS)}"
    ),
    all_hooks: bool = typer.Option(False, "--all", help="Disable all hooks at once"),
) -> None:
    """Disable a Git hook (deactivates it by removing script from .git/hooks/).

    Available hooks: pre-commit, pre-push, commit-msg, post-commit

    Examples:
        vibe hooks disable commit-msg
        vibe hooks disable pre-push
        vibe hooks disable --all
    """
    if all_hooks:
        for name in _VALID_HOOKS:
            try:
                _disable_hook(name)
            except Exception as e:
                logger.warning(f"Failed to disable {name}: {e}")
        typer.echo("✓ All hooks disabled")
        return

    if not hook_name:
        raise typer.BadParameter("Provide a hook name or use --all")
    if hook_name not in _VALID_HOOKS:
        raise typer.BadParameter(
            f"Invalid hook: {hook_name}. Valid: {', '.join(_VALID_HOOKS)}"
        )

    log = logger.bind(domain="hook_manager", action="disable", hook=hook_name)
    try:
        _disable_hook(hook_name)
        typer.echo(f"✓ {hook_name} disabled")
        log.success(f"{hook_name} hook disabled")
    except Exception as e:
        raise HookManagerError(operation="disable", details=str(e)) from e


# ── Deprecated aliases (backward compat) ────────────────────────────────────


@app.command("install", hidden=True, deprecated=True)
def install_hook(hook_name: str = typer.Argument(...)) -> None:
    """Deprecated: use 'vibe hooks enable <hook>'."""
    enable_hook(hook_name)


@app.command("install-hooks", hidden=True, deprecated=True)
def install_hooks() -> None:
    """Deprecated: use 'vibe hooks enable --all'."""
    enable_hook(hook_name=None, all_hooks=True)


@app.command("uninstall-hooks", hidden=True, deprecated=True)
def uninstall_hooks() -> None:
    """Deprecated: use 'vibe hooks disable --all'."""
    disable_hook(hook_name=None, all_hooks=True)

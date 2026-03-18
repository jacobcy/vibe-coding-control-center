"""Hooks command - 管理 Git hooks 的安装与卸载."""

import os
import shutil
from pathlib import Path

import typer
from loguru import logger

from vibe3.exceptions import HookManagerError

app = typer.Typer(
    name="hooks", help="Manage Git hooks", no_args_is_help=True, rich_markup_mode="rich"
)

# 项目根目录（hooks.py 位于 src/vibe3/commands/，向上四级到根）
_ROOT = Path(__file__).parent.parent.parent.parent


@app.command("install-hooks")
def install_hooks() -> None:
    """Install Git hooks into .git/hooks/.

    Example: vibe hooks install-hooks
    """
    log = logger.bind(domain="hook_manager", action="install_hooks")
    log.info("Installing Git hooks")

    source = _ROOT / "scripts" / "hooks" / "post-commit"
    target = _ROOT / ".git" / "hooks" / "post-commit"

    try:
        shutil.copy2(source, target)
        target.chmod(0o755)

        if not os.access(target, os.X_OK):
            raise RuntimeError("Permission verification failed: hook is not executable")

        typer.echo("✓ Installed hook: .git/hooks/post-commit")
        log.success("Git hook installed successfully")
    except HookManagerError:
        raise
    except Exception as e:
        raise HookManagerError(operation="install", details=str(e)) from e


@app.command("uninstall-hooks")
def uninstall_hooks() -> None:
    """Uninstall Git hooks from .git/hooks/.

    Example: vibe hooks uninstall-hooks
    """
    log = logger.bind(domain="hook_manager", action="uninstall_hooks")
    log.info("Uninstalling Git hooks")

    target = _ROOT / ".git" / "hooks" / "post-commit"

    try:
        if target.exists():
            target.unlink()
            log.success("Git hook uninstalled successfully")
        # 不存在则静默跳过
    except Exception as e:
        raise HookManagerError(operation="uninstall", details=str(e)) from e

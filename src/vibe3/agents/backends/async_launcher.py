"""Async launcher utilities for codeagent backend.

Pure functions for tmux session allocation, wrapper script generation,
and async command launching.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    pass

# Known Codex runtime warnings to filter from async logs
KNOWN_CODEX_STATE_DB_WARNINGS: Final[tuple[str, ...]] = (
    r"failed to open state db at .*migration .*missing in the resolved migrations",
    r"failed to initialize state runtime at .*migration "
    r".*missing in the resolved migrations",
    r"state db discrepancy during "
    r"find_thread_path_by_id_str_in_subdir: falling_back",
)
KNOWN_CODEX_SNAPSHOT_WARNING: Final[str] = (
    r'Failed to delete shell snapshot at ".*": Os \{ code: 2, kind: NotFound, '
    r'message: "No such file or directory" \}'
)
KNOWN_CODEX_ANALYTICS_WARNING: Final[str] = (
    r"analytics_client: events failed with status 403 Forbidden:"
)


@dataclass(frozen=True)
class AsyncExecutionHandle:
    """Async execution metadata returned by the wrapper adapter."""

    tmux_session: str
    log_path: Path
    prompt_file_path: Path


def list_tmux_sessions(*, prefix: str | None = None) -> set[str]:
    """Return tmux session names, optionally filtered by prefix.

    Args:
        prefix: Optional prefix to filter sessions

    Returns:
        Set of matching tmux session names
    """
    try:
        result = subprocess.run(
            ["tmux", "ls"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return set()
    except Exception:
        return set()
    if result.returncode != 0:
        return set()

    sessions: set[str] = set()
    for line in result.stdout.splitlines():
        session_name = line.split(":", 1)[0].strip()
        if not session_name:
            continue
        if (
            prefix is None
            or session_name == prefix
            or session_name.startswith(f"{prefix}-")
        ):
            sessions.add(session_name)
    return sessions


def has_tmux_session(session_name: str) -> bool:
    """Return whether the exact tmux session currently exists.

    Args:
        session_name: Exact session name to check

    Returns:
        True if session exists, False otherwise
    """
    return session_name in list_tmux_sessions()


def allocate_tmux_session_name(base_name: str) -> str:
    """Return a non-colliding tmux session name.

    Args:
        base_name: Desired base session name

    Returns:
        Unique session name (may have counter suffix like -2, -3)
    """
    candidate = base_name
    counter = 2
    while True:
        probe = subprocess.run(
            ["tmux", "has-session", "-t", candidate],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            return candidate
        candidate = f"{base_name}-{counter}"
        counter += 1


def default_log_dir() -> Path:
    """Return default async log directory path.

    Returns:
        Path to async log directory
    """
    override_dir = os.environ.get("VIBE3_ASYNC_LOG_DIR", "").strip()
    if override_dir:
        return Path(override_dir).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / "temp" / "logs"


def resolve_async_log_path(log_dir: Path, execution_name: str) -> Path:
    """Resolve log path for async execution with issue number awareness.

    Args:
        log_dir: Base log directory
        execution_name: Execution name (e.g., vibe3-manager-issue-123)

    Returns:
        Resolved log path
    """
    issue_match = re.match(
        r"^vibe3-(manager|planner|executor|reviewer|supervisor|plan|run|review)(?:-[^-]+)?(?:-(?:task|dev))?-issue-(\d+)(?:-(\d+))?$",
        execution_name,
    )
    if issue_match:
        role, issue_number, suffix = issue_match.groups()
        role_name = {
            "manager": "manager",
            "planner": "plan",
            "executor": "run",
            "reviewer": "review",
            "supervisor": "supervisor",
            "plan": "plan",
            "run": "run",
            "review": "review",
        }[role]
        file_name = role_name if suffix is None else f"{role_name}-{suffix}"
        return log_dir / "issues" / f"issue-{issue_number}" / f"{file_name}.async.log"

    governance_match = re.match(
        r"^vibe3-governance-(.+)$",
        execution_name,
    )
    if governance_match:
        return (
            log_dir
            / "orchestra"
            / "governance"
            / f"{governance_match.group(1)}.async.log"
        )

    return log_dir / f"{execution_name}.async.log"


def build_async_log_filter() -> list[str]:
    """Return awk filter that strips known Codex runtime noise from async logs.

    Also filters out <agent-prompt> blocks to prevent full prompts from
    appearing in repository logs.

    Returns:
        awk command arguments
    """
    state_patterns = " || ".join(
        f"$0 ~ /{pattern}/" for pattern in KNOWN_CODEX_STATE_DB_WARNINGS
    )
    script = (
        # Filter agent-prompt blocks
        "$0 ~ /<agent-prompt>/ { skip_prompt=1; prompt_lines++; next }\n"
        "skip_prompt { if ($0 ~ /<\\/agent-prompt>/) { skip_prompt=0 } next }\n"
        # Filter known Codex warnings
        f"({state_patterns}) {{ state_db++; next }}\n"
        f"$0 ~ /{KNOWN_CODEX_SNAPSHOT_WARNING}/ "
        f"{{ shell_snapshot++; next }}\n"
        f"$0 ~ /{KNOWN_CODEX_ANALYTICS_WARNING}/ "
        f"{{ analytics++; skip_html=1; next }}\n"
        "skip_html { if ($0 ~ /<\\/html>/) { skip_html=0 } next }\n"
        "{ print }\n"
        "END {\n"
        '  if (prompt_lines > 0) print "[vibe3 async] suppressed " '
        'prompt_lines " agent-prompt line(s)"\n'
        '  if (state_db > 0) print "[vibe3 async] suppressed " '
        'state_db " codex state-db warning line(s)"\n'
        '  if (shell_snapshot > 0) print "[vibe3 async] suppressed " '
        'shell_snapshot " codex shell-snapshot cleanup warning line(s)"\n'
        '  if (analytics > 0) print "[vibe3 async] suppressed " '
        'analytics " codex analytics 403 warning block(s)"\n'
        "}\n"
    )
    # tmux send-keys feeds literal newlines as Enter presses; keep the awk
    # program on a single shell line so async sessions don't get stuck in
    # zsh "pipe quote>" continuation mode.
    script = script.replace("\n", "; ").replace("{;", "{ ").strip()
    return ["awk", script]


def build_async_shell_command(
    command: list[str],
    *,
    log_path: Path,
    keep_alive_seconds: int,
    env: dict[str, str] | None = None,
) -> str:
    """Build shell command for async execution with logging.

    Args:
        command: Command to execute
        log_path: Path for filtered log
        keep_alive_seconds: Seconds to keep tmux session alive after completion
        env: Optional environment overrides

    Returns:
        Shell command string
    """
    filter_command = shlex.join(build_async_log_filter())
    env = env or {}
    env_overrides = {
        key: value for key, value in env.items() if os.environ.get(key) != value
    }
    command_with_env = command
    if env_overrides:
        env_prefix = ["env"] + [
            f"{key}={value}" for key, value in sorted(env_overrides.items())
        ]
        command_with_env = env_prefix + command
    cmd_str = shlex.join(command_with_env)
    log_str = shlex.quote(str(log_path))

    # Single filtered log file (removed wrapper.full.log to avoid duplication)
    shell = (
        f"{cmd_str} 2>&1 | {filter_command} | tee {log_str}; "
        "cmd_status=${PIPESTATUS[0]:-$?}; "
        "echo; "
        'echo "[vibe3 async] command exited with status: ${cmd_status}"; '
    )
    if keep_alive_seconds > 0:
        shell += (
            f'echo "[vibe3 async] keeping tmux session alive for '
            f'{keep_alive_seconds}s for inspection..."; '
            f"sleep {keep_alive_seconds}; "
        )
    return shell + "exit ${cmd_status}"


def write_async_wrapper_script(shell_command: str, *, execution_name: str) -> Path:
    """Persist the async wrapper command to a script file for tmux launch.

    Launching tmux with a script avoids racing interactive shell startup
    output against `send-keys`, which can corrupt long async commands.

    Args:
        shell_command: Shell command to execute
        execution_name: Execution name for script filename

    Returns:
        Path to wrapper script
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", execution_name).strip("-") or "async"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f"vibe3-{slug}-",
        suffix=".sh",
        delete=False,
    ) as tmp:
        tmp.write("#!/usr/bin/env zsh\n")
        tmp.write(shell_command)
        tmp.write("\n")
    path = Path(tmp.name)
    path.chmod(0o700)
    return path


def spawn_tmux_command(
    command: list[str],
    *,
    execution_name: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    keep_alive_seconds: int = 0,
) -> AsyncExecutionHandle:
    """Spawn command in tmux session with repo-local logging.

    Args:
        command: Command to execute
        execution_name: Execution name for session and log
        cwd: Working directory
        env: Optional environment overrides
        keep_alive_seconds: Seconds to keep session alive after completion

    Returns:
        AsyncExecutionHandle with session and log info
    """
    project_root = cwd or Path.cwd()

    log_dir = default_log_dir()
    prefix = execution_name.replace("/", "-")[:50]
    session_id = allocate_tmux_session_name(prefix)

    # Use codeagent's specialized log path resolution (includes issue number)
    # Use actual session_id (may include counter suffix like -2, -3)
    log_path = resolve_async_log_path(log_dir, session_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()

    shell_command = build_async_shell_command(
        command,
        log_path=log_path,
        keep_alive_seconds=keep_alive_seconds,
        env=env,
    )
    wrapper_path = write_async_wrapper_script(
        shell_command,
        execution_name=execution_name,
    )

    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session_id, "zsh", str(wrapper_path)],
        cwd=project_root,
        check=True,
    )

    return AsyncExecutionHandle(
        tmux_session=session_id,
        log_path=log_path,
        prompt_file_path=Path(""),
    )


def start_async_command(
    command: list[str],
    *,
    execution_name: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    keep_alive_seconds: int = 0,
) -> AsyncExecutionHandle:
    """Start an already-built command in tmux with repo-local logging.

    Args:
        command: Command to execute
        execution_name: Execution name for session and log
        cwd: Working directory
        env: Optional environment overrides
        keep_alive_seconds: Seconds to keep session alive after completion

    Returns:
        AsyncExecutionHandle with session and log info
    """
    return spawn_tmux_command(
        command,
        execution_name=execution_name,
        cwd=cwd,
        env=env,
        keep_alive_seconds=keep_alive_seconds,
    )

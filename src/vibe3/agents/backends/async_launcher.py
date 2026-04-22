"""Async launcher utilities for codeagent backend.

Pure functions for tmux session allocation, wrapper script generation,
and async command launching.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

CRITICAL_ENV_PASSTHROUGH = {
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "SHELL",
    "TMPDIR",
    "USER",
}


@dataclass(frozen=True)
class AsyncExecutionHandle:
    """Async execution metadata returned by the wrapper adapter."""

    tmux_session: str
    log_path: Path
    prompt_file_path: Path


def build_tmux_log_filter(session_id: str) -> str:
    """Return the awk program used to persist tmux pane output."""
    awk_script = """
/<agent-prompt>/ {
    skip_prompt = 1
    next
}
skip_prompt && /<\\/agent-prompt>/ {
    skip_prompt = 0
    next
}
skip_prompt {
    next
}
/Uninstalled/ { next }
/Installing wheels/ { next }
/Installed 1 package/ { next }
/\\[2m/ { next }
/░/ { next }
/█/ { next }
/API Error: 429/ || /ServerOverloaded/ || /TooManyRequests/ || /rate_limit/ {
    print "\\n[vibe3] FATAL: 429 Rate Limit. Aborting to prevent loop."
    fflush()
    system("tmux kill-session -t {SESSION_ID}")
    exit 1
}
{
    print
    fflush()
}
"""
    return awk_script.replace("{SESSION_ID}", session_id).strip()


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


def allocate_tmux_session_name(base_name: str, *, auto_increment: bool = True) -> str:
    """Return a non-colliding tmux session name.

    Args:
        base_name: Desired base session name
        auto_increment: If False, returns base_name immediately even if it exists.
            If True, returns unique session name (may have counter suffix like -2, -3).

    Returns:
        Session name
    """
    if not auto_increment:
        return base_name

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
        Resolved log path (not guaranteed to be unique)
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


def allocate_log_path(log_dir: Path, execution_name: str) -> Path:
    """Resolve and allocate a non-colliding log path.

    Uses atomic file creation to prevent TOCTOU race conditions in concurrent scenarios.
    Ensures we don't overwrite previous logs, even if the execution name (session id)
    doesn't have an incremented suffix.

    Args:
        log_dir: Base log directory
        execution_name: Execution name (session id)

    Returns:
        Unique log path (file is atomically created to reserve the path)
    """
    base_path = resolve_async_log_path(log_dir, execution_name)

    # Ensure parent directory exists before attempting atomic creation
    base_path.parent.mkdir(parents=True, exist_ok=True)

    # Try atomic creation with O_EXCL to prevent race conditions
    # This atomically checks "does not exist" and creates the file
    try:
        fd = os.open(
            str(base_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
        os.close(fd)
        return base_path
    except FileExistsError:
        # File exists, need to find next available suffix
        pass

    # If file exists, find the next suffix using atomic creation
    # e.g. manager.async.log -> manager-2.async.log
    name = base_path.name
    if not name.endswith(".async.log"):
        # Fallback: just return the base path even though it exists
        # This shouldn't happen but provides graceful degradation
        return base_path

    base_name = name[: -len(".async.log")]
    counter = 2
    while True:
        candidate = base_path.parent / f"{base_name}-{counter}.async.log"
        try:
            # Atomic creation attempt for each candidate
            fd = os.open(
                str(candidate),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
            os.close(fd)
            return candidate
        except FileExistsError:
            # Try next counter
            counter += 1


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
    from loguru import logger

    project_root = cwd or Path.cwd()

    log_dir = default_log_dir()
    prefix = execution_name.replace("/", "-")[:50]

    # Rule: L3 agent roles (manager/plan/run/review) MUST NOT auto-increment
    # to prevent multiple physical sessions running for the same task.
    # Supervisor/Governance can auto-increment as they are often parallel or transient.
    auto_inc = True
    if any(
        f"vibe3-{role}" in execution_name
        for role in ["manager", "plan", "run", "review"]
    ):
        auto_inc = False

    session_id = allocate_tmux_session_name(prefix, auto_increment=auto_inc)

    # Intercept duplicate session if auto-increment is disabled
    if not auto_inc and has_tmux_session(session_id):
        logger.bind(
            domain="async_launcher",
            session=session_id,
            execution_name=execution_name,
        ).warning("Intercepted duplicate physical tmux session, aborting spawn")
        raise RuntimeError(f"Tmux session '{session_id}' already exists")

    # Use codeagent's specialized log path resolution (includes issue number)
    # Use allocate_log_path to ensure logs are never overwritten, even if
    # tmux session id is fixed.
    log_path = allocate_log_path(log_dir, session_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepend environment overrides to the command
    final_command = command
    if env:
        env_overrides = {
            k: v
            for k, v in env.items()
            if os.environ.get(k) != v or k in CRITICAL_ENV_PASSTHROUGH
        }
        if env_overrides:
            final_command = (
                ["env"]
                + [f"{k}={v}" for k, v in sorted(env_overrides.items())]
                + command
            )

    # Start an idle tmux shell first so we can attach pipe-pane before the
    # real command begins emitting output. Otherwise we can miss the opening
    # <agent-prompt> marker and leak prompt body into repo-local logs.
    tmux_args = ["tmux", "new-session", "-d", "-s", session_id, "-c", str(project_root)]
    if keep_alive_seconds > 0:
        tmux_args += ["-e", "TMUX_PANE_REMAIN=1"]

    subprocess.run(tmux_args, check=True)

    if keep_alive_seconds > 0:
        # Set remain-on-exit option explicitly as well
        subprocess.run(
            ["tmux", "set-option", "-t", session_id, "remain-on-exit", "on"],
            check=False,
        )

    # Pipe pane output to a repo-local log without breaking PTY behavior.
    # Keep the filter deliberately dumb: strip prompt echoes and a few known
    # uv/bootstrap noise lines, but do not gate on markers or buffer output.
    awk_filter = build_tmux_log_filter(session_id)
    pipe_cmd = f"awk {shlex.quote(awk_filter)} >> {shlex.quote(str(log_path))}"
    subprocess.run(
        ["tmux", "pipe-pane", "-t", session_id, pipe_cmd],
        check=False,
    )

    command_str = f"VIBE3_LOG_PATH={shlex.quote(str(log_path))} exec {
        shlex.join(final_command)}"
    subprocess.run(
        [
            "tmux",
            "respawn-pane",
            "-k",
            "-t",
            session_id,
            "-c",
            str(project_root),
            command_str,
        ],
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

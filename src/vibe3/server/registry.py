"""Utility functions for orchestra server registry and assembly.

Extracted from orchestra/serve_utils.py.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.failed_gate import FailedGate
from vibe3.orchestra.logging import orchestra_events_log_path, orchestra_log_dir
from vibe3.orchestra.services.assignee_dispatch import AssigneeDispatchService
from vibe3.orchestra.services.comment_reply import CommentReplyService
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.pr_review_dispatch import PRReviewDispatchService
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.orchestra.services.supervisor_handoff import SupervisorHandoffService
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.services.orchestra_status_service import (
    OrchestraSnapshot,
    OrchestraStatusService,
)
from vibe3.services.session_registry import SessionRegistryService

ORCHESTRA_TMUX_SESSION = "vibe3-orchestra-serve"


def _resolve_orchestra_repo_root() -> Path:
    """Resolve the shared repo root for orchestra-managed auto scenes.

    We intentionally anchor orchestra to the git common-dir parent (the main
    repository root), not the caller's current worktree cwd. This keeps auto
    task scenes under ``<repo>/.worktrees/`` instead of nesting them under the
    current debug/manual worktree.
    """
    try:
        git_common_dir = GitClient().get_git_common_dir()
        if git_common_dir:
            return Path(git_common_dir).parent
    except Exception:
        pass
    return Path.cwd()


def _resolve_dispatcher_repo_root(
    config: OrchestraConfig,
    launch_cwd: Path | None = None,
) -> Path:
    """Resolve the worktree root used for dispatcher-managed auto scenes."""
    _ = config
    _ = launch_cwd
    return _resolve_orchestra_repo_root().resolve()


def _resolve_dispatcher_models_root(
    config: OrchestraConfig,
    launch_cwd: Path | None = None,
) -> Path:
    """Resolve control-plane models root for dispatcher-managed execution."""
    resolved_cwd = (launch_cwd or Path.cwd()).resolve()
    if config.debug:
        return resolved_cwd
    return _resolve_orchestra_repo_root().resolve()


def _resolve_orchestra_log_dir(launch_cwd: Path | None = None) -> Path:
    """Resolve the shared orchestra log root anchored to the launch cwd."""
    return (launch_cwd or Path.cwd()).resolve() / "temp" / "logs"


def _build_server(config: OrchestraConfig) -> tuple[HeartbeatServer, FastAPI]:
    """Instantiate heartbeat + FastAPI app with registered services."""
    return _build_server_with_launch_cwd(config)


def _build_server_with_launch_cwd(
    config: OrchestraConfig,
    launch_cwd: Path | None = None,
) -> tuple[HeartbeatServer, FastAPI]:
    """Instantiate heartbeat + FastAPI app with explicit launch cwd context."""
    from vibe3.agents.backends.codeagent import CodeagentBackend
    from vibe3.server.app import make_webhook_router

    shared_github = GitHubClient()
    shared_store = SQLiteClient()
    shared_backend = CodeagentBackend()
    shared_registry = SessionRegistryService(store=shared_store, backend=shared_backend)
    failed_gate = FailedGate(github=shared_github, repo=config.repo)

    heartbeat = HeartbeatServer(config, failed_gate=failed_gate)

    shared_executor = ThreadPoolExecutor(max_workers=config.max_concurrent_flows)
    shared_manager = ManagerExecutor(
        config,
        dry_run=config.dry_run,
        repo_path=_resolve_dispatcher_repo_root(config, launch_cwd),
        registry=shared_registry,
    )

    # Pass circuit_breaker from manager for status reporting
    status_service = OrchestraStatusService(
        config,
        github=shared_github,
        orchestrator=shared_manager.flow_manager,
        circuit_breaker=shared_manager._circuit_breaker,
        failed_gate=failed_gate,
    )

    if config.assignee_dispatch.enabled:
        heartbeat.register(
            AssigneeDispatchService(
                config,
                manager=shared_manager,
                github=shared_github,
                executor=shared_executor,
            )
        )
    if config.comment_reply.enabled:
        heartbeat.register(
            CommentReplyService(
                config,
                github=shared_github,
            )
        )
    if config.pr_review_dispatch.enabled:
        heartbeat.register(
            PRReviewDispatchService(
                config,
                manager=shared_manager,
                executor=shared_executor,
            )
        )
    if config.state_label_dispatch.enabled:
        heartbeat.register(
            StateLabelDispatchService(
                config,
                trigger_state=IssueState.READY,
                trigger_name="manager",
                status_service=status_service,
                manager=shared_manager,
                github=shared_github,
                executor=shared_executor,
                registry=shared_registry,
            )
        )
        heartbeat.register(
            StateLabelDispatchService(
                config,
                trigger_state=IssueState.HANDOFF,
                trigger_name="manager",
                status_service=status_service,
                manager=shared_manager,
                github=shared_github,
                executor=shared_executor,
                registry=shared_registry,
            )
        )
        heartbeat.register(
            StateLabelDispatchService(
                config,
                trigger_state=IssueState.CLAIMED,
                trigger_name="plan",
                status_service=status_service,
                manager=shared_manager,
                github=shared_github,
                executor=shared_executor,
                registry=shared_registry,
            )
        )
        heartbeat.register(
            StateLabelDispatchService(
                config,
                trigger_state=IssueState.IN_PROGRESS,
                trigger_name="run",
                status_service=status_service,
                manager=shared_manager,
                github=shared_github,
                executor=shared_executor,
                registry=shared_registry,
            )
        )
        heartbeat.register(
            StateLabelDispatchService(
                config,
                trigger_state=IssueState.REVIEW,
                trigger_name="review",
                status_service=status_service,
                manager=shared_manager,
                github=shared_github,
                executor=shared_executor,
                registry=shared_registry,
            )
        )

    if config.governance.enabled:
        heartbeat.register(
            GovernanceService(
                config,
                status_service=status_service,
                manager=shared_manager,
                executor=shared_executor,
                registry=shared_registry,
            )
        )
    if config.supervisor_handoff.enabled:
        heartbeat.register(
            SupervisorHandoffService(
                config,
                github=shared_github,
                status_service=status_service,
                manager=shared_manager,
                executor=shared_executor,
            )
        )

    fastapi_app = FastAPI(title="vibe3 Orchestra", version="1.0")
    fastapi_app.include_router(make_webhook_router(heartbeat, config.webhook_secret))

    # Store status_service for HTTP endpoint
    fastapi_app.state.status_service = status_service

    @fastapi_app.get("/status")
    def get_status() -> OrchestraSnapshot:
        """Get current orchestra status snapshot."""
        return status_service.snapshot(queued=shared_manager.queued_issues)

    # Mount MCP server (gracefully degrades if not available)
    try:
        from vibe3.server.mcp import create_mcp_server

        mcp = create_mcp_server(
            status_service, get_queued=lambda: shared_manager.queued_issues
        )
        fastapi_app.mount("/mcp", mcp.sse_app())
        logger.bind(domain="orchestra").info("MCP server mounted at /mcp")
    except ImportError as exc:
        logger.bind(domain="orchestra").debug(
            f"MCP package not available, skipping MCP server: {exc}"
        )
    except Exception as exc:
        logger.bind(domain="orchestra").warning(
            f"Failed to mount MCP server, continuing without MCP: {exc}"
        )

    return heartbeat, fastapi_app


def _resolve_tsu_script() -> Path | None:
    """Resolve scripts/tsu.sh path from current repo/worktree."""
    env_path = os.environ.get("VIBE3_TSU_SCRIPT")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return candidate

    cwd_candidate = (Path.cwd() / "scripts" / "tsu.sh").resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            root = Path(result.stdout.strip())
            candidate = root / "scripts" / "tsu.sh"
            if candidate.exists():
                return candidate
    except Exception:
        pass

    return None


def _setup_tailscale_webhook(port: int) -> tuple[bool, str]:
    """Enable temporary Tailscale Funnel webhook via scripts/tsu.sh."""
    tsu = _resolve_tsu_script()
    if tsu is None:
        return (
            False,
            "Cannot enable --ts: scripts/tsu.sh not found "
            "(set VIBE3_TSU_SCRIPT to override)",
        )

    try:
        # Best-effort start; command is idempotent when already running.
        subprocess.run(
            [str(tsu), "start"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        # Keep going; next command reports a concrete failure if unavailable.
        pass

    try:
        result = subprocess.run(
            [str(tsu), "serve", "webhook", str(port)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError:
        return False, f"Cannot execute tsu script: {tsu}"
    except Exception as exc:
        return False, f"Tailscale webhook setup failed: {exc}"

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        detail = stderr or stdout or f"exit={result.returncode}"
        return False, f"Tailscale webhook setup failed: {detail}"

    return True, stdout or f"Tailscale webhook configured for port {port}"


def _is_orchestra_process(pid: int) -> bool:
    """Check if a PID is actually an orchestra process."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        cmdline = result.stdout.strip().lower()
        return "vibe3" in cmdline and "serve" in cmdline
    except Exception:
        return False


def _validate_pid_file(pid_file: Path) -> tuple[int | None, bool]:
    """Validate PID file and check if process is an orchestra instance."""
    if not pid_file.exists():
        return None, False

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None, False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return pid, False
    except PermissionError:
        return pid, False

    return pid, _is_orchestra_process(pid)


def _build_async_serve_command(
    config: OrchestraConfig,
    verbose: int,
    launch_cwd: Path | None = None,
) -> list[str]:
    """Build self-invocation command for async tmux startup."""
    models_root = _resolve_dispatcher_models_root(config, launch_cwd)
    log_dir = _resolve_orchestra_log_dir(launch_cwd)
    cmd = [
        "env",
        "VIBE3_ORCHESTRA_EVENT_LOG=1",
        f"VIBE3_REPO_MODELS_ROOT={models_root}",
        f"VIBE3_ASYNC_LOG_DIR={log_dir}",
        "uv",
        "run",
        "python",
        "src/vibe3/cli.py",
        "serve",
        "start",
        "--no-async",
        "--interval",
        str(config.polling_interval),
        "--port",
        str(config.port),
    ]
    if config.repo:
        cmd.extend(["--repo", config.repo])
    if config.dry_run:
        cmd.append("--dry-run")
    if config.debug:
        cmd.append("--debug")
    for _ in range(verbose):
        cmd.append("-v")
    return cmd


def _start_async_serve(config: OrchestraConfig, verbose: int) -> tuple[bool, str]:
    """Start serve command in tmux session."""
    session_name = ORCHESTRA_TMUX_SESSION
    launch_cwd = Path.cwd()
    cmd = _build_async_serve_command(config, verbose, launch_cwd=launch_cwd)
    try:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "--"] + cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False, "tmux not found, cannot start --async serve mode"
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        if "duplicate session" in stderr.lower():
            return (
                False,
                f"Async serve session already exists: {session_name} "
                "(use `tmux ls` / `tmux kill-session -t vibe3-orchestra-serve`)",
            )
        return False, f"Failed to start async serve: {stderr or str(exc)}"

    return (
        True,
        f"Started Orchestra server in tmux session: {session_name}\n"
        f"Main log: {orchestra_events_log_path(launch_cwd)}\n"
        f"Log dir: {orchestra_log_dir(launch_cwd)}\n"
        "Use `uv run python src/vibe3/cli.py serve status` or "
        "`tmux attach -t vibe3-orchestra-serve` to inspect",
    )


def _orchestra_tmux_session_exists() -> bool:
    """Return whether the orchestra tmux session currently exists."""
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", ORCHESTRA_TMUX_SESSION],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return result.returncode == 0


def _kill_orchestra_tmux_session() -> bool:
    """Kill the orchestra tmux session if it exists."""
    try:
        result = subprocess.run(
            ["tmux", "kill-session", "-t", ORCHESTRA_TMUX_SESSION],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return result.returncode == 0

"""Utility functions for orchestra server registry and assembly.

Extracted from orchestra/serve_utils.py.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.orchestra.heartbeat import HeartbeatServer
from vibe3.orchestra.services.assignee_dispatch import AssigneeDispatchService
from vibe3.orchestra.services.comment_reply import CommentReplyService
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.pr_review_dispatch import PRReviewDispatchService
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.orchestra.services.status_service import (
    OrchestraSnapshot,
    OrchestraStatusService,
)


def _build_server(config: OrchestraConfig) -> tuple[HeartbeatServer, FastAPI]:
    """Instantiate heartbeat + FastAPI app with registered services."""
    from vibe3.server.app import make_webhook_router

    heartbeat = HeartbeatServer(config)

    # Shared resources (reduces duplication)
    shared_executor = ThreadPoolExecutor(max_workers=config.max_concurrent_flows)
    shared_github = GitHubClient()
    shared_orchestrator = FlowOrchestrator(config)
    shared_dispatcher = Dispatcher(
        config,
        dry_run=config.dry_run,
        orchestrator=shared_orchestrator,
    )

    # Status service for HTTP endpoint and CLI
    # Pass circuit_breaker from dispatcher for status reporting
    status_service = OrchestraStatusService(
        config,
        github=shared_github,
        orchestrator=shared_orchestrator,
        circuit_breaker=shared_dispatcher._circuit_breaker,
    )

    if config.assignee_dispatch.enabled:
        heartbeat.register(
            AssigneeDispatchService(
                config,
                dispatcher=shared_dispatcher,
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
                dispatcher=shared_dispatcher,
                executor=shared_executor,
            )
        )
    if config.state_label_dispatch.enabled:
        heartbeat.register(
            StateLabelDispatchService(
                config,
                dispatcher=shared_dispatcher,
                github=shared_github,
                executor=shared_executor,
            )
        )

    if config.governance.enabled:
        heartbeat.register(
            GovernanceService(
                config,
                status_service=status_service,
                dispatcher=shared_dispatcher,
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
        return status_service.snapshot()

    # Mount MCP server (optional, gracefully degrades if mcp package not available)
    try:
        from vibe3.server.mcp import create_mcp_server

        mcp = create_mcp_server(status_service)
        # Mount SSE endpoint for MCP
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
    """Validate PID file and check if process is running.

    Returns:
        Tuple of (pid, is_valid_orchestra_process)
    """
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


def _build_async_serve_command(config: OrchestraConfig, verbose: int) -> list[str]:
    """Build self-invocation command for async tmux startup."""
    cmd = [
        "uv",
        "run",
        "python",
        "src/vibe3/cli.py",
        "serve",
        "start",
        "--interval",
        str(config.polling_interval),
        "--port",
        str(config.port),
    ]
    if config.repo:
        cmd.extend(["--repo", config.repo])
    if config.dry_run:
        cmd.append("--dry-run")
    for _ in range(verbose):
        cmd.append("-v")
    return cmd


def _start_async_serve(config: OrchestraConfig, verbose: int) -> tuple[bool, str]:
    """Start serve command in tmux session.

    Returns:
        (success, message)
    """
    session_name = "vibe3-orchestra-serve"
    cmd = _build_async_serve_command(config, verbose)
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
        "Use `vibe3 serve status` or `tmux attach -t vibe3-orchestra-serve` to inspect",
    )

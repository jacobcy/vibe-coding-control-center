"""Utility functions for orchestra server registry and assembly.

Extracted from orchestra/serve_utils.py.
"""

import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.execution.capacity_service import CapacityService
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import FailedGate
from vibe3.orchestra.logging import orchestra_events_log_path, orchestra_log_dir
from vibe3.orchestra.services.comment_reply import CommentReplyService
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.roles.registry import LABEL_DISPATCH_ROLES
from vibe3.runtime.circuit_breaker import CircuitBreaker
from vibe3.runtime.heartbeat import HeartbeatServer
from vibe3.services.orchestra_status_service import (
    OrchestraSnapshot,
    OrchestraStatusService,
)

ORCHESTRA_TMUX_SESSION = "vibe3-orchestra-serve"


def _resolve_dispatcher_models_root(
    config: OrchestraConfig,
    launch_cwd: Path | None = None,
) -> Path:
    """Resolve control-plane models root for dispatcher-managed execution."""
    resolved_cwd = (launch_cwd or Path.cwd()).resolve()
    if config.debug:
        return resolved_cwd
    return resolve_orchestra_repo_root().resolve()


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

    # Startup cleanup: unconditionally mark all active sessions as stopped.
    # Design: server lifecycle owns session state. Any session from a previous
    # run is considered ended on restart, regardless of tmux state. The tmux
    # processes are NOT killed -- agents may continue writing results -- but
    # capacity slots are fully released so dispatch starts from a clean slate.
    shared_registry.clear_all_sessions()

    failed_gate = FailedGate(github=shared_github, repo=config.repo)

    heartbeat = HeartbeatServer(config, failed_gate=failed_gate)
    # Shutdown cleanup: mark all sessions stopped when the server exits.
    # Same clean-slate semantics as startup -- session lifecycle is owned by
    # the server. Agents may still be running in tmux; they are not killed.
    heartbeat.set_shutdown_callback(shared_registry.clear_all_sessions)

    shared_executor = ThreadPoolExecutor(max_workers=config.max_concurrent_flows)
    shared_flow_manager = FlowManager(config, registry=shared_registry)
    shared_circuit_breaker = None

    # Create shared CapacityService for capacity-aware dispatch
    shared_capacity = CapacityService(config, shared_store, shared_backend)

    if config.circuit_breaker.enabled:
        shared_circuit_breaker = CircuitBreaker(
            failure_threshold=config.circuit_breaker.failure_threshold,
            cooldown_seconds=config.circuit_breaker.cooldown_seconds,
            half_open_max_tests=config.circuit_breaker.half_open_max_tests,
        )

    # Pass circuit_breaker from manager for status reporting
    status_service = OrchestraStatusService(
        config,
        github=shared_github,
        orchestrator=shared_flow_manager,
        circuit_breaker=shared_circuit_breaker,
        failed_gate=failed_gate,
    )

    if config.comment_reply.enabled:
        heartbeat.register(
            CommentReplyService(
                config,
                github=shared_github,
            )
        )

    # Build dispatch services for all trigger states.
    # These are NOT registered directly with the heartbeat — instead they are
    # passed to OrchestrationFacade and called concurrently from its on_tick(),
    # reducing heartbeat services from 6 to 1 (the facade itself).
    dispatch_services = []
    if config.state_label_dispatch.enabled:
        for role_service in LABEL_DISPATCH_ROLES:
            dispatch_services.append(
                StateLabelDispatchService(
                    config,
                    github=shared_github,
                    executor=shared_executor,
                    flow_manager=shared_flow_manager,
                    registry=shared_registry,
                    capacity=shared_capacity,
                    role_def=role_service,
                )
            )

    # Register OrchestrationFacade as the single domain-first
    # heartbeat entry point. It incorporates governance scan,
    # supervisor scan, and issue-label dispatch polling.
    facade = OrchestrationFacade(
        config=config,
        dispatch_services=dispatch_services,
        capacity=shared_capacity,
        failed_gate=failed_gate,
    )
    heartbeat.register(facade)

    # GovernanceService and SupervisorHandoffService are deleted.
    # Governance and supervisor dispatch are now handled inline by
    # OrchestrationFacade via roles/governance.py and roles/supervisor.py
    # through ExecutionCoordinator — no per-role service or handler needed.

    fastapi_app = FastAPI(title="vibe3 Orchestra", version="1.0")
    fastapi_app.include_router(make_webhook_router(heartbeat, config.webhook_secret))

    # Store status_service for HTTP endpoint
    fastapi_app.state.status_service = status_service

    @fastapi_app.get("/status")
    def get_status() -> OrchestraSnapshot:
        """Get current orchestra status snapshot."""
        return status_service.snapshot()

    # Mount MCP server (gracefully degrades if not available)
    try:
        from vibe3.server.mcp import create_mcp_server

        mcp = create_mcp_server(status_service, get_queued=None)
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
    """Start serve command in tmux session with streaming output."""
    session_name = ORCHESTRA_TMUX_SESSION
    launch_cwd = Path.cwd()
    cmd = _build_async_serve_command(config, verbose, launch_cwd=launch_cwd)

    # Use async_launcher's streaming output logic
    log_path = orchestra_events_log_path(launch_cwd)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, *cmd],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "tmux",
                "pipe-pane",
                "-t",
                session_name,
                f"cat >> {shlex.quote(str(log_path))}",
            ],
            check=False,
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

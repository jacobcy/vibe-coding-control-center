"""Utility functions for orchestra server registry and assembly.

Extracted from orchestra/serve_utils.py.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse

    from vibe3.models import OrchestraConfig
    from vibe3.runtime import HeartbeatServer, OrchestraInstanceInfo

ORCHESTRA_TMUX_SESSION = "vibe3-orchestra-serve"


def _resolve_dispatcher_models_root(
    config: "OrchestraConfig",
    launch_cwd: Path | None = None,
) -> Path:
    """Resolve control-plane models root for dispatcher-managed execution."""
    from vibe3.execution import resolve_orchestra_repo_root

    resolved_cwd = (launch_cwd or Path.cwd()).resolve()
    if config.debug:
        return resolved_cwd
    return resolve_orchestra_repo_root().resolve()


def _resolve_orchestra_log_dir(launch_cwd: Path | None = None) -> Path:
    """Resolve the shared orchestra log root anchored to the launch cwd."""
    return (launch_cwd or Path.cwd()).resolve() / "temp" / "logs"


def _build_server(config: "OrchestraConfig") -> tuple["HeartbeatServer", "FastAPI"]:
    """Instantiate heartbeat + FastAPI app with registered services."""
    return _build_server_with_launch_cwd(config)


def _build_server_with_launch_cwd(
    config: "OrchestraConfig",
    launch_cwd: Path | None = None,
) -> tuple["HeartbeatServer", "FastAPI"]:
    """Instantiate heartbeat + FastAPI app with explicit launch cwd context."""
    from typing import cast

    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from starlette.concurrency import run_in_threadpool

    from vibe3.agents import CodeagentBackend
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.domain import (
        FailedGate,
        FlowManager,
        GlobalDispatchCoordinator,
        OrchestrationFacade,
        build_action_handlers,
        evaluate_rules,
        load_rules,
    )
    from vibe3.environment import SessionRegistryService
    from vibe3.execution import CapacityService
    from vibe3.models import DomainEvent, get_publisher
    from vibe3.orchestra import create_global_dispatch_coordinator
    from vibe3.runtime import (
        CircuitBreaker,
        FailedGateProtocol,
        HeartbeatServer,
    )
    from vibe3.services import CheckService, FlowService, OrchestraStatusService

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

    failed_gate = FailedGate(store=shared_store)

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

    # Register OrchestrationFacade as the single domain-first
    # heartbeat entry point. It incorporates governance scan,
    # supervisor scan, and issue-label dispatch polling.
    # GlobalDispatchCoordinator is created internally by the facade.

    shared_check_service = CheckService(
        store=shared_store,
        git_client=shared_flow_manager.git,
        github_client=shared_github,
    )
    shared_flow_service = FlowService(
        store=shared_store,
        git_client=shared_flow_manager.git,
    )

    facade = OrchestrationFacade(
        config=config,
        capacity=shared_capacity,
        store=shared_store,
        coordinator_factory=create_global_dispatch_coordinator,  # type: ignore[arg-type]
        coordinator_class=GlobalDispatchCoordinator,
        check_service=shared_check_service,
        flow_service=shared_flow_service,
        queue_filter=None,  # default behavior
    )

    def _cleanup_expired_actors() -> list[str]:
        from vibe3.execution import get_actor_registry

        return get_actor_registry().cleanup_expired()

    heartbeat = HeartbeatServer(
        config,
        failed_gate=cast(FailedGateProtocol | None, failed_gate),
        error_tracker=None,
        check_service=shared_check_service,
        cleanup_service=None,
        actor_cleanup=_cleanup_expired_actors,
    )
    heartbeat.register(facade)  # type: ignore[arg-type]

    # Wire event rules engine into EventPublisher
    try:
        from vibe3.utils import find_repo_root

        rules_dir = find_repo_root() / "config" / "policies"
        rules = load_rules(rules_dir)
        action_handlers = build_action_handlers()
        publisher = get_publisher()

        def rule_engine_hook(event: DomainEvent) -> None:  # type: ignore[valid-type]
            evaluate_rules(event, rules, action_handlers)

        publisher.add_publish_hook(rule_engine_hook)
        logger.bind(domain="orchestra").info(
            f"Event rules engine initialized with {len(rules)} rules"
        )
    except Exception as exc:
        logger.bind(domain="orchestra").warning(
            f"Event rules engine initialization failed (non-fatal): {exc}"
        )

    # Combined shutdown callback for all services
    def shutdown_all() -> None:
        """Cleanup all services on shutdown."""
        shared_registry.clear_all_sessions()
        facade.shutdown()

    heartbeat.set_shutdown_callback(shutdown_all)
    # Governance and supervisor dispatch are now handled inline by
    # OrchestrationFacade via roles/governance.py and roles/supervisor.py
    # through ExecutionCoordinator — no per-role service or handler needed.

    fastapi_app = FastAPI(title="vibe3 Orchestra", version="1.0")

    # Store status_service for HTTP endpoint
    fastapi_app.state.status_service = status_service

    @fastapi_app.get("/status")
    async def get_status() -> dict:
        """Get current orchestra status snapshot with job monitoring data."""
        from vibe3.execution import ActiveJob, JobMonitorService

        snapshot = await run_in_threadpool(status_service.snapshot)
        job_svc = JobMonitorService()
        jobs = job_svc.snapshot()

        def _job_to_dict(job: ActiveJob) -> dict:
            return {
                "actor_id": job.actor_id,
                "job_type": job.job_type.value,
                "status": job.status.value,
                "issue_number": job.issue_number,
                "branch": job.branch,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "pid": job.pid,
            }

        result = {
            **snapshot.__dict__,
            "jobs": {
                "active": [_job_to_dict(j) for j in jobs.active_jobs],
                "recent": [_job_to_dict(j) for j in jobs.recent_jobs],
                "summary": {
                    "running": jobs.running_count,
                    "completed": jobs.completed_count,
                    "failed": jobs.failed_count,
                },
            },
        }
        return result

    @fastapi_app.get("/")
    async def root_redirect() -> RedirectResponse:
        """Redirect root to /status."""
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/status", status_code=301)

    @fastapi_app.get("/web", response_class=HTMLResponse)
    async def get_web_dashboard() -> str:
        """Serve the Orchestra status web console."""
        html_path = Path(__file__).parent / "static" / "status.html"
        return html_path.read_text(encoding="utf-8")

    # Mount MCP server (gracefully degrades if not available)
    try:
        from .mcp import create_mcp_server

        mcp = create_mcp_server(
            status_service, get_queued=facade.get_queued_issue_numbers
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

    # Mount webhook router (gracefully degrades if not available)
    try:
        from .webhook import router as webhook_router

        fastapi_app.include_router(webhook_router)
        logger.bind(domain="orchestra").info(
            "Webhook router mounted at /webhook/github"
        )
    except Exception as exc:
        logger.bind(domain="orchestra").warning(
            f"Failed to mount webhook router, continuing without webhook: {exc}"
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
    """Enable temporary Tailscale Funnel to expose server port via scripts/tsu.sh."""
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


def validate_pid_file(pid_file: Path) -> tuple["OrchestraInstanceInfo | None", bool]:
    """Validate PID file and check if process is a running orchestra instance.

    Returns:
        tuple of (instance_info, is_running):
        - (None, False): No PID file or invalid format
        - (info, False): Valid PID file but process is dead/not orchestra
        - (info, True): Valid PID file and process is running orchestra
    """
    from vibe3.runtime import (
        read_instance_info,
        validate_instance,
    )

    info = read_instance_info(pid_file)
    if info is None:
        return None, False

    is_running = validate_instance(info)
    return info, is_running


def _build_async_serve_command(
    config: "OrchestraConfig",
    verbose: int,
    launch_cwd: Path | None = None,
) -> list[str]:
    """Build self-invocation command for async tmux startup."""

    models_root = _resolve_dispatcher_models_root(config, launch_cwd)
    log_dir = _resolve_orchestra_log_dir(launch_cwd)

    # Resolve the absolute path to vibe3 project root via module location.
    # This works correctly in both:
    # - Local development: points to source repo
    # - Global install: points to ~/.vibe
    # Important: Do NOT use resolve_orchestra_repo_root() which returns
    # the current working project root, not the vibe3 tool's source root.
    repo_root = (Path(__file__).parent.parent.parent.parent).resolve()
    cli_path = repo_root / "src" / "vibe3" / "cli.py"

    # Always explicitly set VIBE3_ASYNC_CLI_PROJECT_ROOT to prevent
    # parent environment hijacking the async child's code-root resolution
    async_cli_root_env = "VIBE3_ASYNC_CLI_PROJECT_ROOT="
    cmd = [
        "env",
        "VIBE3_ORCHESTRA_EVENT_LOG=1",
        f"VIBE3_REPO_MODELS_ROOT={models_root}",
        f"VIBE3_ASYNC_LOG_DIR={log_dir}",
        async_cli_root_env,
    ]
    cmd.extend(
        [
            "uv",
            "run",
            "--project",
            str(repo_root),
            "python",
            str(cli_path),
            "serve",
            "start",
            "--no-async",
            "--interval",
            str(config.polling_interval),
            "--port",
            str(config.port),
        ]
    )
    if config.repo:
        cmd.extend(["--repo", config.repo])
    if config.dry_run:
        cmd.append("--dry-run")
    if config.debug:
        cmd.append("--debug")
    for _ in range(verbose):
        cmd.append("-v")
    return cmd


def _start_async_serve(config: "OrchestraConfig", verbose: int) -> tuple[bool, str]:
    """Start serve command in tmux session with streaming output."""
    from vibe3.observability import orchestra_events_log_path, orchestra_log_dir

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

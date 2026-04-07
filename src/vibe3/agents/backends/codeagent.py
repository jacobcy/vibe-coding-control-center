import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from loguru import logger

from vibe3.agents.backends.codeagent_config import (
    resolve_effective_agent_options,
    sync_models_json,
)
from vibe3.exceptions import AgentExecutionError
from vibe3.models.review_runner import AgentOptions, AgentResult

DEFAULT_WRAPPER_PATH: Final[Path] = (
    Path.home() / ".claude" / "bin" / "codeagent-wrapper"
)

KNOWN_CODEX_STATE_DB_WARNINGS: Final[tuple[str, ...]] = (
    r"failed to open state db at .*migration .*missing in the resolved migrations",
    r"failed to initialize state runtime at .*migration "
    r".*missing in the resolved migrations",  # noqa: E501
    r"state db discrepancy during "
    r"find_thread_path_by_id_str_in_subdir: falling_back",  # noqa: E501
)
KNOWN_CODEX_SNAPSHOT_WARNING: Final[str] = (
    r'Failed to delete shell snapshot at ".*": Os \{ code: 2, kind: NotFound, '
    r'message: "No such file or directory" \}'
)
KNOWN_CODEX_ANALYTICS_WARNING: Final[str] = (
    r"analytics_client: events failed with status 403 Forbidden:"
)
RESUME_RETRY_EXIT_CODES: Final[frozenset[int]] = frozenset({42})
RESUME_RETRY_ERROR_SNIPPETS: Final[tuple[str, ...]] = (
    "session not found",
    "invalid session",
    "failed to resume",
    "unable to resume",
    "could not resume",
    "resume error",
)


@dataclass(frozen=True)
class AsyncExecutionHandle:
    """Async execution metadata returned by the wrapper adapter."""

    tmux_session: str
    log_path: Path
    prompt_file_path: Path


def extract_session_id(stdout: str) -> str | None:
    """Extract session ID from codeagent-wrapper output.

    Pattern:
        SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8
    """
    if not stdout:
        return None
    match = re.search(r"SESSION_ID:\s*([A-Za-z0-9_-]+)", stdout)
    if not match:
        match = re.search(r'"sessionID":"([A-Za-z0-9_-]+)"', stdout)
    if not match:
        match = re.search(r'\\"sessionID\\":\\"([A-Za-z0-9_-]+)\\"', stdout)
    return match.group(1) if match else None


class CodeagentBackend:
    """基于 codeagent-wrapper 二进制的 agent 执行后端。"""

    @staticmethod
    def _should_retry_without_session(
        result: subprocess.CompletedProcess[str],
        *,
        session_id: str | None,
    ) -> bool:
        """Return True when wrapper failure indicates the resume target is invalid."""
        if not session_id:
            return False
        if result.returncode not in RESUME_RETRY_EXIT_CODES:
            return False

        combined_output = f"{result.stdout}\n{result.stderr}".lower()
        return any(
            snippet in combined_output for snippet in RESUME_RETRY_ERROR_SNIPPETS
        )

    @staticmethod
    def _run_subprocess(
        command: list[str],
        *,
        project_root: str,
        timeout_seconds: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

    @staticmethod
    def list_tmux_sessions(*, prefix: str | None = None) -> set[str]:
        """Return tmux session names, optionally filtered by prefix."""
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

    @classmethod
    def has_tmux_session(cls, session_name: str) -> bool:
        """Return whether the exact tmux session currently exists."""
        return session_name in cls.list_tmux_sessions()

    @classmethod
    def has_tmux_session_prefix(cls, prefix: str) -> bool:
        """Return whether any tmux session exists for the given prefix."""
        return bool(cls.list_tmux_sessions(prefix=prefix))

    @staticmethod
    def _build_async_log_filter() -> list[str]:
        """Return awk filter that strips known Codex runtime noise from async logs.

        Also filters out <agent-prompt> blocks to prevent full prompts from
        appearing in repository logs.
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
        return ["awk", script]

    @classmethod
    def _build_async_shell_command(
        cls,
        command: list[str],
        *,
        log_path: Path,
        keep_alive_seconds: int,
    ) -> str:
        filter_command = shlex.join(cls._build_async_log_filter())
        cmd_str = shlex.join(command)
        log_str = shlex.quote(str(log_path))
        return (
            f"{cmd_str} 2>&1 | {filter_command} | tee {log_str}; "
            "status=${PIPESTATUS[0]:-$?}; "
            "echo; "
            'echo "[vibe3 async] command exited with status: ${status}"; '
            f'echo "[vibe3 async] keeping tmux session alive for '
            f'{keep_alive_seconds}s for inspection..."; '
            f"sleep {keep_alive_seconds}; "
            "exit ${status}"
        )

    @staticmethod
    def _allocate_tmux_session_name(base_name: str) -> str:
        """Return a non-colliding tmux session name."""
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

    @staticmethod
    def _prepare_prompt_file(prompt: str) -> Path:
        prompt_dir = Path.home() / ".codeagent" / "agents"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, dir=prompt_dir
        ) as f:
            f.write(prompt)
            return Path(f.name)

    @staticmethod
    def _build_command(
        options: AgentOptions,
        prompt_file_path: str,
        task: str | None = None,
        session_id: str | None = None,
    ) -> list[str]:
        options = resolve_effective_agent_options(options)
        command: list[str] = [str(DEFAULT_WRAPPER_PATH)]

        if options.agent:
            command.extend(["--agent", options.agent])
        elif options.backend:
            command.extend(["--backend", options.backend])
            if options.model:
                command.extend(["--model", options.model])
        else:
            command.extend(["--agent", "code-reviewer"])

        command.extend(["--prompt-file", prompt_file_path])

        if options.worktree and not session_id:
            command.append("--worktree")

        if session_id:
            command.append("resume")
            command.append(cast(str, session_id))
            if task:
                command.append(task)
            else:
                command.append("continue")
        elif task:
            command.append(task)

        return command

    @staticmethod
    def _default_log_dir() -> Path:
        override_dir = os.environ.get("VIBE3_ASYNC_LOG_DIR", "").strip()
        if override_dir:
            return Path(override_dir).expanduser().resolve()
        return Path(__file__).resolve().parents[4] / "temp" / "logs"

    @classmethod
    def _resolve_async_log_path(cls, log_dir: Path, execution_name: str) -> Path:
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
            return (
                log_dir / "issues" / f"issue-{issue_number}" / f"{file_name}.async.log"
            )

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

    def _spawn_tmux_command(
        self,
        command: list[str],
        *,
        execution_name: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        keep_alive_seconds: int = 60,
    ) -> AsyncExecutionHandle:
        project_root = cwd or Path.cwd()
        base_name = execution_name.replace("/", "-")[:50]
        safe_name = self._allocate_tmux_session_name(base_name)
        log_dir = self._default_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._resolve_async_log_path(log_dir, safe_name)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            log_path.unlink()
        shell_command = self._build_async_shell_command(
            command,
            log_path=log_path,
            keep_alive_seconds=keep_alive_seconds,
        )

        subprocess.run(
            ["tmux", "new-session", "-d", "-s", safe_name, "sh", "-lc", shell_command],
            cwd=project_root,
            env=env,
            check=True,
        )

        return AsyncExecutionHandle(
            tmux_session=safe_name,
            log_path=log_path,
            prompt_file_path=Path(""),
        )

    def start_async_command(
        self,
        command: list[str],
        *,
        execution_name: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        keep_alive_seconds: int = 60,
    ) -> AsyncExecutionHandle:
        """Start an already-built command in tmux with repo-local logging."""
        return self._spawn_tmux_command(
            command,
            execution_name=execution_name,
            cwd=cwd,
            env=env,
            keep_alive_seconds=keep_alive_seconds,
        )

    def start_async(
        self,
        prompt: str,
        options: AgentOptions,
        *,
        task: str | None = None,
        session_id: str | None = None,
        execution_name: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        keep_alive_seconds: int = 60,
    ) -> AsyncExecutionHandle:
        """Start codeagent-wrapper in tmux and return the async handle."""
        sync_models_json(options)

        prompt_file_path = self._prepare_prompt_file(prompt)
        command = self._build_command(
            options,
            str(prompt_file_path),
            task=task,
            session_id=session_id,
        )
        handle = self._spawn_tmux_command(
            command,
            execution_name=execution_name,
            cwd=cwd,
            env=env,
            keep_alive_seconds=keep_alive_seconds,
        )
        return AsyncExecutionHandle(
            tmux_session=handle.tmux_session,
            log_path=handle.log_path,
            prompt_file_path=prompt_file_path,
        )

    def run(
        self,
        prompt: str,
        options: AgentOptions,
        task: str | None = None,
        dry_run: bool = False,
        session_id: str | None = None,
        cwd: Path | None = None,
    ) -> AgentResult:
        """Run codeagent-wrapper synchronously."""
        sync_models_json(options)

        project_root = str(cwd or Path.cwd())
        prompt_file_path = str(self._prepare_prompt_file(prompt))

        try:
            command = self._build_command(
                options,
                cast(str, prompt_file_path),
                task=task,
                session_id=session_id,
            )

            if dry_run:
                print("=== Command ===")
                print(" ".join(command))
                if prompt_file_path:
                    print(f"\n=== Prompt File: {prompt_file_path} ===")
                    print(prompt)
                if task:
                    print(f"\n=== Task ===\n{task}")
                print("\n=== End ===")
                return AgentResult(exit_code=0, stdout="[dry-run]", stderr="")

            try:
                result = self._run_subprocess(
                    command,
                    project_root=project_root,
                    timeout_seconds=options.timeout_seconds,
                )

                if self._should_retry_without_session(result, session_id=session_id):
                    retry_command = self._build_command(
                        options,
                        cast(str, prompt_file_path),
                        task=task,
                        session_id=None,
                    )
                    logger.bind(domain="agent_execution").warning(
                        "Stored wrapper session is not resumable; "
                        "retrying with a fresh session."
                    )
                    result = self._run_subprocess(
                        retry_command,
                        project_root=project_root,
                        timeout_seconds=options.timeout_seconds,
                    )

            except FileNotFoundError:
                raise AgentExecutionError(
                    f"codeagent-wrapper not found at {DEFAULT_WRAPPER_PATH}. "
                    "Please ensure it is installed and accessible."
                ) from None
            except subprocess.TimeoutExpired:
                raise AgentExecutionError(
                    f"codeagent-wrapper timed out after {options.timeout_seconds}s. "
                    "Consider increasing the timeout or splitting the review scope."
                ) from None

            if result.stdout:
                print(result.stdout, end="", flush=True)
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="", flush=True)

            agent_result = AgentResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                session_id=extract_session_id(result.stdout),
            )

            if not agent_result.is_success():
                if agent_result.stderr:
                    stderr_preview = agent_result.stderr[:500]
                elif agent_result.stdout:
                    stderr_preview = agent_result.stdout[:500]
                else:
                    stderr_preview = "(no output)"

                raise AgentExecutionError(
                    f"codeagent-wrapper failed with exit code "
                    f"{agent_result.exit_code}:\n{stderr_preview}"
                )

            return agent_result
        finally:
            if prompt_file_path:
                Path(prompt_file_path).unlink(missing_ok=True)

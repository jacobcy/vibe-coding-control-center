"""Codeagent backend - execute agents via codeagent-wrapper.

Core execution logic with session and async launching delegated to dedicated modules.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Final, cast

from loguru import logger

from vibe3.agents.backends.async_launcher import (
    AsyncExecutionHandle,
    spawn_tmux_command,
)
from vibe3.agents.backends.codeagent_config import (
    resolve_effective_agent_options,
    sync_models_json,
)
from vibe3.agents.backends.session_manager import (
    extract_session_id,
    should_retry_without_session,
)
from vibe3.exceptions import AgentExecutionError
from vibe3.models.review_runner import AgentOptions, AgentResult
from vibe3.utils.codeagent_helpers import (
    build_prompt_file_content,
    diagnose_backend_error,
    prepare_prompt_file,
    sanitize_task_shell_meta,
    stream_reader,
    summarize_backend_output,
)

DEFAULT_WRAPPER_PATH: Final[Path] = (
    Path.home() / ".claude" / "bin" / "codeagent-wrapper"
)


class CodeagentBackend:
    """基于 codeagent-wrapper 二进制的 agent 执行后端。"""

    @staticmethod
    def has_tmux_session(session_name: str) -> bool:
        """Check if tmux session exists."""
        from vibe3.agents.backends.async_launcher import has_tmux_session as _has

        return _has(session_name)

    @staticmethod
    def _build_command(
        options: AgentOptions,
        prompt_file_path: str,
        task: str | None = None,
        session_id: str | None = None,
    ) -> list[str]:
        """Build codeagent-wrapper command."""
        options = resolve_effective_agent_options(options)
        command: list[str] = [str(DEFAULT_WRAPPER_PATH)]

        if options.agent:
            command.extend(["--agent", options.agent])
        elif options.backend:
            command.extend(["--backend", options.backend])
            if options.model:
                command.extend(["--model", options.model])
        else:
            command.extend(["--agent", "vibe-reviewer"])

        command.append("--skip-permissions")
        command.extend(["--prompt-file", prompt_file_path])

        safe_task = sanitize_task_shell_meta(task) if task else None

        if session_id:
            command.append("resume")
            command.append(cast(str, session_id))
            if safe_task:
                command.append(safe_task)
            else:
                command.append("continue")
        elif safe_task:
            command.append(safe_task)

        return command

    _ROLE_LOG_NAME: dict[str, str] = {
        "executor": "run",
        "planner": "plan",
        "reviewer": "review",
        "manager": "manager",
        "supervisor": "supervisor",
        "governance": "governance",
    }

    @staticmethod
    def _allocate_sync_log_path(
        log_dir: Path, role_log_name: str, issue_number: str
    ) -> Path:
        """Allocate a non-colliding sync log path with numeric suffix."""
        base = log_dir / f"issue-{issue_number}" / f"{role_log_name}.sync.log"
        base.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(str(base), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            return base
        except FileExistsError:
            pass
        counter = 2
        while True:
            candidate = base.parent / f"{role_log_name}-{counter}.sync.log"
            try:
                fd = os.open(
                    str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644
                )
                os.close(fd)
                return candidate
            except FileExistsError:
                counter += 1

    @staticmethod
    def _run_subprocess(
        command: list[str],
        *,
        project_root: str,
        timeout_seconds: int,
        role: str = "executor",
    ) -> tuple[subprocess.CompletedProcess[str], Path | None]:
        """Run subprocess with streaming output and capture return value."""
        import threading

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        proc = subprocess.Popen(
            command,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            text=False,
        )

        stdout_thread = threading.Thread(
            target=stream_reader,
            args=(proc.stdout, stdout_chunks, sys.stdout, proc),
        )
        stderr_thread = threading.Thread(
            target=stream_reader,
            args=(proc.stderr, stderr_chunks, sys.stderr, proc),
        )

        stdout_thread.start()
        stderr_thread.start()

        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            raise

        stdout_thread.join()
        stderr_thread.join()

        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)

        result = subprocess.CompletedProcess(
            args=command,
            returncode=proc.returncode,
            stdout=stdout_text,
            stderr=stderr_text,
        )

        saved_log_path: Path | None = None
        log_dir = Path(project_root) / "temp" / "logs"
        if "issue-" in project_root or any("issue-" in arg for arg in command):
            import re

            issue_match = re.search(r"issue-(\d+)", project_root)
            if not issue_match:
                for arg in command:
                    issue_match = re.search(r"issue-(\d+)", arg)
                    if issue_match:
                        break

            if issue_match:
                role_log_name = CodeagentBackend._ROLE_LOG_NAME.get(role, role)
                sync_log_path = CodeagentBackend._allocate_sync_log_path(
                    log_dir, role_log_name, issue_match.group(1)
                )
                sync_log_path.write_text(f"{stdout_text}\n{stderr_text}")
                saved_log_path = sync_log_path

        return result, saved_log_path

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
        keep_alive_seconds: int = 0,
    ) -> AsyncExecutionHandle:
        """Start codeagent-wrapper in tmux and return the async handle."""
        sync_models_json(options)

        prompt_file_path = prepare_prompt_file(prompt)
        command = self._build_command(
            options,
            str(prompt_file_path),
            task=task,
            session_id=session_id,
        )
        handle = spawn_tmux_command(
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
        role: str = "executor",
        show_prompt: bool = False,
        include_global_notice: bool = True,
        fallback_prompt: str | None = None,
        fallback_include_global_notice: bool = True,
        dry_run_summary: dict[str, object] | None = None,
    ) -> AgentResult:
        """Run codeagent-wrapper synchronously."""
        sync_models_json(options)

        project_root = str(cwd or Path.cwd())
        prompt_file_path = str(
            prepare_prompt_file(prompt, include_global_notice=include_global_notice)
        )

        try:
            command = self._build_command(
                options,
                cast(str, prompt_file_path),
                task=task,
                session_id=session_id,
            )

            if dry_run:
                if dry_run_summary:
                    print("=== Dry Run Summary ===")
                    for key, value in dry_run_summary.items():
                        print(f"{key}: {value}")
                print("=== Command ===")
                print(" ".join(command))
                if show_prompt and prompt_file_path:
                    print(f"\n=== Prompt File: {prompt_file_path} ===")
                    print(
                        build_prompt_file_content(
                            prompt, include_global_notice=include_global_notice
                        )
                    )
                if task:
                    print(f"\n=== Task ===\n{task}")
                print("\n=== End ===")
                return AgentResult(exit_code=0, stdout="[dry-run]", stderr="")

            wrapper_log_path: Path | None = None
            try:
                result, wrapper_log_path = self._run_subprocess(
                    command,
                    project_root=project_root,
                    timeout_seconds=options.timeout_seconds,
                    role=role,
                )

                if should_retry_without_session(result, session_id=session_id):
                    retry_prompt_path = prompt_file_path
                    if fallback_prompt is not None:
                        retry_prompt_path = str(
                            prepare_prompt_file(
                                fallback_prompt,
                                include_global_notice=fallback_include_global_notice,
                            )
                        )
                    retry_command = self._build_command(
                        options,
                        cast(str, retry_prompt_path),
                        task=task,
                        session_id=None,
                    )
                    logger.bind(domain="agent_execution").warning(
                        "Stored session not resumable; retrying with fresh session."
                    )
                    result, wrapper_log_path = self._run_subprocess(
                        retry_command,
                        project_root=project_root,
                        timeout_seconds=options.timeout_seconds,
                        role=role,
                    )

            except FileNotFoundError:
                raise AgentExecutionError(
                    f"codeagent-wrapper not found at {DEFAULT_WRAPPER_PATH}.",
                    log_path=wrapper_log_path,
                ) from None
            except subprocess.TimeoutExpired:
                raise AgentExecutionError(
                    f"codeagent-wrapper timed out after {options.timeout_seconds}s.",
                    log_path=wrapper_log_path,
                ) from None

            agent_result = AgentResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                session_id=extract_session_id(result.stdout),
            )

            if not agent_result.is_success():
                combined_output = f"{agent_result.stdout}\n{agent_result.stderr}"
                diagnosis = diagnose_backend_error(combined_output)
                stderr_preview = summarize_backend_output(
                    agent_result.stderr, agent_result.stdout
                )

                error_msg = (
                    f"codeagent-wrapper failed (code {agent_result.exit_code}):\n"
                    f"{stderr_preview}"
                )
                if diagnosis:
                    error_msg += f"\n\n{diagnosis}"

                raise AgentExecutionError(error_msg, log_path=wrapper_log_path)

            return agent_result
        finally:
            if prompt_file_path:
                Path(prompt_file_path).unlink(missing_ok=True)

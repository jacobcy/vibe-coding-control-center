"""Codeagent backend - execute agents via codeagent-wrapper.

Core execution logic with session and async launching delegated to dedicated modules.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final, cast

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
from vibe3.config.settings import VibeConfig
from vibe3.exceptions import AgentExecutionError
from vibe3.models.review_runner import AgentOptions, AgentResult

DEFAULT_WRAPPER_PATH: Final[Path] = (
    Path.home() / ".claude" / "bin" / "codeagent-wrapper"
)

# Known backend-internal error patterns with suggested fixes
KNOWN_BACKEND_ERROR_PATTERNS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "schema._zod.def",
        "OpenCode Zod schema error",
        "OpenCode internal schema parsing failed. Try: 1) Update codeagent-wrapper, "
        "2) Use a different model, 3) Check ~/.codeagent/models.json",
    ),
    (
        "Failed to parse event",
        "Backend event parsing error",
        "Backend event parse failed. Try: 1) Use a different model/backend, "
        "2) Simplify the prompt, 3) Check codeagent-wrapper logs",
    ),
    (
        "completed without agent_message output",
        "No agent output",
        "Backend completed but produced no output. Try: 1) Use a different model, "
        "2) Check if the model supports structured output, 3) Simplify the task",
    ),
)


def _diagnose_backend_error(output: str) -> str | None:
    """Diagnose known backend error patterns and return suggested fix.

    Args:
        output: Combined stdout/stderr from codeagent-wrapper

    Returns:
        Diagnosis string with title and suggestion, or None if no match.
    """
    for pattern, title, suggestion in KNOWN_BACKEND_ERROR_PATTERNS:
        if pattern in output:
            return f"[{title}] {suggestion}"
    return None


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from backend output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _summarize_backend_output(stderr: str, stdout: str) -> str:
    """Build a short, readable summary from backend stdout/stderr."""
    raw_output = stderr or stdout
    if not raw_output.strip():
        return "(no output)"

    lines = [
        _strip_ansi(line).strip()
        for line in raw_output.splitlines()
        if _strip_ansi(line).strip()
    ]
    if not lines:
        return "(no output)"

    metadata_prefixes = (
        "[codeagent-wrapper]",
        "Backend:",
        "Command:",
        "PID:",
        "Log:",
        "Traceback (most recent call last):",
    )
    detail_markers = (
        "TypeError:",
        "ValueError:",
        "RuntimeError:",
        "Error:",
        "Exception:",
        "Failed to parse event",
        "completed without agent_message output",
        "Unexpected error:",
    )

    selected: list[str] = []
    for line in lines:
        if line.startswith(metadata_prefixes):
            continue
        if line.startswith("at ") or line.startswith("File "):
            continue
        if line.startswith("│") or line.startswith("└") or line.startswith("> File "):
            continue
        if any(marker in line for marker in detail_markers):
            selected.append(line)

    if not selected:
        selected = [
            line
            for line in lines
            if not line.startswith(metadata_prefixes)
            and not line.startswith("at ")
            and not line.startswith("File ")
        ]

    preview = " | ".join(selected[:3]).strip()
    if not preview:
        preview = lines[0]
    return preview[:500]


class CodeagentBackend:
    """基于 codeagent-wrapper 二进制的 agent 执行后端。"""

    @staticmethod
    def has_tmux_session(session_name: str) -> bool:
        """Check if tmux session exists.

        Args:
            session_name: Exact tmux session name to check

        Returns:
            True if session exists, False otherwise
        """
        from vibe3.agents.backends.async_launcher import has_tmux_session as _has

        return _has(session_name)

    @staticmethod
    def _build_prompt_file_content(prompt: str) -> str:
        """Apply configured global notice to the prompt file content."""
        notice = VibeConfig.get_defaults().agent_prompt.global_notice.strip()
        if not notice:
            return prompt
        return f"{notice}\n\n---\n\n{prompt}"

    @staticmethod
    def _prepare_prompt_file(prompt: str) -> Path:
        """Create temporary prompt file with global notice."""
        prompt_dir = Path.home() / ".codeagent" / "agents"
        prompt_dir.mkdir(parents=True, exist_ok=True)
        prompt_content = CodeagentBackend._build_prompt_file_content(prompt)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, dir=prompt_dir
        ) as f:
            f.write(prompt_content)
            return Path(f.name)

    @staticmethod
    def _sanitize_task_shell_meta(task: str) -> str:
        """Replace shell glob meta characters with safe equivalents.

        Shell glob patterns (*?[]{}) in task arguments may expand unexpectedly
        when passed through shell layers inside codeagent-wrapper. Replace them
        with visually similar but non-glob characters to prevent expansion.

        Args:
            task: Task string that may contain shell meta characters

        Returns:
            Sanitized task string safe for command-line arguments

        Example:
            "回收 worktree（do/*）" → "回收 worktree（do/×）"
        """
        # Replace glob meta characters with visually similar safe equivalents
        replacements = {
            "*": "×",  # Asterisk → multiplication sign (looks similar)
            "?": "？",  # Question mark → full-width question mark
            "[": "【",  # Left bracket → full-width lenticular bracket
            "]": "】",  # Right bracket → full-width lenticular bracket
            "{": "｛",  # Left brace → full-width brace
            "}": "｝",  # Right brace → full-width brace
        }
        result = task
        for meta, safe in replacements.items():
            result = result.replace(meta, safe)
        return result

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
            # Default fallback: vibe-reviewer for code review tasks
            command.extend(["--agent", "vibe-reviewer"])

        # Skip interactive permission prompts so worktree agents can access
        # shared paths (e.g. main/.git/vibe3/handoff/) without being blocked.
        command.append("--skip-permissions")

        command.extend(["--prompt-file", prompt_file_path])

        # Sanitize task for shell meta characters before adding to command
        safe_task = CodeagentBackend._sanitize_task_shell_meta(task) if task else None

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
    ) -> tuple[subprocess.CompletedProcess[str], "Path | None"]:
        """Run subprocess with streaming output and capture return value.

        Returns (result, sync_log_path) — sync_log_path is None when no
        issue number is found in the cwd/args (e.g. ad-hoc runs).
        Streams stdout/stderr to live console while accumulating for return value.
        """
        import threading

        def _stream_reader(
            stream: Any,
            accumulator: list[str],
            output_file: Any,
        ) -> None:
            """Read from stream in chunks, accumulate, and write to output.

            Filters out uv installation noise by waiting for "-> " marker.
            All output before the marker is discarded; everything from the
            first marker onwards is shown and captured. If no marker is found,
            outputs everything (backward compatibility).
            """
            import codecs

            found_marker = False
            pre_marker_buffer = ""
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

            while True:
                try:
                    # Use read1 for real-time streaming (returns whatever is available)
                    if hasattr(stream, "read1"):
                        chunk_bytes = stream.read1(4096)
                    else:
                        chunk_bytes = stream.read(1)
                except (OSError, ValueError):
                    break

                if not chunk_bytes:
                    break

                chunk = decoder.decode(chunk_bytes)
                if not chunk:
                    continue

                if not found_marker:
                    pre_marker_buffer += chunk
                    if "-> " in pre_marker_buffer:
                        found_marker = True
                        # Find the first instance of the marker
                        marker_pos = pre_marker_buffer.find("-> ")
                        # Output everything from the marker onwards
                        good_stuff = pre_marker_buffer[marker_pos:]
                        accumulator.append(good_stuff)
                        output_file.write(good_stuff)
                        output_file.flush()
                        pre_marker_buffer = ""  # Clear buffer
                else:
                    # After marker found, output everything immediately
                    accumulator.append(chunk)
                    output_file.write(chunk)
                    output_file.flush()

            # Finalize decoding (handles any trailing bytes)
            final_chunk = decoder.decode(b"", final=True)
            if final_chunk:
                if not found_marker:
                    pre_marker_buffer += final_chunk
                else:
                    accumulator.append(final_chunk)
                    output_file.write(final_chunk)
                    output_file.flush()

            # Fallback if no marker was found: output everything we buffered
            if not found_marker and pre_marker_buffer:
                accumulator.append(pre_marker_buffer)
                output_file.write(pre_marker_buffer)
                output_file.flush()

        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        proc = subprocess.Popen(
            command,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # Unbuffered binary pipes
            text=False,
        )

        stdout_thread = threading.Thread(
            target=_stream_reader,
            args=(proc.stdout, stdout_chunks, sys.stdout),
        )
        stderr_thread = threading.Thread(
            target=_stream_reader,
            args=(proc.stderr, stderr_chunks, sys.stderr),
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

        # Save complete wrapper logs for diagnostics (sync execution)
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

        prompt_file_path = self._prepare_prompt_file(prompt)
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
                    # Show complete prompt content (including global_notice)
                    complete_prompt = self._build_prompt_file_content(prompt)
                    print(complete_prompt)
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
                    result, wrapper_log_path = self._run_subprocess(
                        retry_command,
                        project_root=project_root,
                        timeout_seconds=options.timeout_seconds,
                        role=role,
                    )

            except FileNotFoundError:
                raise AgentExecutionError(
                    f"codeagent-wrapper not found at {DEFAULT_WRAPPER_PATH}. "
                    "Please ensure it is installed and accessible.",
                    log_path=wrapper_log_path,
                ) from None
            except subprocess.TimeoutExpired:
                raise AgentExecutionError(
                    f"codeagent-wrapper timed out after {options.timeout_seconds}s. "
                    "Consider increasing the timeout or splitting the review scope.",
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
                diagnosis = _diagnose_backend_error(combined_output)
                stderr_preview = _summarize_backend_output(
                    agent_result.stderr, agent_result.stdout
                )

                error_msg = (
                    f"codeagent-wrapper failed with exit code "
                    f"{agent_result.exit_code}:\n{stderr_preview}"
                )
                if diagnosis:
                    error_msg += f"\n\n{diagnosis}"

                raise AgentExecutionError(error_msg, log_path=wrapper_log_path)

            return agent_result
        finally:
            if prompt_file_path:
                Path(prompt_file_path).unlink(missing_ok=True)

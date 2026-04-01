import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final, cast

from loguru import logger

from vibe3.exceptions import AgentExecutionError
from vibe3.models.review_runner import AgentOptions, AgentResult

# Default wrapper path
DEFAULT_WRAPPER_PATH: Final[Path] = (
    Path.home() / ".claude" / "bin" / "codeagent-wrapper"
)

# Path to codeagent models config
MODELS_JSON_PATH: Final[Path] = Path.home() / ".codeagent" / "models.json"


def sync_models_json(options: AgentOptions) -> None:
    """Sync effective backend/model to ~/.codeagent/models.json.

    In backend mode: updates default_backend (and default_model if specified),
    so codeagent-wrapper uses vibe3's config instead of whatever is in the file.

    In agent preset mode: no-op — codeagent manages the preset's backend/model
    from its own config.
    """
    if not options.backend:
        return  # agent preset mode — codeagent reads preset config itself

    try:
        existing: dict[str, Any] = {}
        if MODELS_JSON_PATH.exists():
            existing = json.loads(MODELS_JSON_PATH.read_text())
    except Exception as exc:
        logger.bind(domain="review_runner").warning(
            f"Failed to read models.json, will overwrite: {exc}"
        )
        existing = {}

    existing["default_backend"] = options.backend
    if options.model:
        existing["default_model"] = options.model

    try:
        MODELS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        MODELS_JSON_PATH.write_text(json.dumps(existing, indent=2))
        logger.bind(
            domain="review_runner",
            backend=options.backend,
            model=options.model,
        ).debug("Synced models.json")
    except Exception as exc:
        logger.bind(domain="review_runner").warning(
            f"Failed to write models.json: {exc}"
        )


def extract_session_id(stdout: str) -> str | None:
    """Extract session ID from codeagent-wrapper output.

    Pattern:
        SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8
    """
    if not stdout:
        return None
    match = re.search(r"SESSION_ID:\s*([a-f0-9-]{36})", stdout)
    return match.group(1) if match else None


class CodeagentBackend:
    """基于 codeagent-wrapper 二进制的 agent 执行后端。"""

    def run(
        self,
        prompt: str,
        options: AgentOptions,
        task: str | None = None,
        dry_run: bool = False,
        session_id: str | None = None,
    ) -> AgentResult:
        """运行 codeagent-wrapper。"""
        # Ensure codeagent uses vibe3's backend/model config
        sync_models_json(options)

        project_root = os.getcwd()
        wrapper_path = DEFAULT_WRAPPER_PATH
        prompt_dir = Path.home() / ".codeagent" / "agents"
        prompt_dir.mkdir(parents=True, exist_ok=True)

        # Always write prompt file content, even in resume mode
        # This ensures the correct AST information is available
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, dir=prompt_dir
        ) as prompt_file:
            prompt_file.write(prompt)
            prompt_file_path = prompt_file.name

        try:
            # Build command: wrapper --agent <agent> --prompt-file <file> [task]
            command: list[str] = [str(wrapper_path)]

            # Add agent preset or backend+model (for both new and resume sessions)
            if options.agent:
                command.extend(["--agent", options.agent])
            elif options.backend:
                command.extend(["--backend", options.backend])
                if options.model:
                    command.extend(["--model", options.model])
            else:
                command.extend(["--agent", "code-reviewer"])

            # Add prompt file (always needed for correct AST context)
            command.extend(["--prompt-file", cast(str, prompt_file_path)])

            # `--worktree` only applies to new session execution.
            if options.worktree and not session_id:
                command.append("--worktree")

            if session_id:
                # Resume mode with session_id
                command.append("resume")
                command.append(cast(str, session_id))
                if task:
                    command.append(task)
                else:
                    command.append("continue")
            else:
                # New session mode: wrapper --agent <agent> --prompt-file <file> [task]
                if task:
                    command.append(task)

            # Dry-run mode: print command and prompt
            if dry_run:
                print("=== Command ===")
                print(" ".join(command))
                if prompt_file_path:
                    print(f"\n=== Prompt File: {prompt_file_path} ===")
                    print(prompt)
                if task:
                    print(f"\n=== Task ===\n{task}")
                print("\n=== End ===")
                # Return a mock success result
                return AgentResult(exit_code=0, stdout="[dry-run]", stderr="")

            try:
                # Run wrapper and capture output for parsing and persistence.
                result = subprocess.run(
                    command,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=options.timeout_seconds,
                    check=False,
                )

            except FileNotFoundError:
                raise AgentExecutionError(
                    f"codeagent-wrapper not found at {wrapper_path}. "
                    "Please ensure it is installed and accessible."
                ) from None
            except subprocess.TimeoutExpired:
                raise AgentExecutionError(
                    f"codeagent-wrapper timed out after {options.timeout_seconds}s. "
                    "Consider increasing the timeout or splitting the review scope."
                ) from None

            # Print output for visibility
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
            # Clean up temporary file
            if prompt_file_path:
                Path(prompt_file_path).unlink(missing_ok=True)

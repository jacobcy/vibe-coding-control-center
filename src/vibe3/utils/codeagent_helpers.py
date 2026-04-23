"""Helper functions for Codeagent backend."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any, Final

from loguru import logger

from vibe3.config.settings import VibeConfig

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


def diagnose_backend_error(output: str) -> str | None:
    """Diagnose known backend error patterns and return suggested fix."""
    for pattern, title, suggestion in KNOWN_BACKEND_ERROR_PATTERNS:
        if pattern in output:
            return f"[{title}] {suggestion}"
    return None


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from backend output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def summarize_backend_output(stderr: str, stdout: str) -> str:
    """Build a short, readable summary from backend stdout/stderr."""
    raw_output = stderr or stdout
    if not raw_output.strip():
        return "(no output)"

    lines = [
        strip_ansi(line).strip()
        for line in raw_output.splitlines()
        if strip_ansi(line).strip()
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


def build_prompt_file_content(prompt: str, include_global_notice: bool = True) -> str:
    """Apply configured global notice to the prompt file content."""
    if not include_global_notice:
        return prompt
    notice = VibeConfig.get_defaults().agent_prompt.global_notice.strip()
    if not notice:
        return prompt
    return f"{notice}\n\n---\n\n{prompt}"


def prepare_prompt_file(prompt: str, include_global_notice: bool = True) -> Path:
    """Create temporary prompt file with global notice."""
    prompt_dir = Path.home() / ".codeagent" / "agents"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_content = build_prompt_file_content(
        prompt, include_global_notice=include_global_notice
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=prompt_dir
    ) as f:
        f.write(prompt_content)
        return Path(f.name)


def sanitize_task_shell_meta(task: str) -> str:
    """Replace shell glob meta characters with safe equivalents."""
    replacements = {
        "*": "×",
        "?": "？",
        "[": "【",
        "]": "】",
        "{": "｛",
        "}": "｝",
    }
    result = task
    for meta, safe in replacements.items():
        result = result.replace(meta, safe)
    return result


def stream_reader(
    stream: Any,
    accumulator: list[str],
    output_file: Any,
    proc: Any,
) -> None:
    """Read from stream in chunks, accumulate, and write to output."""
    import codecs

    recent_text = ""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    while True:
        try:
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

        recent_text += chunk
        if len(recent_text) > 4096:
            recent_text = recent_text[-2048:]

        is_rate_limit = "429" in recent_text and (
            "ServerOverloaded" in recent_text
            or "TooManyRequests" in recent_text
            or "rate_limit" in recent_text
        )
        if is_rate_limit:
            logger.warning(
                "FATAL: Detected 429 Rate Limit error. "
                "Aborting subprocess to prevent infinite retry loop."
            )
            proc.kill()
            break

        if any(
            noise in chunk
            for noise in (
                "[2m",
                "Uninstalled",
                "Installing wheels",
                "Installed 1 package",
                "░",
                "█",
            )
        ):
            continue

        accumulator.append(chunk)
        output_file.write(chunk)
        output_file.flush()

    final_chunk = decoder.decode(b"", final=True)
    if final_chunk:
        if not any(
            noise in final_chunk
            for noise in (
                "[2m",
                "Uninstalled",
                "Installing wheels",
                "Installed 1 package",
                "░",
                "█",
            )
        ):
            accumulator.append(final_chunk)
            output_file.write(final_chunk)
            output_file.flush()

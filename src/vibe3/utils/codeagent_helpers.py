"""Helper functions for Codeagent backend."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from loguru import logger

# Delayed import to avoid utils → config circular dependency
# from vibe3.config import VibeConfig

if TYPE_CHECKING:
    from vibe3.config import VibeConfig


def get_vibe_config() -> "VibeConfig":
    """Get VibeConfig with delayed import."""
    from vibe3.config import VibeConfig

    return VibeConfig.get_defaults()


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
        "Backend completed but produced no output. This often indicates prompt size "
        "issue (stdin mode threshold ~800 chars). Try: 1) Check prompt-recipes.yaml "
        "for large kind:file sources, 2) Use kind:literal + Read instruction instead, "
        "3) Use a different model",
    ),
)


def diagnose_backend_error(output: str) -> str | None:
    """Diagnose known backend error patterns and return suggested fix."""
    for pattern, title, suggestion in KNOWN_BACKEND_ERROR_PATTERNS:
        if pattern in output:
            return f"[{title}] {suggestion}"
    return None


def diagnose_prompt_size_issue(prompt_len: int, backend: str, model: str) -> str | None:
    """Diagnose if prompt size exceeds stdin-mode threshold.

    codeagent-wrapper enters stdin mode when prompt exceeds ~800 chars,
    which can cause parsing failures. Returns diagnostic message if size
    exceeds threshold, None otherwise.

    Args:
        prompt_len: Length of the prompt in characters
        backend: Backend name (e.g., "openai", "anthropic")
        model: Model name (e.g., "claude-3-5-sonnet")

    Returns:
        Diagnostic message if prompt exceeds threshold, None otherwise
    """
    # codeagent-wrapper stdin mode threshold is approximately 800 characters
    stdin_mode_threshold = 800

    if prompt_len > stdin_mode_threshold:
        return (
            f"Prompt size ({prompt_len} chars) exceeds stdin-mode threshold "
            f"({stdin_mode_threshold} chars) for {backend}/{model}. "
            f"This may cause codeagent-wrapper to enter stdin mode and fail silently. "
            f"Consider using kind:literal + Read instruction in prompt-recipes.yaml "
            f"instead of kind:file for large files."
        )
    return None


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from backend output."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def summarize_backend_output(stderr: str, stdout: str) -> str:
    """Build a short, readable summary from backend stdout/stderr."""
    # Merge both streams to capture all error information
    # stderr contains wrapper metadata, stdout contains actual errors
    raw_output = f"{stderr}\n{stdout}" if stderr and stdout else stderr or stdout
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
        "CLAUDE_CODE_TMPDIR:",
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
    config = get_vibe_config()
    notice = config.agent_prompt.global_notice.strip()
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
    """Replace shell meta characters with safe equivalents.

    Covers both glob characters and special characters that trigger stdin mode
    in codeagent-wrapper (newline, backslash, quotes, backtick, dollar).
    """
    replacements = {
        # Shell glob characters
        "*": "×",
        "?": "？",
        "[": "【",
        "]": "】",
        "{": "｛",
        "}": "｝",
        # Shell special characters (trigger stdin mode)
        "\\": "＼",  # Fullwidth backslash
        '"': "＂",  # Fullwidth double quote
        "'": "＇",  # Fullwidth single quote
        "`": "｀",  # Fullwidth backtick
        "$": "＄",  # Fullwidth dollar sign
        "\n": " ",  # Newline -> space
    }
    result = task
    for meta, safe in replacements.items():
        result = result.replace(meta, safe)
    return result


def sanitize_prompt_for_display(text: str) -> str:
    """Mask sensitive patterns in prompt text before debug logging.

    Applies regex substitutions for common secret formats (API keys, tokens,
    access keys) while preserving prefixes to maintain debugging utility.
    """
    # OpenAI/API keys: sk-proj-..., sk-...
    # Match sk-proj- or sk- as the prefix, followed by at least 20 chars
    text = re.sub(
        r"(sk-proj-|sk-)[A-Za-z0-9\-_]{20,}",
        r"\1***REDACTED***",
        text,
    )

    # AWS access keys: AKIA...
    text = re.sub(
        r"(AKIA)[A-Z0-9]{16}",
        r"\1***REDACTED***",
        text,
    )

    # GitHub tokens: ghp_..., gho_..., ghu_..., ghs_..., ghr_...
    text = re.sub(
        r"(gh[pousr]_)[A-Za-z0-9]{36,}",
        r"\1***REDACTED***",
        text,
    )

    # Generic key/value pairs: api_key: xxx, secret_key=xxx
    text = re.sub(
        r"(?i)(api_key|apikey|secret_key|access_token|auth_token|private_key)\s*[:=]\s*\S+",
        r"\1***REDACTED***",
        text,
    )

    # Bearer tokens: Bearer eyJ...
    text = re.sub(
        r"(Bearer\s+)[A-Za-z0-9\-_\.]{20,}",
        r"\1***REDACTED***",
        text,
    )

    return text


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

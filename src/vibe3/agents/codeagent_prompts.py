"""Config-dependent prompt helpers for Codeagent backend.

Extracted from vibe3.utils.codeagent_helpers to break the
utils → config circular dependency (config is layer 6, utils is layer 6;
this file lives in agents which is layer 4, allowed to depend on config).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.config import VibeConfig


def get_vibe_config() -> "VibeConfig":
    """Get VibeConfig with delayed import."""
    from vibe3.config import VibeConfig

    return VibeConfig.get_defaults()


def build_prompt_file_content(prompt: str, include_global_notice: bool = True) -> str:
    """Apply configured global notice to the prompt file content."""
    if not include_global_notice:
        return prompt
    config = get_vibe_config()
    notice = config.agent_prompt.global_notice.strip()
    if not notice:
        return prompt
    return f"{notice}\n\n---\n\n{prompt}"


def prepare_prompt_file(
    prompt: str, include_global_notice: bool = True
) -> tuple[Path, str]:
    """Create temporary prompt file with global notice.

    Returns:
        tuple of (file_path, prompt_content) to avoid caller needing to
        call build_prompt_file_content separately for diagnostics.
    """
    prompt_dir = Path.home() / ".codeagent" / "agents"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_content = build_prompt_file_content(
        prompt, include_global_notice=include_global_notice
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=prompt_dir
    ) as f:
        f.write(prompt_content)
        return Path(f.name), prompt_content

"""Shared prompt routing metadata for role sync execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

PromptContextMode = Literal["bootstrap", "resume"]


@dataclass(frozen=True)
class PromptMeta:
    """Derived routing metadata for sync prompt assembly."""

    prompt_mode: str
    context_mode: PromptContextMode
    session_id: str | None
    refs: dict[str, str]

    @property
    def include_global_notice(self) -> bool:
        return not (self.prompt_mode == "retry" and self.context_mode == "resume")

    @property
    def fallback_context_mode(self) -> PromptContextMode | None:
        if self.context_mode == "resume":
            return "bootstrap"
        return None

    @property
    def session_reused(self) -> bool:
        return bool(self.session_id and self.context_mode == "resume")

    def summary(self, sections: list[str]) -> dict[str, object]:
        result: dict[str, object] = {
            "prompt_mode": self.prompt_mode,
            "context_mode": self.context_mode,
            "session_reused": self.session_reused,
            "session_id": self.session_id or "",
            "sections": sections,
            "refs": self.refs,
        }
        if self.fallback_context_mode is not None:
            result["fallback_context_mode"] = self.fallback_context_mode
        return result


def collect_prompt_refs(
    flow_state: Mapping[str, object] | None,
    *,
    ref_keys: tuple[str, ...],
) -> dict[str, str]:
    """Collect authoritative refs from flow state."""
    refs: dict[str, str] = {}
    if not flow_state:
        return refs

    for key in ref_keys:
        value = flow_state.get(key)
        if value:
            refs[key] = str(value)
    return refs


def build_prompt_meta(
    flow_state: Mapping[str, object] | None,
    *,
    ref_keys: tuple[str, ...],
    retry_ref_keys: tuple[str, ...],
    session_id: str | None,
    default_mode: str,
    retry_mode: str = "retry",
) -> PromptMeta:
    """Derive prompt routing metadata from refs + session state."""
    refs = collect_prompt_refs(flow_state, ref_keys=ref_keys)
    prompt_mode = (
        retry_mode if any(key in refs for key in retry_ref_keys) else default_mode
    )
    context_mode: PromptContextMode = (
        "resume" if prompt_mode == retry_mode and session_id else "bootstrap"
    )
    return PromptMeta(
        prompt_mode=prompt_mode,
        context_mode=context_mode,
        session_id=session_id,
        refs=refs,
    )

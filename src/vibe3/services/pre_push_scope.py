"""Helpers for resolving pre-push review scope."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass

ZERO_SHA = "0" * 40
DEFAULT_BASE_REF = "origin/main"


@dataclass(frozen=True)
class PrePushReviewScope:
    """Resolved review scope for the current push."""

    local_ref: str
    remote_ref: str
    head_ref: str
    base_ref: str
    is_incremental: bool
    summary: str


def resolve_pre_push_scope(
    push_stdin: str, default_base_ref: str = DEFAULT_BASE_REF
) -> PrePushReviewScope:
    """Resolve the diff scope that should be reviewed for a pre-push hook."""

    for raw_line in push_stdin.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 4:
            continue

        local_ref, local_sha, remote_ref, remote_sha = parts

        if local_sha == ZERO_SHA:
            continue

        if remote_sha != ZERO_SHA:
            return PrePushReviewScope(
                local_ref=local_ref,
                remote_ref=remote_ref,
                head_ref=local_sha,
                base_ref=remote_sha,
                is_incremental=True,
                summary=(
                    "this push only: "
                    f"{remote_ref}@{remote_sha[:12]}..{local_sha[:12]}"
                ),
            )

        return PrePushReviewScope(
            local_ref=local_ref,
            remote_ref=remote_ref,
            head_ref=local_sha,
            base_ref=default_base_ref,
            is_incremental=False,
            summary=(
                "new branch push: "
                f"{local_ref}@{local_sha[:12]} against {default_base_ref}"
            ),
        )

    return PrePushReviewScope(
        local_ref="HEAD",
        remote_ref="HEAD",
        head_ref="HEAD",
        base_ref=default_base_ref,
        is_incremental=False,
        summary=f"fallback scope: HEAD against {default_base_ref}",
    )


def main() -> None:
    """Resolve scope from stdin and print JSON for shell hooks."""
    scope = resolve_pre_push_scope(sys.stdin.read())
    print(json.dumps(asdict(scope)))


if __name__ == "__main__":
    main()

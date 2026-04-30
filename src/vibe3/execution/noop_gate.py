"""Unified no-op gate: blocks when agent fails to change issue state."""

from loguru import logger

from vibe3.agents.models import ExecutionRole
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.role_policy import get_role_block_function


def extract_state_label(issue_payload: dict[str, object]) -> str | None:
    """Extract state/ label from GitHub issue payload."""
    labels = issue_payload.get("labels")
    if not isinstance(labels, list):
        return None
    for label in labels:
        if not isinstance(label, dict):
            continue
        name = label.get("name")
        if isinstance(name, str) and name.startswith("state/"):
            return name
    return None


def apply_unified_noop_gate(
    *,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    role: ExecutionRole,
    before_state_label: str | None,
    repo: str | None = None,
    required_ref_key: str | None = None,
    flow_state: dict | None = None,
) -> None:
    """Apply the single hard no-op gate after agent completion.

    Reads state labels from GitHub issue (remote source of truth).

    Rules:
    - if the issue has no state/ label, skip (not managed by state machine)
    - if required_ref is missing (for worker roles), block
    - if the agent did not change the issue's state/ label, block
    - if the agent changed the issue's state/ label, record and pass
    """
    from vibe3.utils.constants import (
        EVENT_CANNOT_VERIFY_REMOTE_STATE,
        EVENT_REQUIRED_REF_MISSING,
        EVENT_STATE_TRANSITIONED,
        EVENT_STATE_UNCHANGED,
    )

    # Resolve role-specific block function (used in all failure paths)
    _block_fn = get_role_block_function(role)

    # Skip no-op gate if issue has no state/ label (not managed by state machine)
    if not before_state_label:
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).info("No-op gate SKIP: issue has no state/ label")
        return

    # Read after_state from GitHub issue (remote source of truth)
    try:
        from vibe3.clients.github_client import GitHubClient

        issue_payload = GitHubClient().view_issue(issue_number, repo=repo)
    except Exception as exc:
        # Fail-safe: if we cannot verify state, block rather than skip
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).warning(f"No-op gate BLOCK: cannot read issue state: {exc}")
        store.add_event(
            branch,
            EVENT_CANNOT_VERIFY_REMOTE_STATE,
            actor,
            detail=f"Gate cannot verify state (GitHub read failed): {exc}",
            refs={
                "state": str(before_state_label or ""),
                "issue": str(issue_number),
                "error": str(exc),
            },
        )
        _block_fn(
            issue_number=issue_number,
            repo=repo,
            reason=f"cannot verify remote state: {exc}",
            actor=actor,
        )
        return

    if not isinstance(issue_payload, dict):
        # Fail-safe: malformed response, block
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).warning("No-op gate BLOCK: GitHub returned non-dict payload")
        store.add_event(
            branch,
            EVENT_CANNOT_VERIFY_REMOTE_STATE,
            actor,
            detail="Gate cannot verify state (malformed GitHub response)",
            refs={
                "state": str(before_state_label or ""),
                "issue": str(issue_number),
            },
        )
        _block_fn(
            issue_number=issue_number,
            repo=repo,
            reason="cannot verify remote state: malformed GitHub response",
            actor=actor,
        )
        return

    after_state_label = extract_state_label(issue_payload)

    # Fail-safe: if state label disappeared after agent, block
    if not after_state_label:
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).warning(
            f"No-op gate BLOCK: state label disappeared after {role} "
            f"(was {before_state_label})"
        )
        store.add_event(
            branch,
            EVENT_STATE_UNCHANGED,
            actor,
            detail=(
                f"State label disappeared after {role}: "
                f"was {before_state_label}, now missing"
            ),
            refs={
                "before_state": str(before_state_label or ""),
                "issue": str(issue_number),
            },
        )
        _block_fn(
            issue_number=issue_number,
            repo=repo,
            reason="state label disappeared after agent",
            actor=actor,
        )
        return

    # --- NEW: required_ref check ---
    # Only check ref for worker roles (planner/executor/reviewer).
    # Manager skips this check (required_ref_key is None).
    if required_ref_key is not None and flow_state is not None:
        ref_value = flow_state.get(required_ref_key)
        if not ref_value:
            logger.bind(
                domain="codeagent",
                role=role,
                issue_number=issue_number,
                branch=branch,
            ).warning(
                f"No-op gate BLOCK: required ref {required_ref_key} "
                f"missing after {role}"
            )
            store.add_event(
                branch,
                EVENT_REQUIRED_REF_MISSING,
                actor,
                detail=(
                    f"Required ref {required_ref_key} missing after {role}: "
                    f"state was {before_state_label}"
                ),
                refs={
                    "before_state": str(before_state_label or ""),
                    "issue": str(issue_number),
                    "required_ref": required_ref_key,
                },
            )
            _block_fn(
                issue_number=issue_number,
                repo=repo,
                reason=f"required ref missing: {required_ref_key}",
                actor=actor,
            )
            return

    if before_state_label == after_state_label:
        state_desc = before_state_label or "(no state)"
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).warning(
            f"No-op gate BLOCK: state unchanged after {role} " f"(still {state_desc})"
        )
        store.add_event(
            branch,
            EVENT_STATE_UNCHANGED,
            actor,
            detail=f"State unchanged after {role}: still {state_desc}",
            refs={
                "state": str(before_state_label or ""),
                "issue": str(issue_number),
            },
        )
        _block_fn(
            issue_number=issue_number,
            repo=repo,
            reason="state unchanged",
            actor=actor,
        )
        return

    logger.bind(
        domain="codeagent",
        role=role,
        issue_number=issue_number,
        branch=branch,
    ).info(
        f"No-op gate PASS: state changed {before_state_label} -> "
        f"{after_state_label}"
    )
    store.add_event(
        branch,
        EVENT_STATE_TRANSITIONED,
        actor,
        detail=f"State changed: {before_state_label} -> {after_state_label}",
        refs={
            "before_state": str(before_state_label or ""),
            "after_state": after_state_label,
            "issue": str(issue_number),
        },
    )

"""Unified no-op gate: blocks when agent fails to change issue state."""

from loguru import logger

from vibe3.agents.models import ExecutionRole
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.role_policy import get_role_block_function

# Loop prevention constants
SINGLE_STEP_LIMIT = 3  # Max occurrences of same transition pair
TRANSITION_LIMIT_SOFT = 10  # Standard flow limit
TRANSITION_LIMIT_HARD = 20  # Hard limit with tolerance


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
        EVENT_TRANSITION_COUNT_EXCEEDED,
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

    # --- NEW: Single-step transition limit check ---
    # Check if this specific (from_state, to_state) pair has occurred >= 3 times
    if (
        before_state_label
        and after_state_label
        and before_state_label != after_state_label
        and hasattr(store, "db_path")
        and hasattr(store, "count_specific_pair")
    ):
        import sqlite3

        try:
            with sqlite3.connect(store.db_path) as conn:
                pair_count = store.count_specific_pair(
                    conn=conn,
                    branch=branch,
                    from_state=before_state_label,
                    to_state=after_state_label,
                )

            # Check single-step limit BEFORE recording this transition
            if pair_count >= SINGLE_STEP_LIMIT:
                logger.bind(
                    domain="codeagent",
                    role=role,
                    issue_number=issue_number,
                    branch=branch,
                ).warning(
                    f"No-op gate BLOCK: single-step limit exceeded "
                    f"({before_state_label} -> {after_state_label} "
                    f"occurred {pair_count} times, limit is {SINGLE_STEP_LIMIT})"
                )
                store.add_event(
                    branch,
                    EVENT_TRANSITION_COUNT_EXCEEDED,
                    actor,
                    detail=(
                        f"Single-step limit exceeded: "
                        f"{before_state_label} -> {after_state_label} "
                        f"occurred {pair_count} times (limit: {SINGLE_STEP_LIMIT}). "
                        f"Possible infinite loop on this pair."
                    ),
                    refs={
                        "from_state": str(before_state_label or ""),
                        "to_state": str(after_state_label or ""),
                        "pair_count": str(pair_count),
                        "single_step_limit": str(SINGLE_STEP_LIMIT),
                        "issue": str(issue_number),
                    },
                )
                _block_fn(
                    issue_number=issue_number,
                    repo=repo,
                    reason=(
                        f"single-step limit exceeded: "
                        f"{before_state_label} -> {after_state_label} "
                        f"({pair_count} times >= {SINGLE_STEP_LIMIT})"
                    ),
                    actor=actor,
                )
                return
        except sqlite3.Error as e:
            # Fail-safe: log and skip single-step check on DB errors
            logger.bind(
                domain="codeagent",
                role=role,
                issue_number=issue_number,
                branch=branch,
            ).warning(f"Single-step transition check skipped: database error ({e})")

    # --- NEW: State transition count check ---
    # Check hard limit BEFORE incrementing
    if flow_state is not None:
        current_count = flow_state.get("transition_count", 0)
        new_count = current_count + 1

        # Check hard limit
        if new_count >= TRANSITION_LIMIT_HARD:
            logger.bind(
                domain="codeagent",
                role=role,
                issue_number=issue_number,
                branch=branch,
            ).warning(
                f"No-op gate BLOCK: transition count exceeded hard limit "
                f"({new_count} >= {TRANSITION_LIMIT_HARD})"
            )
            store.add_event(
                branch,
                EVENT_TRANSITION_COUNT_EXCEEDED,
                actor,
                detail=(
                    f"Transition count exceeded hard limit: {new_count} >= "
                    f"{TRANSITION_LIMIT_HARD}. Possible infinite loop."
                ),
                refs={
                    "transition_count": str(new_count),
                    "limit": str(TRANSITION_LIMIT_HARD),
                    "issue": str(issue_number),
                },
            )
            _block_fn(
                issue_number=issue_number,
                repo=repo,
                reason=(
                    f"transition count exceeded: {new_count} >= "
                    f"{TRANSITION_LIMIT_HARD}"
                ),
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

    # Record this transition in transition_history for single-step tracking
    if (
        before_state_label
        and after_state_label
        and before_state_label != after_state_label
        and hasattr(store, "db_path")
        and hasattr(store, "record_transition")
    ):
        import sqlite3

        try:
            with sqlite3.connect(store.db_path) as conn:
                # Get the event_id of the state_transitioned event we just added
                cursor = conn.cursor()
                row = cursor.execute(
                    """
                    SELECT id FROM flow_events
                    WHERE branch = ? AND event_type = 'state_transitioned'
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (branch,),
                ).fetchone()

                event_id = row[0] if row else None

                store.record_transition(
                    conn=conn,
                    branch=branch,
                    from_state=before_state_label,
                    to_state=after_state_label,
                    actor=actor,
                    event_id=event_id,
                )
                conn.commit()
        except sqlite3.Error as e:
            # Fail-safe: log and skip recording on DB errors
            logger.bind(
                domain="codeagent",
                role=role,
                issue_number=issue_number,
                branch=branch,
            ).warning(f"Transition recording skipped: database error ({e})")

    # Increment transition count AFTER confirming state change
    if flow_state is not None and isinstance(flow_state, dict):
        current_count = flow_state.get("transition_count", 0)
        new_count = current_count + 1
        flow_state["transition_count"] = new_count

        # Log warning if approaching hard limit (after confirming transition)
        if new_count >= TRANSITION_LIMIT_SOFT:
            logger.bind(
                domain="codeagent",
                role=role,
                issue_number=issue_number,
                branch=branch,
            ).warning(
                f"Transition count approaching hard limit: {new_count} "
                f"(soft: {TRANSITION_LIMIT_SOFT}, hard: {TRANSITION_LIMIT_HARD})"
            )

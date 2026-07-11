"""Unified no-op gate: blocks when agent fails to change issue state."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from loguru import logger

from vibe3.agents import ExecutionRole
from vibe3.clients import SQLiteClient
from vibe3.config import get_role_output_contract
from vibe3.execution.publish_completion import PublishPRRefCompensationService
from vibe3.models import VerdictRecord, VerdictValue
from vibe3.services.flow import TransitionRecorder
from vibe3.services.shared import get_role_block_function

if TYPE_CHECKING:
    from vibe3.services.protocols import FlowQueryProtocol


def _extract_latest_verdict(flow_state: dict | None) -> VerdictValue | None:
    if not flow_state:
        return None

    raw_verdict = flow_state.get("latest_verdict")
    if raw_verdict is None:
        return None
    if isinstance(raw_verdict, VerdictRecord):
        return cast(VerdictValue, raw_verdict.verdict)
    if isinstance(raw_verdict, dict):
        try:
            return cast(VerdictValue, VerdictRecord(**raw_verdict).verdict)
        except Exception:
            return None
    if isinstance(raw_verdict, str):
        try:
            return cast(VerdictValue, VerdictRecord(**json.loads(raw_verdict)).verdict)
        except Exception:
            return None
    return None


def apply_unified_noop_gate(
    *,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    role: ExecutionRole,
    before_state_label: str | None,
    before_state_labels: frozenset[str] | None = None,
    repo: str | None = None,
    flow_state: dict | None = None,
    tick_id: int = 0,
    before_issue_is_closed: bool = False,
    flow_service: "FlowQueryProtocol | None" = None,
    publish_mode: bool = False,
    before_open_pr_numbers: frozenset[int] | None = None,
    before_pr_ref: str | None = None,
    publish_completion: PublishPRRefCompensationService | None = None,
) -> None:
    """Apply the single hard no-op gate after agent completion.

    Rules:
    - if the issue has no state/ label, skip (not managed by state machine)
    - if the role's required_ref is missing from flow_state, block
    - if the role requires a verdict and latest_verdict is absent, block
    - if the agent did not change the issue's state/ label, block
    - if the agent changed the issue's state/ label, record and pass
    """
    from vibe3.execution.state_verification import StateVerificationService
    from vibe3.utils import (
        EVENT_REQUIRED_REF_MISSING,
        EVENT_STATE_TRANSITIONED,
        EVENT_STATE_UNCHANGED,
        EVENT_TRANSITION_COUNT_EXCEEDED,
    )

    _block_fn = get_role_block_function(role)
    _contract = get_role_output_contract(role)

    effective_before_labels = (
        before_state_labels
        if before_state_labels is not None
        else frozenset({before_state_label}) if before_state_label else frozenset()
    )
    if not effective_before_labels:
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).info("No-op gate SKIP: issue has no state/ label")
        return

    # Read the complete state-label set in one API call. A newly added label is
    # the transition target even when a stale, higher-priority label remains.
    verifier = StateVerificationService(store=store)
    after_state_labels, after_issue_is_closed = verifier.get_issue_state_labels(
        issue_number=issue_number,
        repo=repo,
        branch=branch,
        flow_state=flow_state,
        tick_id=tick_id,
    )
    from vibe3.services.shared import get_highest_priority_state

    added_state_labels = after_state_labels - effective_before_labels
    target_candidates = added_state_labels or after_state_labels
    after_state_label = get_highest_priority_state(list(target_candidates))
    if after_state_label is None and target_candidates:
        after_state_label = min(target_candidates)
    state_set_changed = effective_before_labels != after_state_labels

    # If the issue was open before agent execution but is now closed,
    # treat this as a meaningful terminal transition regardless of state label.
    if not before_issue_is_closed and after_issue_is_closed:
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).info(
            f"No-op gate PASS: issue #{issue_number} closed by {role} "
            "(terminal transition)"
        )
        store.add_event(
            branch,
            EVENT_STATE_TRANSITIONED,
            actor,
            detail=(f"Issue #{issue_number} closed by {role} (terminal transition)"),
            refs={
                "before_state": str(before_state_label or ""),
                "issue": str(issue_number),
            },
        )
        return

    if flow_state is not None:
        store.update_flow_state(
            branch,
            noop_gate_github_retry_count=0,
            noop_gate_malformed_retry_count=0,
        )
        flow_state["noop_gate_github_retry_count"] = 0
        flow_state["noop_gate_malformed_retry_count"] = 0

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
            flow_service=flow_service,
        )
        return

    record_from_state = before_state_label or get_highest_priority_state(
        list(effective_before_labels)
    )
    if state_set_changed and record_from_state and after_state_label:
        transition = TransitionRecorder(store).record_confirmed(
            branch=branch,
            from_state=record_from_state,
            to_state=after_state_label,
            actor=actor,
            issue_number=issue_number,
        )
        if transition.total_limit_reached or transition.pair_limit_reached:
            reason = (
                f"transition limit reached: total={transition.total_count}, "
                f"pair={transition.pair_count}"
            )
            store.add_event(
                branch,
                EVENT_TRANSITION_COUNT_EXCEEDED,
                actor,
                detail=reason,
                refs={
                    "from_state": record_from_state,
                    "to_state": after_state_label,
                    "transition_count": str(transition.total_count),
                    "pair_count": str(transition.pair_count),
                    "issue": str(issue_number),
                },
            )
            _block_fn(
                issue_number=issue_number,
                repo=repo,
                reason=reason,
                actor=actor,
                flow_service=flow_service,
            )
            return

    # --- Contract-driven output checks ---
    # Each role declares its required outputs in RoleOutputContract.
    # These checks run before the state-change check so that a missing
    # required output blocks even when the state label happened to change.

    if _contract.required_ref and flow_state is not None:
        ref_value = flow_state.get(_contract.required_ref)
        if not ref_value:
            logger.bind(
                domain="codeagent",
                role=role,
                issue_number=issue_number,
                branch=branch,
            ).warning(
                f"No-op gate BLOCK: required ref {_contract.required_ref} "
                f"missing after {role}"
            )
            store.add_event(
                branch,
                EVENT_REQUIRED_REF_MISSING,
                actor,
                detail=(
                    f"Required ref {_contract.required_ref} missing after {role}: "
                    f"state was {before_state_label}"
                ),
                refs={
                    "before_state": str(before_state_label or ""),
                    "issue": str(issue_number),
                    "required_ref": _contract.required_ref,
                },
            )
            _block_fn(
                issue_number=issue_number,
                repo=repo,
                reason=f"required ref missing: {_contract.required_ref}",
                actor=actor,
                flow_service=flow_service,
            )
            return

    if _contract.requires_verdict:
        latest_verdict = _extract_latest_verdict(flow_state)
        if latest_verdict is None:
            logger.bind(
                domain="codeagent",
                role=role,
                issue_number=issue_number,
                branch=branch,
            ).warning("No-op gate BLOCK: latest verdict missing after reviewer")
            store.add_event(
                branch,
                EVENT_REQUIRED_REF_MISSING,
                actor,
                detail=(
                    f"Latest verdict missing after {role}: "
                    f"state was {before_state_label}"
                ),
                refs={
                    "before_state": str(before_state_label or ""),
                    "issue": str(issue_number),
                    "required_ref": "latest_verdict",
                },
            )
            _block_fn(
                issue_number=issue_number,
                repo=repo,
                reason="latest verdict missing after reviewer",
                actor=actor,
                flow_service=flow_service,
            )
            return

    if not state_set_changed:
        publish_reason: str | None = None
        if publish_mode:
            if before_open_pr_numbers is None:
                publish_reason = "authoritative pre-publish PR snapshot unavailable"
            else:
                if publish_completion is None:
                    from vibe3.clients import GitHubClient
                    from vibe3.services.shared import LabelService

                    publish_completion = PublishPRRefCompensationService(
                        GitHubClient(),
                        LabelService(repo=repo),
                        TransitionRecorder(store),
                    )
                publish_result = publish_completion.try_complete(
                    issue_number=issue_number,
                    branch=branch,
                    before_state_labels=effective_before_labels,
                    before_open_pr_numbers=before_open_pr_numbers,
                    before_pr_ref=before_pr_ref,
                    actor=actor,
                )
                if publish_result.completed:
                    return
                publish_reason = publish_result.reason

        state_desc = before_state_label or "(no state)"
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).warning(
            f"No-op gate BLOCK: state unchanged after {role} (still {state_desc})"
        )
        store.add_event(
            branch,
            EVENT_STATE_UNCHANGED,
            actor,
            detail=(
                f"State unchanged after {role}: still {state_desc}"
                + (
                    f"; publish exception rejected: {publish_reason}"
                    if publish_reason
                    else ""
                )
            ),
            refs={
                "state": str(before_state_label or ""),
                "issue": str(issue_number),
            },
        )
        _block_fn(
            issue_number=issue_number,
            repo=repo,
            reason=(
                "state unchanged" + (f": {publish_reason}" if publish_reason else "")
            ),
            actor=actor,
            flow_service=flow_service,
        )
        return

    logger.bind(
        domain="codeagent",
        role=role,
        issue_number=issue_number,
        branch=branch,
    ).info(
        f"No-op gate PASS: state changed {before_state_label} -> {after_state_label}"
    )

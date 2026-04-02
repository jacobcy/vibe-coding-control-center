"""Master agent for issue triage."""

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from vibe3.agents.review_runner import DEFAULT_WRAPPER_PATH
from vibe3.models.review_runner import AgentOptions


@dataclass(frozen=True)
class TriageDecision:
    """Master agent triage decision.

    Actions:
    - close: Close the issue as not needed
    - triage: Valid feature/bug, ready for assignment
    - comment: Add comment requesting more information
    """

    action: str
    reason: str
    labels_to_add: list[str] | None = None
    comment_body: str | None = None

    def is_valid(self) -> bool:
        return self.action in ("close", "triage", "comment", "none")


def parse_triage_response(output: str) -> TriageDecision:
    """Parse master agent output into triage decision.

    Expected output format (JSON):
    {
        "action": "close|triage|comment|none",
        "reason": "explanation",
        "labels_to_add": ["status/triaged"],  # optional
        "comment_body": "text"  # optional
    }
    """
    try:
        data = json.loads(output)
        return TriageDecision(
            action=data.get("action", "none"),
            reason=data.get("reason", ""),
            labels_to_add=data.get("labels_to_add"),
            comment_body=data.get("comment_body"),
        )
    except json.JSONDecodeError:
        return TriageDecision(action="none", reason="Failed to parse response")


def build_master_prompt(issue: dict, repo: str) -> str:
    """Build prompt for master agent."""
    body = issue.get("body", "(no description)")
    return f"""# Issue Triage Task

Analyze this GitHub issue and decide: close, triage, or comment.

## Issue #{issue["number"]}: {issue["title"]}

{body}

## Decision Options

- **close**: Invalid, duplicate, or not relevant
- **triage**: Valid feature/bug, ready for development
- **comment**: Need more information
- **none**: Cannot determine, skip

## Output (JSON)

{{"action": "triage", "reason": "brief explanation"}}
"""


def run_master_agent(
    issue: dict,
    repo: str,
    options: AgentOptions,
    dry_run: bool = False,
) -> TriageDecision:
    """Run master agent to triage an issue.

    Args:
        issue: GitHub issue dict with number, title, body, etc.
        repo: Repository name (owner/repo)
        options: Agent configuration
        dry_run: If True, print command without executing

    Returns:
        TriageDecision with action to take
    """
    log = logger.bind(domain="orchestra", action="master", issue=issue["number"])

    prompt = build_master_prompt(issue, repo)

    if dry_run:
        log.info("Dry run, skipping master agent")
        return TriageDecision(action="none", reason="dry_run")

    command = [str(DEFAULT_WRAPPER_PATH)]
    if options.agent:
        command.extend(["--agent", options.agent])
    elif options.backend:
        command.extend(["--backend", options.backend])
        if options.model:
            command.extend(["--model", options.model])
    else:
        command.extend(["--agent", "master-controller"])

    command.append("--output-format")
    command.append("json")

    log.info(f"Running master agent: {' '.join(command)}")

    prompt_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix="master_prompt_", delete=False
        ) as f:
            f.write(prompt)
            prompt_path = f.name

        command.extend(["--prompt-file", prompt_path])

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=options.timeout_seconds,
        )

        if result.returncode != 0:
            log.error(f"Master agent failed: {result.stderr}")
            return TriageDecision(
                action="none", reason=f"agent_failed: {result.stderr}"
            )

        decision = parse_triage_response(result.stdout)
        log.info(f"Master agent decision: {decision.action} - {decision.reason}")
        return decision

    except subprocess.TimeoutExpired:
        log.error("Master agent timed out")
        return TriageDecision(action="none", reason="timeout")
    except Exception as e:
        log.error(f"Master agent error: {e}")
        return TriageDecision(action="none", reason=str(e))
    finally:
        if prompt_path:
            Path(prompt_path).unlink(missing_ok=True)

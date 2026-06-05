"""GitHub client PR read operations."""

import json
import re
import subprocess
from typing import Any

from loguru import logger

# public-api: pending upstream export
from vibe3.models.pr import CICheck, PRMetadata, PRResponse, PRState

_ACTIONS_RUN_LINK_RE = re.compile(
    r"actions/runs/(?P<run_id>\d+)(?:/job/(?P<job_id>\d+))?"
)


def _extract_actions_run_details(link: str) -> tuple[str | None, str | None]:
    """Extract GitHub Actions run and job IDs from a check link."""
    match = _ACTIONS_RUN_LINK_RE.search(link)
    if not match:
        return None, None

    return match.group("run_id"), match.group("job_id")


def _build_failure_command(run_id: str, job_id: str | None) -> str:
    """Build the command to inspect the failing job logs."""
    command = f"gh run view {run_id}"
    if job_id:
        command += f" --job {job_id}"
    return f"{command} --log-failed"


def _classify_failed_step_name(step_name: str) -> str | None:
    """Classify a failed step name into a coarse failure category."""
    lowered = step_name.lower()
    # Specific tools first to avoid "Run bats tests" matching "test" before "bats"
    if "bats" in lowered:
        return "bats"
    if "ruff" in lowered:
        return "ruff"
    if "black" in lowered or "format" in lowered:
        return "black"
    if "mypy" in lowered or "type check" in lowered:
        return "mypy"
    if "loc" in lowered:
        return "loc"
    # Generic test match as last resort
    if "pytest" in lowered or "tests" in lowered or "test" in lowered:
        return "pytest"
    # Generic lint match (may include non-ruff steps like "dual-layer lint")
    if "lint" in lowered:
        return "lint"
    return None


def _classify_failed_job(job: dict[str, Any]) -> str | None:
    """Classify a failed GitHub Actions job from step names."""
    steps = job.get("steps", [])
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            conclusion = str(step.get("conclusion", "")).lower()
            if conclusion in {"failure", "cancelled", "timed_out"}:
                step_name = str(step.get("name", ""))
                category = _classify_failed_step_name(step_name)
                if category:
                    return category
                break

    job_name = str(job.get("name", ""))
    return _classify_failed_step_name(job_name)


def _enrich_failed_check(check: CICheck) -> CICheck:
    """Add failure metadata to a failed check when job details are available."""
    if check.bucket != "fail":
        return check

    run_id, job_id = _extract_actions_run_details(check.link)
    if not run_id:
        return check

    failure_command = _build_failure_command(run_id, job_id)
    failure_category: str | None = None

    if not job_id:
        return check.model_copy(update={"failure_command": failure_command})

    try:
        run_result = subprocess.run(
            [
                "gh",
                "run",
                "view",
                run_id,
                "--job",
                job_id,
                "--json",
                "jobs",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        logger.bind(external="github", run_id=run_id, job_id=job_id).debug(
            "gh CLI not found when fetching Actions job details"
        )
        return check.model_copy(update={"failure_command": failure_command})
    except subprocess.TimeoutExpired:
        logger.bind(external="github", run_id=run_id, job_id=job_id).debug(
            "gh run view timed out after 30 seconds"
        )
        return check.model_copy(update={"failure_command": failure_command})

    if run_result.returncode == 0:
        try:
            run_data = json.loads(run_result.stdout)
        except json.JSONDecodeError as e:
            logger.bind(
                external="github",
                run_id=run_id,
                job_id=job_id,
                error=str(e),
            ).debug("Failed to parse gh run view JSON output")
        else:
            jobs = run_data.get("jobs", [])
            if isinstance(jobs, list):
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    failure_category = _classify_failed_job(job)
                    if failure_category:
                        break

    return check.model_copy(
        update={
            "failure_category": failure_category,
            "failure_command": failure_command,
        }
    )


class PRReadMixin:
    """Mixin for PR read operations."""

    def get_pr(
        self: Any, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Get PR by number or branch."""
        logger.bind(
            external="github",
            operation="get_pr",
            pr_number=pr_number,
            branch=branch,
        ).debug("Calling GitHub API: get_pull_request")

        target = str(pr_number) if pr_number else branch
        if not target:
            # Try current branch
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            target = result.stdout.strip()

        result = self._run_gh_command(
            [
                "gh",
                "pr",
                "view",
                target,
                "--json",
                "number,title,body,state,headRefName,baseRefName,"
                "url,isDraft,createdAt,updatedAt,mergedAt,closedAt,mergeable,statusCheckRollup,"
                "closingIssuesReferences",
            ]
        )
        if result is None:
            # Timeout or gh CLI not found
            return None
        if result.returncode != 0:
            logger.bind(external="github", target=target).warning("PR not found")
            return None

        data = json.loads(result.stdout)

        # Determine is_ready: not a draft
        is_ready = not bool(data.get("isDraft", True))

        # Determine ci_passed: check statusCheckRollup
        status_checks = data.get("statusCheckRollup")
        ci_status: str | None
        ci_passed: bool
        if status_checks and isinstance(status_checks, list):
            # Determine overall CI status from check list
            conclusions = [
                c.get("conclusion", "")
                for c in status_checks
                if c.get("status") == "COMPLETED"
            ]
            pending = any(c.get("status") != "COMPLETED" for c in status_checks)
            if pending:
                ci_status = "pending"
                ci_passed = False
            elif all(c == "SUCCESS" for c in conclusions):
                ci_status = "success"
                ci_passed = True
            elif any(c == "FAILURE" for c in conclusions):
                ci_status = "failure"
                ci_passed = False
            else:
                ci_status = conclusions[0].lower() if conclusions else None
                ci_passed = False
        else:
            ci_passed = False
            ci_status = None

        # Parse closingIssuesReferences to get task_issue
        # Note: closingIssuesReferences is a list (not {references: [...]} object)
        # See github_issue_admin_ops.py:get_pr_for_issue for reference
        closing_refs = data.get("closingIssuesReferences", [])
        task_issue = None
        if closing_refs and isinstance(closing_refs, list):
            # Take the first closing issue as task_issue
            task_issue = closing_refs[0].get("number")

        metadata = None
        if task_issue:
            metadata = PRMetadata(
                branch=None,
                task_issue=task_issue,
                flow_slug=None,
                spec_ref=None,
                planner=None,
                executor=None,
                reviewer=None,
                latest=None,
            )

        # Fetch CI check details via gh pr checks
        ci_checks: list[CICheck] = []
        checks_result = self._run_gh_command(
            [
                "gh",
                "pr",
                "checks",
                target,
                "--json",
                "name,state,bucket,link,description,workflow",
            ]
        )
        if checks_result is not None and checks_result.returncode == 0:
            try:
                checks_data = json.loads(checks_result.stdout)
                ci_checks = [
                    _enrich_failed_check(CICheck(**c))
                    for c in checks_data
                    if isinstance(c, dict)
                ]
            except json.JSONDecodeError as e:
                logger.bind(external="github", target=target, error=str(e)).debug(
                    "Failed to parse gh pr checks JSON output"
                )
        elif checks_result is not None:
            stderr = checks_result.stderr.strip() if checks_result.stderr else None
            logger.bind(
                external="github",
                target=target,
                returncode=checks_result.returncode,
                stderr=stderr,
            ).debug("gh pr checks returned non-zero exit code")

        return PRResponse(
            number=int(data["number"]),
            title=str(data["title"]),
            body=str(data.get("body", "")),
            state=PRState(data["state"]),
            head_branch=str(data["headRefName"]),
            base_branch=str(data["baseRefName"]),
            url=str(data["url"]),
            draft=bool(data.get("isDraft", False)),
            is_ready=is_ready,
            ci_passed=ci_passed,
            ci_status=ci_status,
            created_at=data.get("createdAt"),
            updated_at=data.get("updatedAt"),
            merged_at=data.get("mergedAt"),
            closed_at=data.get("closedAt"),
            metadata=metadata,
            ci_checks=ci_checks,
        )

    def list_all_prs(
        self: Any, state: str = "open", limit: int = 100, *, repo: str | None = None
    ) -> list[PRResponse]:
        """List all PRs in repository without branch filter.

        Batch query optimization: fetch all PRs in one API call
        instead of N calls for N branches.

        Args:
            state: PR state filter (open, closed, merged, all)
            limit: Maximum number of PRs to return
            repo: Optional repository in owner/repo format

        Returns:
            List of PR objects with all fields, or empty list on failure
        """
        logger.bind(
            external="github",
            operation="list_all_prs",
            state=state,
            limit=limit,
            repo=repo,
        ).debug("Calling GitHub API: list_all_prs (batch query)")

        cmd = [
            "gh",
            "pr",
            "list",
            "--state",
            state,
            "--limit",
            str(limit),
            "--json",
            "number,title,state,isDraft,url,headRefName,baseRefName,mergedAt,closedAt",
        ]
        if repo:
            cmd.extend(["--repo", repo])

        result = self._run_gh_command(cmd)
        if result is None:
            # Timeout or gh CLI not found
            return []
        if result.returncode != 0:
            logger.bind(external="github", repo=repo, stderr=result.stderr).warning(
                "Failed to list PRs, returning empty list"
            )
            return []

        # Parse PR list from output
        try:
            prs_data = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            logger.bind(
                external="github",
                repo=repo,
                error=str(e),
                stdout_preview=result.stdout[:100],
            ).warning("Failed to parse PR list JSON, returning empty list")
            return []

        prs = []
        for pr_data in prs_data:
            prs.append(
                PRResponse(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body="",
                    state=PRState(pr_data["state"].upper()),
                    head_branch=pr_data["headRefName"],
                    base_branch=pr_data["baseRefName"],
                    url=pr_data["url"],
                    draft=pr_data.get("isDraft", False),
                    is_ready=not pr_data.get("isDraft", False),
                    ci_passed=False,
                    ci_status=None,
                    created_at=None,
                    updated_at=None,
                    merged_at=pr_data.get("mergedAt"),
                    closed_at=pr_data.get("closedAt"),
                    metadata=None,
                )
            )

        logger.bind(
            external="github",
            state=state,
            pr_count=len(prs),
        ).debug("Retrieved all PRs (batch query)")

        return prs

    def list_prs_for_branch(
        self: Any, branch: str, *, state: str | None = None, repo: str | None = None
    ) -> list[PRResponse]:
        """List PRs for a specific branch.

        Note: For querying multiple branches, prefer list_all_prs()
        for batch optimization (1 API call instead of N).

        Args:
            branch: Branch name to query
            state: Optional PR state filter
            repo: Optional repository in owner/repo format

        Returns:
            List of PR responses, or empty list on failure
        """
        logger.bind(
            external="github",
            operation="list_prs_for_branch",
            branch=branch,
            repo=repo,
        ).debug("Calling GitHub API: list_prs")

        cmd = [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--json",
            "number,title,state,isDraft,url,headRefName,baseRefName,mergedAt,closedAt",
        ]
        if state:
            cmd.extend(["--state", state])
        if repo:
            cmd.extend(["--repo", repo])

        result = self._run_gh_command(cmd)
        if result is None:
            # Timeout or gh CLI not found
            return []
        if result.returncode != 0:
            logger.bind(
                external="github", branch=branch, repo=repo, stderr=result.stderr
            ).warning("Failed to list PRs for branch, returning empty list")
            return []

        # Parse PR list from output
        try:
            prs_data = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            logger.bind(
                external="github",
                branch=branch,
                repo=repo,
                error=str(e),
                stdout_preview=result.stdout[:100],
            ).warning("Failed to parse PR list JSON for branch, returning empty list")
            return []

        prs = []
        for pr_data in prs_data:
            prs.append(
                PRResponse(
                    number=pr_data["number"],
                    title=pr_data["title"],
                    body="",
                    state=PRState(pr_data["state"].upper()),
                    head_branch=pr_data["headRefName"],
                    base_branch=pr_data["baseRefName"],
                    url=pr_data["url"],
                    draft=pr_data.get("isDraft", False),
                    is_ready=not pr_data.get("isDraft", False),
                    ci_passed=False,
                    ci_status=None,
                    created_at=None,
                    updated_at=None,
                    merged_at=pr_data.get("mergedAt"),
                    closed_at=pr_data.get("closedAt"),
                    metadata=None,
                )
            )

        logger.bind(
            external="github",
            branch=branch,
            pr_count=len(prs),
        ).debug("Retrieved PRs for branch")

        return prs

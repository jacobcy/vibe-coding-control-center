"""Audit evidence collector service.

Implements evidence collection from flow store, GitHub, and git for audit purposes.
"""

import hashlib
import re
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.audit_evidence import (
    CollectionContext,
    EvidenceBundle,
    EvidenceSummary,
    FlowRef,
    GitHubRef,
    GitRef,
    PrimarySubject,
    RepoInfo,
    SourceRefs,
    TimeWindow,
    Trust,
)


def _extract_author_login(author_field: Any) -> str | None:
    """Extract login from GitHub API author field.

    GitHub API returns nested objects like {"login": "username", ...}
    This helper extracts the login string safely.
    """
    if isinstance(author_field, str):
        return author_field
    if isinstance(author_field, dict):
        return author_field.get("login")
    return None


class AuditEvidenceCollector:
    """Collect audit evidence from flow store, GitHub, and git.

    This service is read-only and does not modify any external state.
    """

    def __init__(
        self,
        sqlite_client: SQLiteClient,
        github_client: GitHubClient,
        git_client: GitClient,
    ):
        """Initialize with dependency injection.

        Args:
            sqlite_client: SQLite client for flow store access
            github_client: GitHub client for issue/PR access
            git_client: Git client for commit/diff access
        """
        self.sqlite = sqlite_client
        self.github = github_client
        self.git = git_client

    def collect_flow_evidence(self, branch: str, limit: int = 200) -> list[FlowRef]:
        """Collect flow state and timeline events from SQLite.

        Args:
            branch: Flow branch name
            limit: Maximum number of events to retrieve (default 200)

        Returns:
            List of FlowRef objects representing flow state and events
        """
        refs: list[FlowRef] = []

        # Get flow state
        flow_state = self.sqlite.get_flow_state(branch)
        if not flow_state:
            logger.warning(f"No flow state found for branch: {branch}")
            return refs

        # Get flow events
        events = self.sqlite.get_events(branch=branch, limit=limit)
        event_count = len(events)

        # Calculate watermark
        last_event_at = (
            events[0]["created_at"] if events else datetime.now().isoformat()
        )
        watermark_data = f"{event_count}:{last_event_at}"
        watermark = hashlib.sha256(watermark_data.encode()).hexdigest()[:16]

        # Create FlowRef for flow state snapshot
        flow_ref = FlowRef(
            branch=branch,
            flow_slug=flow_state.get("flow_slug"),
            event_id=None,
            event_type="flow_state_snapshot",
            actor=flow_state.get("latest_actor"),
            created_at=flow_state.get("updated_at"),
            watermark=watermark,
        )
        refs.append(flow_ref)

        # Create FlowRef for each event
        for event in events:
            event_ref = FlowRef(
                branch=branch,
                flow_slug=flow_state.get("flow_slug"),
                event_id=event.get("id"),
                event_type=event.get("event_type"),
                actor=event.get("actor"),
                created_at=event.get("created_at"),
                watermark=watermark,
            )
            refs.append(event_ref)

        logger.info(f"Collected {len(refs)} flow refs for branch: {branch}")
        return refs

    def collect_github_issue_evidence(
        self, issue_number: int, repo: str | None = None
    ) -> list[GitHubRef]:
        """Collect issue and issue comments from GitHub.

        Args:
            issue_number: GitHub issue number
            repo: Optional repo override (owner/repo)

        Returns:
            List of GitHubRef objects for issue and comments
        """
        refs: list[GitHubRef] = []

        # Get issue details
        issue = self.github.view_issue(
            issue_number,
            repo=repo,
            fields=[
                "number",
                "title",
                "body",
                "state",
                "labels",
                "createdAt",
                "updatedAt",
                "author",
            ],
        )
        if not issue or isinstance(issue, str):
            logger.warning(f"Could not retrieve issue #{issue_number}")
            return refs

        # Create GitHubRef for issue body
        issue_ref = GitHubRef(
            kind="issue",
            number=issue_number,
            url=f"https://github.com/{repo or 'owner/repo'}/issues/{issue_number}",
            author=_extract_author_login(
                issue.get("author") if isinstance(issue, dict) else None
            ),
            created_at=issue.get("createdAt") if isinstance(issue, dict) else None,
            marker=None,
        )
        refs.append(issue_ref)

        # Get issue comments
        comments = self.github.list_issue_comments(issue_number, repo=repo)

        # Create GitHubRef for each comment, extracting markers
        for comment in comments:
            body = comment.get("body", "")
            marker = None
            if body:
                # Extract first complete marker using regex
                # Matches patterns like [manager], [plan], etc.
                match = re.search(r"\[[\w-]+\]", body)
                if match:
                    marker = match.group(0)

            comment_ref = GitHubRef(
                kind="issue_comment",
                number=comment.get("id", 0),
                url=comment.get("url", ""),
                author=_extract_author_login(comment.get("author")),
                created_at=comment.get("createdAt"),
                marker=marker,
            )
            refs.append(comment_ref)

        logger.info(f"Collected {len(refs)} GitHub refs for issue #{issue_number}")
        return refs

    def collect_github_pr_evidence(
        self,
        branch: str | None = None,
        issue_number: int | None = None,
        repo: str | None = None,
    ) -> list[GitHubRef]:
        """Collect PR state, comments, and reviews from GitHub.

        Args:
            branch: Optional branch name to find PRs
            issue_number: Optional issue number to find linked PRs
            repo: Optional repo override (owner/repo)

        Returns:
            List of GitHubRef objects for PR state, comments, and reviews
        """
        refs: list[GitHubRef] = []

        # Find PRs by branch or issue
        prs = []
        if branch:
            prs = self.github.list_prs_for_branch(branch, repo=repo)
        elif issue_number:
            # Try to find PRs linked to the issue
            # Note: simplified approach; real implementation
            # would need more sophisticated linking
            pass

        for pr in prs:
            # Handle PRResponse objects (use attribute access for Pydantic models)
            # Try dict access first, fall back to attribute access
            if isinstance(pr, dict):
                pr_number_val = pr.get("number")
                pr_url = pr.get("url", "")
                pr_author = pr.get("author")
                pr_created = pr.get("createdAt")
            else:
                # PRResponse is a Pydantic model - use attribute access
                pr_number_val = getattr(pr, "number", None)
                pr_url = getattr(pr, "url", "")
                pr_author = getattr(pr, "author", None)
                pr_created = getattr(pr, "created_at", None)

            if not pr_number_val or not isinstance(pr_number_val, int):
                continue

            # Create GitHubRef for PR state
            pr_ref = GitHubRef(
                kind="pr",
                number=pr_number_val,
                url=str(pr_url),
                author=_extract_author_login(pr_author),
                created_at=pr_created if isinstance(pr_created, str) else None,
                marker=None,
            )
            refs.append(pr_ref)

            # Get PR general comments
            try:
                comments = self.github.list_pr_comments(pr_number_val)
                for comment in comments:
                    comment_ref = GitHubRef(
                        kind="pr_comment",
                        number=comment.get("id", 0),
                        url=comment.get("url", ""),
                        author=_extract_author_login(comment.get("author")),
                        created_at=comment.get("createdAt"),
                        marker=None,
                    )
                    refs.append(comment_ref)
            except Exception as e:
                logger.warning(
                    f"Could not retrieve PR comments for #{pr_number_val}: {e}"
                )

            # Get PR reviews
            try:
                reviews = self.github.list_pr_reviews(pr_number_val)
                for review in reviews:
                    # Reviews use "user" field, not "author"
                    review_ref = GitHubRef(
                        kind="review",
                        number=review.get("id", 0),
                        url=review.get("url", ""),
                        author=_extract_author_login(review.get("user")),
                        created_at=review.get("submittedAt"),
                        marker=None,
                    )
                    refs.append(review_ref)
            except Exception as e:
                logger.warning(
                    f"Could not retrieve PR reviews for #{pr_number_val}: {e}"
                )

        logger.info(f"Collected {len(refs)} GitHub PR refs")
        return refs

    def collect_git_evidence(
        self,
        branch: str,
        base_ref: str = "origin/main",
        time_window: tuple[datetime, datetime] | None = None,
    ) -> list[GitRef]:
        """Collect git commits and changed files.

        Args:
            branch: Branch name
            base_ref: Base reference for diff (default: origin/main)
            time_window: Optional time window for filtering commits

        Returns:
            List of GitRef objects for commits and diffs
        """
        refs: list[GitRef] = []

        # Get commits between base and branch using git log
        try:
            # Use git log to get SHA and subject
            log_output = self.git._run(
                ["log", f"{base_ref}..{branch}", "--oneline", "--format=%H %s"]
            )
            commit_lines = [
                line.strip() for line in log_output.splitlines() if line.strip()
            ]

            # Create GitRef for commit range
            if commit_lines:
                git_ref = GitRef(
                    kind="diff_range",
                    ref=f"{base_ref}..{branch}",
                    base_ref=base_ref,
                    head_ref=branch,
                    author=None,  # Agent vs human detection would need more analysis
                    committed_at=None,
                    files_changed=[],
                )
                refs.append(git_ref)

            # Create GitRef for individual commits
            for line in commit_lines[:50]:  # Limit to first 50 commits
                parts = line.split(maxsplit=1)
                if len(parts) >= 1:
                    sha = parts[0]
                    commit_ref = GitRef(
                        kind="commit",
                        ref=sha,  # Use SHA, not subject
                        base_ref=None,
                        head_ref=None,
                        author=None,
                        committed_at=None,
                        files_changed=[],
                    )
                    refs.append(commit_ref)

        except Exception as e:
            logger.warning(f"Could not retrieve git commits for {branch}: {e}")

        logger.info(f"Collected {len(refs)} git refs for branch: {branch}")
        return refs

    def assemble_bundle(
        self,
        mode: str,
        *,
        issue_number: int | None = None,
        branch: str | None = None,
        time_window: tuple[datetime, datetime] | None = None,
        repo: str | None = None,
    ) -> EvidenceBundle:
        """Assemble complete evidence bundle from all sources.

        Args:
            mode: Collection mode (issue, flow, pr, time_window, manual)
            issue_number: Optional issue number
            branch: Optional flow branch name
            time_window: Optional time window for filtering
            repo: Optional repo override (owner/repo)

        Returns:
            Complete EvidenceBundle ready for JSON output
        """
        # Collect evidence from all sources, capturing errors
        flow_refs = []
        github_refs = []
        git_refs = []
        limitations: list[str] = []

        if branch:
            try:
                flow_refs = self.collect_flow_evidence(branch)
            except Exception as e:
                limitations.append(f"Flow collection failed: {str(e)}")
                logger.warning(f"Flow evidence collection failed: {e}")

            try:
                git_refs = self.collect_git_evidence(branch, time_window=time_window)
            except Exception as e:
                limitations.append(f"Git collection failed: {str(e)}")
                logger.warning(f"Git evidence collection failed: {e}")

        if issue_number:
            try:
                github_refs.extend(
                    self.collect_github_issue_evidence(issue_number, repo=repo)
                )
            except Exception as e:
                limitations.append(f"GitHub issue collection failed: {str(e)}")
                logger.warning(f"GitHub issue evidence collection failed: {e}")

            # Try to find PRs for the issue
            try:
                pr_refs = self.collect_github_pr_evidence(
                    branch=branch, issue_number=issue_number, repo=repo
                )
                github_refs.extend(pr_refs)
            except Exception as e:
                limitations.append(f"GitHub PR collection failed: {str(e)}")
                logger.warning(f"GitHub PR evidence collection failed: {e}")

        # Build collection context
        time_window_obj = TimeWindow()
        if time_window:
            time_window_obj = TimeWindow(
                start=time_window[0].isoformat(),
                end=time_window[1].isoformat(),
            )

        # Get source metadata
        source_machine = socket.gethostname()
        source_db = getattr(self.sqlite, "db_path", None)
        try:
            source_commit = self.git.get_current_commit()
        except Exception as e:
            source_commit = None
            limitations.append(f"Git commit resolution failed: {str(e)}")

        collection_context = CollectionContext(
            mode=mode,  # type: ignore
            source_machine=source_machine,
            source_db=source_db,
            source_commit=source_commit,
            time_window=time_window_obj,
        )

        # Build primary subject
        primary_subject = PrimarySubject(
            issue_number=issue_number,
            branch=branch,
            pr_number=None,
        )

        # Build source refs
        source_refs = SourceRefs(
            github=github_refs,
            flow=flow_refs,
            handoff=[],  # Would need separate handoff collection logic
            git=git_refs,
            prompt=[],
            skill=[],
            memory=[],
        )

        # Build repo info
        repo_info = RepoInfo(
            owner="owner",  # Would need to parse from repo string or git remote
            name="repo",
            local_root=str(Path.cwd()),
        )

        # Build summary (simplified; real impl would analyze flow state)
        symptom = f"Evidence collected for {mode} mode"
        evidence_text = (
            f"Flow refs: {len(flow_refs)}, "
            f"GitHub refs: {len(github_refs)}, "
            f"Git refs: {len(git_refs)}"
        )
        summary = EvidenceSummary(
            symptom=symptom,
            evidence_text=evidence_text,
            candidate_failure_patterns=[],
        )

        # Build trust classification with error limitations
        trust = Trust(
            source_class="authoritative",
            freshness="fresh",
            confidence="medium" if not limitations else "weak",
            limitations=limitations,
        )

        # Generate bundle ID
        bundle_id_data = (
            f"{mode}:{issue_number or ''}:{branch or ''}:{datetime.now().isoformat()}"
        )
        bundle_id = hashlib.sha256(bundle_id_data.encode()).hexdigest()[:16]

        # Assemble bundle
        bundle = EvidenceBundle(
            id=bundle_id,
            created_by="audit_evidence_collector",
            repo=repo_info,
            collection_context=collection_context,
            primary_subject=primary_subject,
            source_refs=source_refs,
            summary=summary,
            trust=trust,
        )

        logger.info(f"Assembled evidence bundle: {bundle_id}")
        return bundle

    def format_bundle_json(self, bundle: EvidenceBundle) -> str:
        """Format bundle as JSON string.

        Args:
            bundle: Evidence bundle to format

        Returns:
            JSON string representation
        """
        return bundle.model_dump_json(indent=2)

    def format_bundle_summary(self, bundle: EvidenceBundle) -> str:
        """Format bundle as human-readable summary.

        Args:
            bundle: Evidence bundle to format

        Returns:
            Human-readable text summary
        """
        lines = [
            f"Evidence Bundle: {bundle.id}",
            f"Schema Version: {bundle.schema_version}",
            f"Created: {bundle.created_at}",
            f"Mode: {bundle.collection_context.mode}",
            "",
            "Primary Subject:",
            f"  Issue: {bundle.primary_subject.issue_number or 'N/A'}",
            f"  Branch: {bundle.primary_subject.branch or 'N/A'}",
            f"  PR: {bundle.primary_subject.pr_number or 'N/A'}",
            "",
            "Source References:",
            f"  GitHub: {len(bundle.source_refs.github)}",
            f"  Flow: {len(bundle.source_refs.flow)}",
            f"  Handoff: {len(bundle.source_refs.handoff)}",
            f"  Git: {len(bundle.source_refs.git)}",
            "",
            "Summary:",
            f"  Symptom: {bundle.summary.symptom}",
            f"  Evidence: {bundle.summary.evidence_text}",
            "",
            "Trust:",
            f"  Class: {bundle.trust.source_class}",
            f"  Freshness: {bundle.trust.freshness}",
            f"  Confidence: {bundle.trust.confidence}",
        ]

        if bundle.trust.limitations:
            lines.append("  Limitations:")
            for limitation in bundle.trust.limitations:
                lines.append(f"    - {limitation}")

        return "\n".join(lines)

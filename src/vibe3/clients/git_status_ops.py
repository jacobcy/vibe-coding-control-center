"""Git status operations - diff and status helpers."""

import re
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.exceptions import GitError, SystemError
from vibe3.models import (
    BranchSource,
    ChangeSource,
    ChangeSourceType,
    CommitSource,
    PRSource,
)

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient


def get_changed_files(
    run: Callable[[list[str]], str],
    source: ChangeSource,
    github_client: "GitHubClient | None" = None,
    pathspec: str | None = None,
) -> list[str]:
    """统一接口：获取改动文件列表.

    Args:
        run: Git command runner function
        source: 改动源（PR/Commit/Branch/Uncommitted）
        github_client: 可选的 GitHubClient 实例，用于处理 PR 相关操作
        pathspec: 可选的 git pathspec 过滤模式（如 '*.py'）

    Returns:
        改动文件路径列表

    Raises:
        GitError: git 命令执行失败
    """
    log = logger.bind(domain="git", action="get_changed_files", source_type=source.type)
    log.info("Getting changed files")

    if source.type == ChangeSourceType.UNCOMMITTED:
        files = _get_uncommitted_files(run, pathspec=pathspec)
    elif source.type == ChangeSourceType.COMMIT:
        if not isinstance(source, CommitSource):
            raise SystemError(
                f"Type mismatch: expected CommitSource, got {type(source).__name__}"
            )
        files = _get_commit_files(run, source.sha, pathspec=pathspec)
    elif source.type == ChangeSourceType.BRANCH:
        if not isinstance(source, BranchSource):
            raise SystemError(
                f"Type mismatch: expected BranchSource, got {type(source).__name__}"
            )
        files = _get_branch_files(run, source.branch, source.base, pathspec=pathspec)
    elif source.type == ChangeSourceType.PR:
        if not isinstance(source, PRSource):
            raise SystemError(
                f"Type mismatch: expected PRSource, got {type(source).__name__}"
            )
        if not github_client:
            raise GitError(
                "get_changed_files",
                "PR source requires GitHubClient injection",
            )
        files = github_client.get_pr_files(source.pr_number)
        if pathspec:
            files = [f for f in files if fnmatch(f, pathspec)]
    else:
        raise GitError("get_changed_files", f"Unknown source type: {source.type}")

    log.bind(file_count=len(files)).success("Got changed files")
    return files


def get_diff(
    run: Callable[[list[str]], str],
    source: ChangeSource,
    github_client: "GitHubClient | None" = None,
    pr_diff_cache: dict[int, str] | None = None,
    pathspec: list[str] | None = None,
) -> str:
    """统一接口：获取 diff 内容.

    Args:
        run: Git command runner function
        source: 改动源（PR/Commit/Branch/Uncommitted）
        github_client: 可选的 GitHubClient 实例，用于处理 PR 相关操作
        pr_diff_cache: 可选的 PR diff 缓存字典
        pathspec: 可选的路径过滤列表（如 ['src/', 'bin/']）

    Returns:
        diff 文本

    Raises:
        GitError: git 命令执行失败
    """
    log = logger.bind(domain="git", action="get_diff", source_type=source.type)
    log.info("Getting diff")

    if source.type == ChangeSourceType.UNCOMMITTED:
        args = ["diff", "HEAD"]
        if pathspec:
            args.extend(["--"] + pathspec)
        diff = run(args)
    elif source.type == ChangeSourceType.COMMIT:
        if not isinstance(source, CommitSource):
            raise SystemError(
                f"Type mismatch: expected CommitSource, got {type(source).__name__}"
            )
        args = ["show", source.sha, "--stat"]
        if pathspec:
            args.extend(["--"] + pathspec)
        diff = run(args)
    elif source.type == ChangeSourceType.BRANCH:
        if not isinstance(source, BranchSource):
            raise SystemError(
                f"Type mismatch: expected BranchSource, got {type(source).__name__}"
            )
        args = ["diff", f"{source.base}...{source.branch}"]
        if pathspec:
            args.extend(["--"] + pathspec)
        diff = run(args)
    elif source.type == ChangeSourceType.PR:
        if not isinstance(source, PRSource):
            raise SystemError(
                f"Type mismatch: expected PRSource, got {type(source).__name__}"
            )
        if not github_client:
            raise GitError(
                "get_diff",
                "PR source requires GitHubClient injection",
            )
        if pr_diff_cache is not None and source.pr_number in pr_diff_cache:
            diff = pr_diff_cache[source.pr_number]
        else:
            diff = github_client.get_pr_diff(source.pr_number)
            if pr_diff_cache is not None:
                pr_diff_cache[source.pr_number] = diff
        if pathspec:
            diff = _filter_unified_diff_by_paths(diff, pathspec)
    else:
        raise GitError("get_diff", f"Unknown source type: {source.type}")

    log.bind(diff_len=len(diff)).success("Got diff")
    return diff


def _get_uncommitted_files(
    run: Callable[[list[str]], str], pathspec: str | None = None
) -> list[str]:
    """获取未提交改动文件（暂存 + 工作区）."""
    pargs = ["--", pathspec] if pathspec else []
    staged = run(["diff", "--name-only", "--cached"] + pargs)
    unstaged = run(["diff", "--name-only"] + pargs)
    untracked = run(["ls-files", "--others", "--exclude-standard"] + pargs)
    all_files = set()
    for line in (staged + "\n" + unstaged + "\n" + untracked).splitlines():
        if line.strip():
            all_files.add(line.strip())
    return sorted(all_files)


def get_untracked_files(run: Callable[[list[str]], str]) -> list[str]:
    """获取未跟踪文件列表."""
    output = run(["ls-files", "--others", "--exclude-standard"])
    return [f for f in output.splitlines() if f.strip()]


def get_tracked_files(
    run: Callable[[list[str]], str], pathspec: str | None = None
) -> list[str]:
    """Get all tracked files from git, optionally filtered by pathspec.

    Naturally respects .gitignore since git ls-files only returns tracked files.

    Args:
        run: Git command runner function
        pathspec: Optional pathspec filter (e.g. "src/vibe3/**/*.py")

    Returns:
        List of tracked file paths relative to repo root
    """
    args = ["ls-files"]
    if pathspec:
        args.extend(["--", pathspec])
    output = run(args)
    return [f for f in output.splitlines() if f.strip()]


def _get_commit_files(
    run: Callable[[list[str]], str], sha: str, pathspec: str | None = None
) -> list[str]:
    """获取指定 commit 的改动文件."""
    pargs = ["--", pathspec] if pathspec else []
    output = run(
        ["diff-tree", "--no-commit-id", "-r", "--name-only", "-m", sha] + pargs
    )
    return sorted(set(f for f in output.splitlines() if f.strip()))


def _get_branch_files(
    run: Callable[[list[str]], str], branch: str, base: str, pathspec: str | None = None
) -> list[str]:
    """获取分支相对于 base 的改动文件."""
    pargs = ["--", pathspec] if pathspec else []
    output = run(["diff", "--name-only", f"{base}...{branch}"] + pargs)
    return [f for f in output.splitlines() if f.strip()]


def _numstat_via_merge_base(
    run: Callable[[list[str]], str],
    get_merge_base: Callable[[str, str], str],
    head: str,
    base: str,
) -> str:
    """Get numstat via merge-base resolution."""
    merge_base = get_merge_base(head, base)
    if not re.match(r"^[a-f0-9]{40}$", merge_base):
        raise SystemError(f"get_merge_base returned invalid SHA format: '{merge_base}'")
    return run(["diff", "--numstat", f"{merge_base}...{head}"])


def _name_status_via_merge_base(
    run: Callable[[list[str]], str],
    get_merge_base: Callable[[str, str], str],
    head: str,
    base: str,
) -> str:
    """Get name-status via merge-base resolution."""
    merge_base = get_merge_base(head, base)
    if not re.match(r"^[a-f0-9]{40}$", merge_base):
        raise SystemError(f"get_merge_base returned invalid SHA format: '{merge_base}'")
    return run(["diff", "--name-status", f"{merge_base}...{head}"])


def has_uncommitted_changes(run: Callable[[list[str]], str]) -> bool:
    """Check if working directory is dirty.

    Args:
        run: Git command runner function

    Returns:
        True if there are uncommitted changes
    """
    try:
        status = run(["status", "--porcelain"])
        return bool(status)
    except GitError:
        return False


def get_numstat(
    run: Callable[[list[str]], str],
    source: ChangeSource,
    github_client: "GitHubClient | None" = None,
    get_merge_base: Callable[[str, str], str] | None = None,
    pr_numstat_cache: dict[int, str] | None = None,
) -> str:
    """Unified interface: get git diff --numstat output.

    Args:
        run: Git command runner function
        source: Change source (PR/Commit/Branch/Uncommitted)
        github_client: Optional GitHubClient for PR ref resolution
        get_merge_base: Optional merge-base resolver callable
        pr_numstat_cache: Optional PR numstat cache dict

    Returns:
        numstat output string (tab-separated: added deleted filepath)

    Raises:
        GitError: git command execution failed
        SystemError: missing required callables
            (e.g., get_merge_base for branch/PR sources)
    """
    log = logger.bind(domain="git", action="get_numstat", source_type=source.type)
    log.info("Getting numstat")

    # Note: isinstance guards protect against direct dataclass construction
    # bypassing the Pydantic discriminated union discriminator. Sister
    # functions get_changed_files() and get_diff() use the same pattern.

    if source.type == ChangeSourceType.UNCOMMITTED:
        output = run(["diff", "--numstat", "HEAD"])
    elif source.type == ChangeSourceType.COMMIT:
        if not isinstance(source, CommitSource):
            raise SystemError(
                f"Type mismatch: expected CommitSource, got {type(source).__name__}"
            )
        output = run(["diff", "--numstat", f"{source.sha}^", source.sha])
    elif source.type == ChangeSourceType.BRANCH:
        if not isinstance(source, BranchSource):
            raise SystemError(
                f"Type mismatch: expected BranchSource, got {type(source).__name__}"
            )
        if not get_merge_base:
            raise SystemError("get_merge_base callable required for BranchSource")
        output = _numstat_via_merge_base(
            run, get_merge_base, source.branch, source.base
        )
    elif source.type == ChangeSourceType.PR:
        if not isinstance(source, PRSource):
            raise SystemError(
                f"Type mismatch: expected PRSource, got {type(source).__name__}"
            )
        if not github_client:
            raise GitError(
                "get_numstat",
                "PR source requires GitHubClient injection",
            )
        if not get_merge_base:
            raise SystemError("get_merge_base callable required for PRSource")
        if pr_numstat_cache is not None and source.pr_number in pr_numstat_cache:
            output = pr_numstat_cache[source.pr_number]
        else:
            pr_info = github_client.get_pr(source.pr_number)
            if not pr_info:
                raise GitError(
                    "get_numstat",
                    f"PR #{source.pr_number} not found",
                )
            output = _numstat_via_merge_base(
                run, get_merge_base, pr_info.head_branch, pr_info.base_branch
            )
            if pr_numstat_cache is not None:
                pr_numstat_cache[source.pr_number] = output
    else:
        raise GitError("get_numstat", f"Unknown source type: {source.type}")

    log.bind(output_len=len(output)).success("Got numstat")
    return output


def _filter_unified_diff_by_paths(diff_text: str, paths: list[str]) -> str:
    """Filter unified diff text to include only files matching given path prefixes.

    Args:
        diff_text: Unified diff text
        paths: List of path prefixes to filter (e.g., ['src/', 'bin/vibe'])

    Returns:
        Filtered diff text containing only matching file sections
    """
    result_lines: list[str] = []
    current_file: str | None = None
    in_matching_file = False

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current_file = parts[2][2:] if len(parts) >= 4 else None
            in_matching_file = current_file is not None and any(
                current_file.startswith(path.rstrip("/")) for path in paths
            )

        if in_matching_file:
            result_lines.append(line)

    return "\n".join(result_lines)


def get_name_status(
    run: Callable[[list[str]], str],
    source: ChangeSource,
    github_client: "GitHubClient | None" = None,
    get_merge_base: Callable[[str, str], str] | None = None,
    pr_name_status_cache: dict[int, str] | None = None,
) -> str:
    """Unified interface: get git diff --name-status output.

    Args:
        run: Git command runner function
        source: Change source (PR/Commit/Branch/Uncommitted)
        github_client: Optional GitHubClient for PR ref resolution
        get_merge_base: Optional merge-base resolver callable
        pr_name_status_cache: Optional PR name-status cache dict

    Returns:
        name-status output string (format: STATUS\\tfilepath)

    Raises:
        GitError: git command execution failed
        SystemError: missing required callables
            (e.g., get_merge_base for branch/PR sources)
    """
    log = logger.bind(domain="git", action="get_name_status", source_type=source.type)
    log.info("Getting name-status")

    if source.type == ChangeSourceType.UNCOMMITTED:
        output = run(["diff", "--name-status", "HEAD"])
    elif source.type == ChangeSourceType.COMMIT:
        if not isinstance(source, CommitSource):
            raise SystemError(
                f"Type mismatch: expected CommitSource, got {type(source).__name__}"
            )
        output = run(["diff", "--name-status", f"{source.sha}^", source.sha])
    elif source.type == ChangeSourceType.BRANCH:
        if not isinstance(source, BranchSource):
            raise SystemError(
                f"Type mismatch: expected BranchSource, got {type(source).__name__}"
            )
        if not get_merge_base:
            raise SystemError("get_merge_base callable required for BranchSource")
        output = _name_status_via_merge_base(
            run, get_merge_base, source.branch, source.base
        )
    elif source.type == ChangeSourceType.PR:
        if not isinstance(source, PRSource):
            raise SystemError(
                f"Type mismatch: expected PRSource, got {type(source).__name__}"
            )
        if not github_client:
            raise GitError(
                "get_name_status",
                "PR source requires GitHubClient injection",
            )
        if not get_merge_base:
            raise SystemError("get_merge_base callable required for PRSource")
        if (
            pr_name_status_cache is not None
            and source.pr_number in pr_name_status_cache
        ):
            output = pr_name_status_cache[source.pr_number]
        else:
            pr_info = github_client.get_pr(source.pr_number)
            if not pr_info:
                raise GitError(
                    "get_name_status",
                    f"PR #{source.pr_number} not found",
                )
            output = _name_status_via_merge_base(
                run, get_merge_base, pr_info.head_branch, pr_info.base_branch
            )
            if pr_name_status_cache is not None:
                pr_name_status_cache[source.pr_number] = output
    else:
        raise GitError("get_name_status", f"Unknown source type: {source.type}")

    log.bind(output_len=len(output)).success("Got name-status")
    return output

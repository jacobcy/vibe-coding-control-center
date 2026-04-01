"""Command analyzer helpers."""

from pathlib import Path


def should_expand(callee: str) -> bool:
    """判断是否应该递归展开某个调用.

    Args:
        callee: 调用目标名称

    Returns:
        是否应该展开
    """
    # Expand service, client, and helper calls
    expand_patterns = (
        "service.",
        "client.",
        "_client",
        "helper",
        "ops",
        "PRService",
        "GitClient",
        "SQLiteClient",
    )
    return any(pattern in callee for pattern in expand_patterns)


def should_show_in_tree(callee: str) -> bool:
    """判断是否应该在调用树中显示某个调用.

    Args:
        callee: 调用目标名称

    Returns:
        是否应该在输出中显示
    """
    # Don't show decorator and type annotation calls
    decorator_patterns = (
        "app.command",
        "typer.Argument",
        "typer.Option",
        "Annotated",
    )

    for pattern in decorator_patterns:
        if callee == pattern or callee.startswith(pattern + "."):
            return False

    # Don't show builtin/standard library/utility calls
    utility_patterns = (
        "logger.",
        "print",
        "len",
        "str",
        "int",
        "dict",
        "list",
        "typer.",
        "json.",
        "yaml.",
        "datetime.",
        "Path(",
        "bool",
        "any",
        "all",
        "setup_logging",
        "create_trace_output",
        "add_execution_step",
        "output_result",
        "noop_context",
        "trace_context",
        "info",
        "debug",
        "warning",
        "error",
        "bind",
    )

    for pattern in utility_patterns:
        if callee == pattern or callee.startswith(pattern + "."):
            return False

    # Don't show local variable calls
    if callee.startswith("start_time.") or callee.startswith("pr."):
        return False

    # Only show meaningful business logic calls
    meaningful_patterns = (
        "service",
        "client",
        "render",
        "Service",
        "Client",
        "PRService",
        "GitClient",
        "SQLiteClient",
    )

    return any(pattern in callee for pattern in meaningful_patterns)


def find_callee_file(callee: str, caller_file: str) -> str | None:
    """查找被调用函数所在的文件.

    Args:
        callee: 调用目标名称（如 "service.get_pr"）
        caller_file: 调用者文件路径

    Returns:
        被调用者文件路径或 None
    """
    # Heuristic: look for patterns like "service.xxx" -> "services/xxx_service.py"
    parts = callee.split(".")
    if len(parts) >= 2:
        obj_name = parts[0]

        # Common patterns
        patterns = [
            f"src/vibe3/services/{obj_name}_service.py",
            f"src/vibe3/clients/{obj_name}_client.py",
            f"src/vibe3/clients/{obj_name}_ops.py",
        ]

        for pattern in patterns:
            if Path(pattern).exists():
                return pattern

    return None


def find_command_file(
    command: str,
    subcommand: str | None = None,
    commands_root: str = "src/vibe3/commands",
) -> str | None:
    """在 commands 目录查找命令对应的文件.

    Args:
        command: 命令名（如 "pr" 或 "flow"）
        subcommand: 子命令名（如 "show"、"draft"）
        commands_root: commands 目录路径

    Returns:
        文件路径或 None
    """
    root = Path(commands_root)

    # Try to find the specific subcommand file first
    if subcommand:
        # Pattern: pr_show.py, pr_draft.py, etc.
        subcommand_file = root / f"{command}_{subcommand}.py"
        if subcommand_file.exists():
            return str(subcommand_file)

        # Pattern: pr_query.py (contains show, version_bump)
        # Try common groupings
        group_patterns = {
            "show": ["query"],
            "version_bump": ["query"],
            "draft": ["create"],
            "ready": ["lifecycle"],
            "merge": ["lifecycle"],
            "review": ["review"],
        }

        if subcommand in group_patterns:
            for group in group_patterns[subcommand]:
                group_file = root / f"{command}_{group}.py"
                if group_file.exists():
                    return str(group_file)

    # Fallback to main command file
    candidate = root / f"{command}.py"
    return str(candidate) if candidate.exists() else None

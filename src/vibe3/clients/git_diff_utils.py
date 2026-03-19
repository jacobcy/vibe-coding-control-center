"""Git diff utilities for PR diff extraction and caching."""


def extract_file_diff(full_diff: str, file_path: str) -> str:
    """Extract diff for a specific file from a unified diff output.

    Args:
        full_diff: Full unified diff (e.g., from gh pr diff)
        file_path: File path to extract

    Returns:
        Diff section for the specified file, or empty string if not found
    """
    lines = full_diff.splitlines(keepends=True)
    result: list[str] = []
    capturing = False

    for line in lines:
        if line.startswith("diff --git "):
            if capturing:
                break  # End of previous file's diff
            # Check if this is the file we want
            # Format: diff --git a/path b/path
            if f"a/{file_path}" in line and f"b/{file_path}" in line:
                capturing = True
        if capturing:
            result.append(line)

    return "".join(result)

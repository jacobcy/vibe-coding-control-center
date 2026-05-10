#!/usr/bin/env python
"""Debug script to test git behavior."""
import os
import subprocess
from pathlib import Path

print(f"Initial cwd: {os.getcwd()}")

# Get worktree root using git command directly
result = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    capture_output=True,
    text=True,
    check=True
)
worktree_root = result.stdout.strip()
print(f"Worktree root (from cwd): {worktree_root}")

# Change to subdirectory
subdir = Path(worktree_root) / "src" / "vibe3" / "utils"
print(f"Changing to subdir: {subdir}")
print(f"Subdir exists: {subdir.exists()}")

if subdir.exists():
    os.chdir(str(subdir))
    print(f"New cwd: {os.getcwd()}")

    # Get worktree root again
    result2 = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True
    )
    worktree_root2 = result2.stdout.strip()
    print(f"Worktree root (from subdir): {worktree_root2}")
    print(f"Match: {worktree_root == worktree_root2}")

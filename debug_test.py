#!/usr/bin/env python
"""Debug script to test the actual test behavior."""
import os
from pathlib import Path

print(f"Initial cwd: {os.getcwd()}")

from vibe3.utils.path_helpers import get_worktree_root

# First call
worktree_root = get_worktree_root()
print(f"First call: {worktree_root}")
root_path = Path(worktree_root)

# Change directory
subdir = root_path / "src" / "vibe3" / "utils"
print(f"Subdir: {subdir}")
print(f"Subdir exists: {subdir.exists()}")

if subdir.exists():
    os.chdir(str(subdir))
    print(f"Changed cwd to: {os.getcwd()}")

    # Second call
    worktree_root_from_subdir = get_worktree_root()
    print(f"Second call: {worktree_root_from_subdir}")
    print(f"Match: {worktree_root == worktree_root_from_subdir}")

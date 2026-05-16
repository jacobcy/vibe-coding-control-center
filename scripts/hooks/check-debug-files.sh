#!/usr/bin/env bash
# Check for temporary debug files in repository root
# This script is called by pre-commit hook to prevent debug files from being committed

set -euo pipefail

# Find debug files in repository root (max depth 1)
# Excludes .git directory
files=$(find . -maxdepth 1 -type f \( -name "debug_*.py" -o -name "debug_*.sh" -o -name "tmp_*.py" \) ! -path "./.git/*" 2>/dev/null || true)

if [ -n "$files" ]; then
    echo "ERROR: Temporary debug files found in repository root:"
    echo "$files"
    echo ""
    echo "Please delete these files before committing."
    echo ""
    echo "Tip: You can use 'rm debug_*.py debug_*.sh tmp_*.py' to clean up."
    exit 1
fi

exit 0

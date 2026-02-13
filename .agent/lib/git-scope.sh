#!/usr/bin/env zsh

# git-scope.sh - Helper script for git scope analysis in workflows
# Usage: SCOPE=[staged|working|commit|all] zsh ./git-scope.sh

set -e

# Default to "all" if SCOPE is not set
SCOPE="${SCOPE:-all}"

echo "Running Contextual Analysis for SCOPE: $SCOPE"

case "$SCOPE" in
  staged)
    echo "=== Staged Changes (Ready to Commit) ==="
    git diff --cached --stat
    git diff --cached
    ;;
  working)
    echo "=== Working Directory Changes (Not Staged) ==="
    git diff --stat
    git diff
    ;;
  commit)
    echo "=== Local Commits (Not Pushed) ==="
    # Check if upstream is configured
    if git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
      # Check if there are outgoing commits
      if git log @{u}..HEAD --oneline | grep -q .; then
        git log @{u}..HEAD --stat
        git diff @{u}..HEAD
      else
        echo "No outgoing commits found relative to upstream."
      fi
    else
      echo "⚠️  No upstream branch configured. Skipping commit comparison."
      echo "Tip: Set upstream with 'git push -u origin <branch>'"
    fi
    ;;
  all)
    echo "=== Comprehensive Review ==="
    if ! git diff --cached --quiet; then
      echo "--- Staged Changes ---"
      git diff --cached --stat
    fi
    if ! git diff --quiet; then
      echo "--- Working Directory Changes ---"
      git diff --stat
    fi
    
    # Check upstream before log to avoid noisy errors
    if git rev-parse --abbrev-ref --symbolic-full-name @{u} >/dev/null 2>&1; then
      if git log @{u}..HEAD --oneline 2>/dev/null | grep -q .; then
        echo "--- Local Commits ---"
        git log @{u}..HEAD --oneline
      fi
    fi
    ;;
  *)
    echo "Unknown scope: $SCOPE. Defaulting to 'all'."
    ;;
esac

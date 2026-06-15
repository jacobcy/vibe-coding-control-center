#!/usr/bin/env bash
set -euo pipefail

# One-time cleanup script for orchestra-governed issues missing state labels
# Issue #2861: https://github.com/anthropics/vibe-coding-control-center/issues/2861

echo "=== Fixing orchestra-governed issues missing state labels ==="
FIXED=0

# Query all open issues with orchestra-governed label, filter to those without state labels
# and without roadmap/rfc or roadmap/epic labels
for issue in $(gh issue list --label "orchestra-governed" --json number,labels --jq '
  .[] | select(
    (.labels | map(.name) | any(startswith("state/"))) | not
  ) | select(
    (.labels | map(.name) | any(startswith("roadmap/rfc") or startswith("roadmap/epic"))) | not
  ) | .number
'); do
  echo "Issue #$issue: adding state/ready"
  gh issue edit "$issue" --add-label "state/ready"
  FIXED=$((FIXED + 1))
done

echo "=== Done: $FIXED issues fixed ==="

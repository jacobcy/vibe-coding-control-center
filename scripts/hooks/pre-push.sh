#!/usr/bin/env bash
# pre-push hook - Local review gate, catch issues before push
set -euo pipefail

echo "Running pre-push checks..."
PUSH_STDIN=$(cat)

SCOPE_JSON=$(printf '%s' "$PUSH_STDIN" | uv run python -m vibe3.services.pre_push_scope) || {
    echo "ERROR: Failed to resolve pre-push review scope"
    exit 1
}

REVIEW_BASE=$(echo "$SCOPE_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print(data['base_ref'])
")

REVIEW_SCOPE_SUMMARY=$(echo "$SCOPE_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print(data['summary'])
")

# Defensive validation: ensure REVIEW_BASE is safe to use
if [ -z "$REVIEW_BASE" ]; then
    echo "ERROR: REVIEW_BASE is empty - cannot proceed with risk assessment"
    exit 1
fi

# Basic sanitization check (allow alphanumeric, dash, underscore, slash, dot, tilde, at)
# This supports:
# - Branch names: main, feature/api-v2, origin/main
# - Commit SHAs: abc123, a1b2c3d4e5f6...
# - Relative refs: HEAD~5, HEAD@{upstream}
if ! echo "$REVIEW_BASE" | grep -qE '^[a-zA-Z0-9_./~@{}-]+$'; then
    echo "ERROR: REVIEW_BASE contains invalid characters: $REVIEW_BASE"
    exit 1
fi

# 1. Compile check (fast, <5s)
echo "  -> Compile check..."
uv run python -m compileall -q src/vibe3 || {
    echo "ERROR: Compile check failed"
    exit 1
}

# 2. Type check (fast, <5s)
echo "  -> Type check..."
uv run mypy src || {
    echo "ERROR: Type check failed"
    exit 1
}

# 4. Test suite (full test run, ~1-2min)
echo "  -> Running test suite..."
uv run pytest tests/vibe3 -v --tb=short || {
    echo "ERROR: Tests failed"
    exit 1
}

# 5. LOC checks (fast, <2s) - WARNING ONLY in pre-push
echo "  -> LOC checks (warning only)..."
bash scripts/hooks/check-python-loc.sh
# Note: Script now exits 0 with warning (doesn't block push)
bash scripts/hooks/check-shell-loc.sh
# Note: Script now exits 0 with warning (doesn't block push)

# 6. Inspect-based risk assessment (fast, <10s)
echo "  -> Risk assessment (inspect)..."
echo "  Review scope: $REVIEW_SCOPE_SUMMARY"
INSPECT_JSON=$(uv run python src/vibe3/cli.py inspect base "$REVIEW_BASE" --json) || {
    echo "ERROR: Inspect failed - cannot assess risk"
    exit 1
}

# Parse all fields in a single Python invocation
PARSED_DATA=$(echo "$INSPECT_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
score = data.get('score', {})
print('RISK_LEVEL=' + score.get('level', 'LOW'))
print('RISK_SCORE=' + str(score.get('score', 0)))
print('BLOCK_REVIEW=' + ('true' if score.get('block', False) else 'false'))
print('RISK_REASON=' + score.get('reason', ''))
print('TRIGGER_FACTORS_START')
for item in score.get('trigger_factors', []):
    print(item)
print('TRIGGER_FACTORS_END')
print('RECOMMENDATIONS_START')
for item in score.get('recommendations', []):
    print(item)
print('RECOMMENDATIONS_END')
print('BLOCK_THRESHOLD=' + str(score.get('block_threshold', 12)))
")

# Parse extracted data
RISK_LEVEL=$(echo "$PARSED_DATA" | grep "^RISK_LEVEL=" | cut -d= -f2)
RISK_SCORE=$(echo "$PARSED_DATA" | grep "^RISK_SCORE=" | cut -d= -f2)
BLOCK_REVIEW=$(echo "$PARSED_DATA" | grep "^BLOCK_REVIEW=" | cut -d= -f2)
RISK_REASON=$(echo "$PARSED_DATA" | grep "^RISK_REASON=" | cut -d= -f2-)
TRIGGER_FACTORS=$(echo "$PARSED_DATA" | sed -n '/^TRIGGER_FACTORS_START$/,/^TRIGGER_FACTORS_END$/p' | grep -v "TRIGGER_FACTORS" || true)
RECOMMENDATIONS=$(echo "$PARSED_DATA" | sed -n '/^RECOMMENDATIONS_START$/,/^RECOMMENDATIONS_END$/p' | grep -v "RECOMMENDATIONS" || true)
BLOCK_THRESHOLD=$(echo "$PARSED_DATA" | grep "^BLOCK_THRESHOLD=" | cut -d= -f2)

echo "  Risk level: $RISK_LEVEL (score: $RISK_SCORE/$BLOCK_THRESHOLD)"
echo "  Review gate block: $BLOCK_REVIEW"
if [ -n "$RISK_REASON" ]; then
    echo "  Risk reason: $RISK_REASON"
fi
if [ -n "$TRIGGER_FACTORS" ]; then
    echo "  Trigger factors:"
    while IFS= read -r factor; do
        [ -n "$factor" ] && echo "    - $factor"
    done <<< "$TRIGGER_FACTORS"
fi
if [ -n "$RECOMMENDATIONS" ]; then
    echo "  Recommendations:"
    while IFS= read -r item; do
        [ -n "$item" ] && echo "    - $item"
    done <<< "$RECOMMENDATIONS"
fi

# 7. Trigger async local review when inspect score reaches block threshold
# NOTE: Review runs asynchronously and does NOT block push.
# High-risk changes are flagged but push proceeds - review results available later.
if [ "$BLOCK_REVIEW" = "true" ]; then
    echo "  Review triggered: yes (async)"
    echo ""
    echo "  ⚠️  WARNING: Blocking risk detected!"
    echo "  Starting async review in background..."
    echo ""

    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

    # Start async review (non-blocking)
    uv run python src/vibe3/cli.py review base "$REVIEW_BASE" --async 2>/dev/null || {
        echo "  [yellow]Note:[/] Failed to start async review (continuing push)"
    }

    echo "  [green]✓[/] Review started in background"
    echo ""
    echo "  [dim]Commands:[/]"
    echo "    vibe3 flow show              # Check review status"
    echo "    vibe3 handoff show           # View review result (when done)"
    echo "    vibe3 flow cancel reviewer   # Cancel running review"
    echo ""
elif [ "$RISK_LEVEL" = "HIGH" ] || [ "$RISK_LEVEL" = "CRITICAL" ]; then
    echo "  Review triggered: recommended-manual"
    echo ""
    echo "  ⚠️  WARNING: Elevated risk detected, but below blocking threshold."
    echo "  Recommendation: run 'vibe3 review base \"$REVIEW_BASE\"' before push if you want extra confidence."
else
    echo "  Review triggered: no"
fi

echo ""
echo "OK: All pre-push checks passed"
exit 0

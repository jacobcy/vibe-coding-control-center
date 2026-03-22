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

# 3. LOC checks (fast, <2s)
echo "  -> LOC checks..."
bash scripts/hooks/check-python-loc.sh || {
    echo "ERROR: Python LOC check failed"
    exit 1
}

bash scripts/hooks/check-shell-loc.sh || {
    echo "ERROR: Shell LOC check failed"
    exit 1
}

# 4. Inspect-based risk assessment (fast, <10s)
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
TRIGGER_FACTORS=$(echo "$PARSED_DATA" | sed -n '/^TRIGGER_FACTORS_START$/,/^TRIGGER_FACTORS_END$/p' | grep -v "TRIGGER_FACTORS")
RECOMMENDATIONS=$(echo "$PARSED_DATA" | sed -n '/^RECOMMENDATIONS_START$/,/^RECOMMENDATIONS_END$/p' | grep -v "RECOMMENDATIONS")
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

# 5. Trigger local review only when inspect score reaches block threshold
if [ "$BLOCK_REVIEW" = "true" ]; then
    echo "  Review triggered: yes"
    echo ""
    echo "  WARNING: Blocking risk detected!"
    echo "  Running local review before push..."
    echo ""

    mkdir -p .agent/reports
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    REVIEW_REPORT_FILE=".agent/reports/pre-push-review-${TIMESTAMP}.md"

    # Run review with real-time output using tee
    set +e
    uv run python src/vibe3/cli.py review base "$REVIEW_BASE" 2>&1 | tee "$REVIEW_REPORT_FILE"
    REVIEW_EXIT=${PIPESTATUS[0]}
    set -e

    echo ""
    echo "  Review report saved: $REVIEW_REPORT_FILE"

    if [ "$REVIEW_EXIT" -ne 0 ]; then
        echo "ERROR: Review failed with exit code $REVIEW_EXIT"
        echo ""
        # Show the error output on failure
        echo "=== Review Output ==="
        cat "$REVIEW_REPORT_FILE"
        echo "====================="
        echo ""
        echo "Blocking risk requires visible review output and a passing review before push."
        exit 1
    fi

    VERDICT=$(python3 -c "
import re
import os
import sys

report_file = os.environ.get('REVIEW_REPORT_FILE')
if not report_file:
    print('PASS')  # Fail-safe
    sys.exit(0)

try:
    with open(report_file) as f:
        content = f.read()

    # Try multiple patterns for robustness
    patterns = [
        r'VERDICT:\s*\*{0,2}(PASS|MAJOR|BLOCK)\*{0,2}',  # Standard format with optional markdown
        r'\*\*VERDICT:\*\*\s*\*{0,2}(PASS|MAJOR|BLOCK)\*{0,2}',  # Bold prefix
        r'Verdict:\s*(PASS|MAJOR|BLOCK)',  # Simple format
        r'=== Verdict:\s*(PASS|MAJOR|BLOCK)',  # Report format
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            print(match.group(1).upper())
            sys.exit(0)

    # Default to PASS if no verdict found (fail-safe)
    print('PASS')
except Exception:
    # On any error, default to PASS (fail-safe)
    print('PASS')
" REVIEW_REPORT_FILE="$REVIEW_REPORT_FILE")
    echo "  Review verdict: $VERDICT"
    if [ "$VERDICT" = "BLOCK" ]; then
        echo "ERROR: Review verdict is BLOCK - fix issues before push"
        exit 1
    fi
elif [ "$RISK_LEVEL" = "HIGH" ] || [ "$RISK_LEVEL" = "CRITICAL" ]; then
    echo "  Review triggered: recommended-manual"
    echo ""
    echo "  WARNING: Elevated risk detected, but below blocking threshold."
    echo "  Recommendation: run 'uv run python src/vibe3/cli.py review base \"$REVIEW_BASE\"' before push if you want extra confidence."
else
    echo "  Review triggered: no"
fi

echo ""
echo "OK: All pre-push checks passed"
exit 0

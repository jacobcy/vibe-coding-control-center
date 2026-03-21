#!/usr/bin/env bash
# pre-push hook - Local review gate, catch issues before push
set -euo pipefail

echo "Running pre-push checks..."

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
INSPECT_JSON=$(uv run python src/vibe3/cli.py inspect base --json) || {
    echo "ERROR: Inspect failed - cannot assess risk"
    exit 1
}

RISK_LEVEL=$(echo "$INSPECT_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print(data.get('score', {}).get('level', 'LOW'))
")

RISK_SCORE=$(echo "$INSPECT_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print(data.get('score', {}).get('score', 0))
")

BLOCK_REVIEW=$(echo "$INSPECT_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print('true' if data.get('score', {}).get('block', False) else 'false')
")

RISK_REASON=$(echo "$INSPECT_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print(data.get('score', {}).get('reason', ''))
")

TRIGGER_FACTORS=$(echo "$INSPECT_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
for item in data.get('score', {}).get('trigger_factors', []):
    print(item)
")

RECOMMENDATIONS=$(echo "$INSPECT_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
for item in data.get('score', {}).get('recommendations', []):
    print(item)
")

echo "  Risk level: $RISK_LEVEL (score: $RISK_SCORE/10)"
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

    # Run review with real-time output, capture exit code
    set +e
    uv run python src/vibe3/cli.py review base 2>&1 | tee "$REVIEW_REPORT_FILE"
    REVIEW_EXIT=${PIPESTATUS[0]}
    set -e

    echo ""
    echo "  Review report saved: $REVIEW_REPORT_FILE"

    if [ "$REVIEW_EXIT" -ne 0 ]; then
        echo "ERROR: Review failed with exit code $REVIEW_EXIT"
        echo ""
        echo "Blocking risk requires visible review output and a passing review before push."
        exit 1
    fi

    VERDICT=$(python3 -c "
import re
content = open('$REVIEW_REPORT_FILE').read()
match = re.search(r'VERDICT:\s*\*{0,2}(PASS|MAJOR|BLOCK)\*{0,2}', content, re.IGNORECASE)
print(match.group(1).upper() if match else 'PASS')
")
    echo "  Review verdict: $VERDICT"
    if [ "$VERDICT" = "BLOCK" ]; then
        echo "ERROR: Review verdict is BLOCK - fix issues before push"
        exit 1
    fi
elif [ "$RISK_LEVEL" = "HIGH" ] || [ "$RISK_LEVEL" = "CRITICAL" ]; then
    echo "  Review triggered: recommended-manual"
    echo ""
    echo "  WARNING: Elevated risk detected, but below blocking threshold."
    echo "  Recommendation: run 'uv run python src/vibe3/cli.py review base' before push if you want extra confidence."
else
    echo "  Review triggered: no"
fi

echo ""
echo "OK: All pre-push checks passed"
exit 0

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
INSPECT_JSON=$(uv run python src/vibe3/cli.py inspect base --json 2>/dev/null) || {
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

echo "  Risk level: $RISK_LEVEL (score: $RISK_SCORE/10)"

# 5. Trigger local review on HIGH/CRITICAL risk
if [ "$RISK_LEVEL" = "HIGH" ] || [ "$RISK_LEVEL" = "CRITICAL" ]; then
    echo ""
    echo "  WARNING: High risk detected!"
    echo "  Running local review before push..."
    echo ""

    REVIEW_RESULT=$(uv run python src/vibe3/cli.py review base 2>&1) || {
        REVIEW_EXIT=$?
        echo "ERROR: Review failed with exit code $REVIEW_EXIT"
        echo "$REVIEW_RESULT"
        if [ "$RISK_LEVEL" = "CRITICAL" ]; then
            echo ""
            echo "CRITICAL risk requires passing review before push."
            exit 1
        fi
        echo ""
        echo "WARNING: Review failed but HIGH risk allows push."
    }

    VERDICT=$(echo "$REVIEW_RESULT" | grep -o "VERDICT: [A-Z]*" | head -1 | cut -d' ' -f2 || echo "PASS")
    if [ "$VERDICT" = "BLOCK" ]; then
        echo "ERROR: Review verdict is BLOCK - fix issues before push"
        exit 1
    fi
fi

echo ""
echo "OK: All pre-push checks passed"
exit 0

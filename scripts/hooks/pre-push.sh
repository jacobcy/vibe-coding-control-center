#!/usr/bin/env bash
# pre-push hook - Local quality gate, catch issues before push
set -euo pipefail

echo "Running pre-push checks..."
PUSH_STDIN=$(cat)

SCOPE_JSON=$(printf '%s' "$PUSH_STDIN" | uv run python -m vibe3.analysis.pre_push_scope) || {
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

# 3. Resolve test scope (incremental by default)
TEST_MODE="full"
TEST_REASON="forced full suite"
TEST_TARGETS=("tests/vibe3")
if [ "${VIBE_PREPUSH_FULL:-0}" != "1" ]; then
    CHANGED_FILES=$(git diff --name-only "$REVIEW_BASE..HEAD" 2>/dev/null) || {
        echo "  -> Could not compute changed files, fallback to full suite"
        CHANGED_FILES=""
    }

    TEST_PLAN_JSON=$(printf '%s\n' "$CHANGED_FILES" | uv run python -m vibe3.analysis.pre_push_test_selector) || {
        echo "  -> Failed to resolve incremental test targets, fallback to full suite"
        TEST_PLAN_JSON=""
    }

    if [ -n "$TEST_PLAN_JSON" ]; then
        TEST_MODE=$(echo "$TEST_PLAN_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print(data.get('mode', 'full'))
")
        TEST_REASON=$(echo "$TEST_PLAN_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
print(data.get('reason', 'resolved by selector'))
")
        TEST_TARGETS=()
        while IFS= read -r line; do
            TEST_TARGETS+=("$line")
        done < <(
            echo "$TEST_PLAN_JSON" | uv run python -c "
import json
import sys
data = json.load(sys.stdin)
for item in data.get('tests', []):
    print(item)
"
        )
    fi
else
    TEST_REASON="VIBE_PREPUSH_FULL=1"
fi

if [ "$TEST_MODE" = "skip" ] || [ "${#TEST_TARGETS[@]}" -eq 0 ]; then
    echo "  -> Tests skipped ($TEST_REASON)"
    echo "     (no local targets determined; CI runs full suite)"
else
    echo "  -> Running test suite ($TEST_MODE): ${TEST_REASON}"
    uv run pytest "${TEST_TARGETS[@]}" -q --tb=short || {
        echo "ERROR: Tests failed"
        exit 1
    }
fi

# 4. LOC checks (fast, <2s) - WARNING ONLY in pre-push
echo "  -> Loc checks (warning only)..."
bash scripts/hooks/check-python-loc.sh
# Note: Script now exits 0 with warning (doesn't block push)
bash scripts/hooks/check-shell-loc.sh
# Note: Script now exits 0 with warning (doesn't block push)

echo ""
echo "OK: All pre-push checks passed"
exit 0
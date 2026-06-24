#!/usr/bin/env bash
# analyze-test-performance.sh — Find slowest tests and suggest optimizations.
#
# Usage:
#   bash scripts/analyze-test-performance.sh           # Full analysis (runs tests)
#   bash scripts/analyze-test-performance.sh --quick   # Counts only (fast)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

header() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

TMPFILE=$(mktemp)
trap "rm -f '$TMPFILE'" EXIT

# --- Threshold: tests slower than this are flagged ---
THRESHOLD=0.7

# --- Parallel workers: use CPU count -1, min 2, max 4 ---
if command -v sysctl &>/dev/null; then
  CPU_COUNT=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
elif command -v nproc &>/dev/null; then
  CPU_COUNT=$(nproc 2>/dev/null || echo 4)
else
  CPU_COUNT=4
fi
PARALLEL=$((CPU_COUNT - 1))
[[ $PARALLEL -lt 2 ]] && PARALLEL=2
[[ $PARALLEL -gt 4 ]] && PARALLEL=4

PYTEST_COMMON=(
  --ignore=tests/vibe3/test_modularity
  --ignore=tests/vibe3/integration
)

header "Test Counts"

unit_count=$(uv run pytest tests/vibe3 \
  -m "not integration and not slow" \
  "${PYTEST_COMMON[@]}" \
  --co -q 2>&1 | tail -1)

slow_count=$(uv run pytest tests/vibe3 \
  -m "slow" \
  "${PYTEST_COMMON[@]}" \
  --co -q 2>&1 | tail -1)

echo -e "  Unit tests:    ${GREEN}$unit_count${NC}"
echo -e "  Slow (marked): ${YELLOW}$slow_count${NC}"

if [[ "${1:-}" == "--quick" ]]; then
    echo -e "\n  ${YELLOW}Skipped duration profiling (--quick mode)${NC}"
    exit 0
fi

# --- Run all fast unit tests with full durations, parallel ---
header "Running Unit Tests (parallel: $PARALLEL workers, durations all)"
echo "  (takes ~2 min with parallel)..."
echo "  Threshold: ${THRESHOLD}s"

uv run pytest tests/vibe3 \
    -m "not integration and not slow" \
    "${PYTEST_COMMON[@]}" \
    -n "$PARALLEL" \
    --durations=0 \
    -q --tb=no > "$TMPFILE" 2>&1 || true

# --- Extract and display ALL tests >THRESHOLD seconds ---
header "All Tests >${THRESHOLD}s"

dur_lines=$(grep -E "^[0-9]+\.[0-9]+s" "$TMPFILE" || true)

if [[ -n "$dur_lines" ]]; then
    slow_set=$(echo "$dur_lines" | awk -v t="$THRESHOLD" -F's' '$1+0 > t {print}' | sort -rn)

    if [[ -n "$slow_set" ]]; then
        echo "$slow_set"
        echo ""
        count=$(echo "$slow_set" | wc -l | tr -d ' ')
        echo -e "  ${YELLOW}>${THRESHOLD}s: $count tests${NC}"
        echo -e "  To mark for exclusion from fast CI, add: ${CYAN}@pytest.mark.slow${NC}"
    else
        echo -e "  ${GREEN}All tests are under ${THRESHOLD}s. No slow tests to flag.${NC}"
    fi
else
    echo "  No duration data found."
fi

# --- Summary ---
header "Summary"
summary=$(grep -E "passed|failed" "$TMPFILE" | tail -1 || true)
echo "  $summary"
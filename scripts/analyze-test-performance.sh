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

header "Test Counts"

unit_count=$(uv run pytest tests/vibe3 -m "not integration and not slow" \
    --ignore=tests/vibe3/test_modularity --ignore=tests/vibe3/integration \
    --co -q 2>&1 | tail -1)

slow_count=$(uv run pytest tests/vibe3 -m "slow" \
    --ignore=tests/vibe3/test_modularity --ignore=tests/vibe3/integration \
    --co -q 2>&1 | tail -1)

echo -e "  Unit tests:    ${GREEN}$unit_count${NC}"
echo -e "  Slow (marked): ${YELLOW}$slow_count${NC}"

if [[ "${1:-}" == "--quick" ]]; then
    echo -e "\n  ${YELLOW}Skipped duration profiling (--quick mode)${NC}"
    exit 0
fi

# Run unit tests with durations, capture to file
header "Running Unit Tests with --durations=20"
echo "  (takes ~3 min)..."

uv run pytest tests/vibe3 \
    -m "not integration and not slow" \
    --ignore=tests/vibe3/test_modularity \
    --ignore=tests/vibe3/integration \
    --durations=20 \
    -q --tb=no > "$TMPFILE" 2>&1

# Extract and display slowest tests
header "Slowest 20 Unit Tests"

# Print duration lines (format: "X.XXs call    tests/...")
dur_lines=$(grep -E "^[0-9]+\.[0-9]+s" "$TMPFILE" || true)
if [[ -n "$dur_lines" ]]; then
    echo "$dur_lines"
    echo ""
    # Count how many are >2s
    over_2s=$(echo "$dur_lines" | awk -F's' '$1+0 > 2 {count++} END {print count+0}')
    over_3s=$(echo "$dur_lines" | awk -F's' '$1+0 > 3 {count++} END {print count+0}')
    echo -e "  ${YELLOW}>2s: $over_2s tests | >3s: $over_3s tests${NC}"
    echo -e "  To move a slow test to Quality CI job, add: ${CYAN}@pytest.mark.slow${NC}"
else
    echo "  No duration data found."
fi

# Summary
header "Summary"
summary=$(grep -E "passed|failed" "$TMPFILE" | tail -1 || true)
echo "  $summary"

#!/usr/bin/env bash
# analyze-test-performance.sh — Analyze test suite performance and suggest optimizations.
#
# Usage:
#   bash scripts/analyze-test-performance.sh           # Full analysis
#   bash scripts/analyze-test-performance.sh --quick   # Skip duration profiling (fast)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

header() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

TMPFILE=$(mktemp)
trap "rm -f '$TMPFILE'" EXIT

header "Test Suite Performance Analysis"

# --- Test counts by category ---
header "Test Counts"

unit_count=$(uv run pytest tests/vibe3 -m "not integration and not slow" \
    --ignore=tests/vibe3/test_modularity --ignore=tests/vibe3/integration \
    --co -q 2>&1 | tail -1)

modularity_count=$(uv run pytest tests/vibe3/test_modularity --co -q 2>&1 | tail -1)

integration_count=$(uv run pytest tests/vibe3/integration --co -q 2>&1 | tail -1)

slow_count=$(uv run pytest tests/vibe3 -m "slow" \
    --ignore=tests/vibe3/test_modularity --ignore=tests/vibe3/integration \
    --co -q 2>&1 | tail -1)

echo -e "  Unit tests (not slow/integration): ${GREEN}$unit_count${NC}"
echo -e "  Modularity tests:                  ${GREEN}$modularity_count${NC}"
echo -e "  Integration tests:                  ${GREEN}$integration_count${NC}"
echo -e "  Slow tests (marked @slow):          ${YELLOW}$slow_count${NC}"

# --- Duration profiling ---
if [[ "${1:-}" != "--quick" ]]; then
    header "Slowest 20 Tests (Unit Tests Only)"
    echo "  Running unit tests with --durations=20 (this takes ~4 min)..."
    uv run pytest tests/vibe3 \
        -m "not integration and not slow" \
        --ignore=tests/vibe3/test_modularity \
        --ignore=tests/vibe3/integration \
        --durations=20 \
        -q --tb=no > "$TMPFILE" 2>&1

    echo ""
    # Extract duration lines (format: "X.XXs call tests/...")
    grep -E "^[0-9]+\.[0-9]+s" "$TMPFILE" || echo "  (no duration data found)"
    echo ""
    # Show summary line
    grep -E "passed|failed|error" "$TMPFILE" | tail -1 || true
else
    header "Duration Profiling (skipped: --quick mode)"
    echo "  Run without --quick to see slowest tests."
fi

# --- Optimization suggestions ---
header "CI Structure (3 parallel jobs)"

echo -e "
  ${GREEN}1. Lint & Type Check${NC}  (~2 min)
     ruff, black, mypy, bats, LOC checks

  ${GREEN}2. Unit Tests${NC}          (~4 min)
     3222 tests, excludes slow/integration/modularity
     Flag: ${CYAN}-m \"not integration and not slow\"${NC}

  ${GREEN}3. Quality Tests${NC}       (~30s)
     modularity (37) + integration (76) + slow (4)
     Flag: ${CYAN}-m slow${NC} + directory-based

  ${YELLOW}Optimization levers:${NC}
    1. Mark slow tests:  @pytest.mark.slow  (moves to Quality job)
    2. Use CliRunner instead of subprocess for CLI tests
    3. Mock heavy fixtures (coordinator, service init)
    4. pytest-xdist (-n auto) for parallel execution
"

echo -e "${GREEN}Done.${NC}"

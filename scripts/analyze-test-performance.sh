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
    echo "  Running unit tests with --durations=20..."
    uv run pytest tests/vibe3 \
        -m "not integration and not slow" \
        --ignore=tests/vibe3/test_modularity \
        --ignore=tests/vibe3/integration \
        --durations=20 \
        -q --tb=no 2>&1 | grep -E "^\s*(tests/|[0-9]+\.[0-9]+s)" | head -40
else
    header "Duration Profiling (skipped: --quick mode)"
    echo "  Run without --quick to see slowest tests."
fi

# --- Optimization suggestions ---
header "Optimization Suggestions"

echo -e "
  ${YELLOW}CI Structure (3 parallel jobs):${NC}
    1. Lint & Type Check  (~2 min)
    2. Unit Tests          (~5 min, excludes slow/integration/modularity)
    3. Quality Tests       (~30s, modularity + integration + slow)

  ${YELLOW}Current bottlenecks:${NC}
    - Unit tests dominate CI time (~5 min)
    - Slow tests (dry-runs, coordinator) run in Quality job

  ${YELLOW}Optimization levers:${NC}
    1. Mark more tests @pytest.mark.slow to move them to Quality job
    2. Replace subprocess CLI tests with Typer CliRunner (ms vs seconds)
    3. Use fixtures with mocks instead of real service initialization
    4. Run pytest-xdist (-n auto) for parallel test execution

  ${YELLOW}To mark a test as slow:${NC}
    import pytest

    @pytest.mark.slow
    def test_my_slow_test(): ...

  ${YELLOW}Pytest markers:${NC}
    @pytest.mark.slow        — Moves test to Quality CI job
    @pytest.mark.integration — For tests needing external services
    @pytest.mark.regression  — For regression tests (e.g., specific issues)
"

echo -e "${GREEN}Done.${NC}"

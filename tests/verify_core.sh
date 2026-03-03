#!/usr/bin/env zsh
# tests/verify_core.sh - Verification script for v3 core layer
# Runs in zsh to test zsh-specific features

set -e

# ── Setup ─────────────────────────────────────────────────
export VIBE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VIBE_LIB="$VIBE_ROOT/lib"
export VIBE_CONFIG="$VIBE_ROOT/config"

source "$VIBE_LIB/utils.sh"

# ── Test Results ──────────────────────────────────────────
typeset -i TESTS_PASSED=0
typeset -i TESTS_FAILED=0

pass() {
    echo "  ✓ $1"
    TESTS_PASSED+=1
}

fail() {
    echo "  ✗ $1"
    echo "    Error: $2"
    TESTS_FAILED+=1
}

# ── Router Tests ───────────────────────────────────────────
echo ""
echo "Router Tests:"
echo ""

# Test 1: Discover capabilities
source "$VIBE_LIB/core/router.sh"
mkdir -p "$VIBE_ROOT/lib/capabilities"

# Create test capability
cat > "$VIBE_ROOT/lib/capabilities/test.sh" <<'EOF'
vibe_test() {
    echo "test executed: $@"
}
EOF

vibe_discover_capabilities

if [[ -n "${_VIBE_CAPABILITY_MAP[test]:-}" ]]; then
    pass "Router discovers capability modules"
else
    fail "Router discovers capability modules" "Capability not found in map"
fi

# Test 2: Route to capability
output=$(vibe_route_command test arg1 arg2 2>&1)
if [[ "$output" == *"test executed: arg1 arg2"* ]]; then
    pass "Router routes to capability"
else
    fail "Router routes to capability" "Unexpected output: $output"
fi

# Test 3: Unknown command
output=$(vibe_route_command unknown_command 2>&1)
if [[ "$output" == *"Unknown command"* ]]; then
    pass "Router handles unknown command"
else
    fail "Router handles unknown command" "Unexpected output: $output"
fi

rm -f "$VIBE_ROOT/lib/capabilities/test.sh"

# ── Lifecycle Tests ────────────────────────────────────────
echo ""
echo "Lifecycle Tests:"
echo ""

source "$VIBE_LIB/core/lifecycle.sh"

# Test 1: Register before hook
before_hook() { echo "before"; }
vibe_register_before_hook "test" "before_hook"

if [[ ${#_VIBE_BEFORE_HOOKS[@]} -gt 0 ]]; then
    pass "Lifecycle registers before hooks"
else
    fail "Lifecycle registers before hooks" "No hooks registered"
fi

# Test 2: Register after hook
after_hook() { echo "after"; }
vibe_register_after_hook "test" "after_hook"

if [[ ${#_VIBE_AFTER_HOOKS[@]} -gt 0 ]]; then
    pass "Lifecycle registers after hooks"
else
    fail "Lifecycle registers after hooks" "No hooks registered"
fi

# Test 3: Execute with lifecycle
typeset before_executed=""
typeset after_executed=""
typeset command_executed=""

test_before() { before_executed="yes"; }
test_after() { after_executed="yes"; }
test_cmd() { command_executed="yes"; return 0; }

_VIBE_BEFORE_HOOKS=()
_VIBE_AFTER_HOOKS=()
vibe_register_before_hook "test" "test_before"
vibe_register_after_hook "test" "test_after"

vibe_execute_with_lifecycle "test" test_cmd

if [[ "$before_executed" == "yes" && "$command_executed" == "yes" && "$after_executed" == "yes" ]]; then
    pass "Lifecycle executes full lifecycle"
else
    fail "Lifecycle executes full lifecycle" "before=$before_executed cmd=$command_executed after=$after_executed"
fi

# ── Registry Tests ─────────────────────────────────────────
echo ""
echo "Registry Tests:"
echo ""

source "$VIBE_LIB/core/capability_registry.sh"

# Test 1: Register capability
vibe_register_capability "test" "1.0.0" "Test capability"

if [[ -n "${_VIBE_CAPABILITY_REGISTRY[test]:-}" ]]; then
    pass "Registry registers capability"
else
    fail "Registry registers capability" "Capability not in registry"
fi

# Test 2: Lookup capability
if vibe_lookup_capability "test"; then
    pass "Registry looks up capability"
else
    fail "Registry looks up capability" "Capability not found"
fi

# Test 3: Get metadata
metadata=$(vibe_get_capability_metadata "test")
if [[ "$metadata" == *"version=1.0.0"* && "$metadata" == *"Test capability"* ]]; then
    pass "Registry retrieves metadata"
else
    fail "Registry retrieves metadata" "Unexpected metadata: $metadata"
fi

# Test 4: Declare and resolve dependencies
vibe_register_capability "dep1" "1.0.0" "Dependency 1"
vibe_declare_deps "test" "dep1"

if vibe_resolve_deps "test"; then
    pass "Registry resolves dependencies"
else
    fail "Registry resolves dependencies" "Dependency resolution failed"
fi

# Test 5: Missing dependency
vibe_declare_deps "test2" "missing_dep"
if ! vibe_resolve_deps "test2" 2>/dev/null; then
    pass "Registry detects missing dependencies"
else
    fail "Registry detects missing dependencies" "Should have failed for missing dependency"
fi

# ── Summary ────────────────────────────────────────────────
echo ""
echo "==================================="
echo "Test Results:"
echo "  Passed: $TESTS_PASSED"
echo "  Failed: $TESTS_FAILED"
echo "==================================="

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi

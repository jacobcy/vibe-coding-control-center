#!/usr/bin/env zsh
# tests/test_capability_registry.sh - Tests for capability registry

# Don't use set -e to allow test failures to continue
# set -e

export VIBE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VIBE_LIB="$VIBE_ROOT/lib"
export VIBE_CONFIG="$VIBE_ROOT/config"

source "$VIBE_LIB/utils.sh"
source "$VIBE_LIB/core/capability_registry.sh"

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

# ── Tests ─────────────────────────────────────────────────
echo "Capability Registry Tests:"
echo ""

# Test 1: Register capability
echo "1. Registration"
vibe_register_capability "test_cap" "1.0.0" "Test capability"
if [[ -n "${_VIBE_CAPABILITY_REGISTRY[test_cap]:-}" ]]; then
    pass "Register capability"
else
    fail "Register capability" "Capability not in registry"
fi

# Test 2: Duplicate registration
echo "2. Duplicate registration"
output=$(vibe_register_capability "test_cap" "2.0.0" "Updated" 2>&1)
if echo "$output" | grep -q "already registered"; then
    pass "Prevent duplicate registration"
else
    fail "Prevent duplicate registration" "Should warn about duplicate. Output: $output"
fi

# Test 3: Lookup capability
echo "3. Lookup capability"
if vibe_lookup_capability "test_cap"; then
    pass "Lookup existing capability"
else
    fail "Lookup existing capability" "Should find registered capability"
fi

if ! vibe_lookup_capability "nonexistent" 2>/dev/null; then
    pass "Lookup non-existent capability"
else
    fail "Lookup non-existent capability" "Should not find unregistered capability"
fi

# Test 4: Get metadata
echo "4. Metadata retrieval"
metadata=$(vibe_get_capability_metadata "test_cap")
if [[ "$metadata" == *"version=1.0.0"* && "$metadata" == *"Test capability"* ]]; then
    pass "Retrieve capability metadata"
else
    fail "Retrieve capability metadata" "Unexpected metadata: $metadata"
fi

# Test 5: Declare dependencies
echo "5. Dependency declaration"
vibe_declare_deps "test_cap" "dep1" "dep2"
if [[ "${_VIBE_CAPABILITY_DEPS[test_cap]}" == *"dep1,dep2"* ]]; then
    pass "Declare dependencies"
else
    fail "Declare dependencies" "Dependencies not stored correctly"
fi

# Test 6: Resolve satisfied dependencies
echo "6. Dependency resolution (satisfied)"
vibe_register_capability "dep1" "1.0.0" "Dependency 1"
vibe_register_capability "dep2" "1.0.0" "Dependency 2"
vibe_declare_deps "test_cap" "dep1" "dep2"

if vibe_resolve_deps "test_cap"; then
    pass "Resolve satisfied dependencies"
else
    fail "Resolve satisfied dependencies" "Should succeed when all deps exist"
fi

# Test 7: Resolve missing dependencies
echo "7. Dependency resolution (missing)"
vibe_register_capability "test_cap2" "1.0.0" "Test 2"
vibe_declare_deps "test_cap2" "missing_dep"

if ! vibe_resolve_deps "test_cap2" 2>/dev/null; then
    pass "Detect missing dependencies"
else
    fail "Detect missing dependencies" "Should fail when deps missing"
fi

# Test 8: Capability discovery
echo "8. Capability discovery"
mkdir -p "$VIBE_ROOT/lib/capabilities"

cat > "$VIBE_ROOT/lib/capabilities/test1.sh" <<'EOF'
vibe_test1_init() {
    vibe_register_capability "test1" "1.0.0" "Test 1"
}
EOF

cat > "$VIBE_ROOT/lib/capabilities/test2.sh" <<'EOF'
vibe_test2_init() {
    vibe_register_capability "test2" "1.0.0" "Test 2"
}
EOF

# Clear registry and rediscover
_VIBE_CAPABILITY_REGISTRY=()
_VIBE_CAPABILITY_METADATA=()
vibe_discover_capabilities

if [[ -n "${_VIBE_CAPABILITY_REGISTRY[test1]:-}" && -n "${_VIBE_CAPABILITY_REGISTRY[test2]:-}" ]]; then
    pass "Discover capabilities from filesystem"
else
    fail "Discover capabilities from filesystem" "Not all capabilities discovered"
fi

# Cleanup
rm -f "$VIBE_ROOT/lib/capabilities/test1.sh"
rm -f "$VIBE_ROOT/lib/capabilities/test2.sh"

# Test 9: Capability invocation
echo "9. Capability invocation"
mkdir -p "$VIBE_ROOT/lib/capabilities"

cat > "$VIBE_ROOT/lib/capabilities/invocable.sh" <<'EOF'
vibe_invocable_init() {
    vibe_register_capability "invocable" "1.0.0" "Invocable test"
}
vibe_invocable() {
    echo "invoked with: $@"
}
EOF

# Clear and re-discover to register the capability
_VIBE_CAPABILITY_REGISTRY=()
vibe_discover_capabilities

# Now invoke
output=$(vibe_invoke_capability "invocable" "arg1" "arg2" 2>&1)
if [[ "$output" == *"invoked with: arg1 arg2"* ]]; then
    pass "Invoke capability"
else
    fail "Invoke capability" "Unexpected output: $output"
fi

# Cleanup
rm -f "$VIBE_ROOT/lib/capabilities/invocable.sh"

# Test 10: Invoke non-existent capability
echo "10. Invoke non-existent capability"
if ! vibe_invoke_capability "nonexistent" 2>/dev/null; then
    pass "Handle non-existent capability invocation"
else
    fail "Handle non-existent capability invocation" "Should fail for non-existent capability"
fi

# ── Summary ────────────────────────────────────────────────
echo ""
echo "==================================="
echo "Test Results:"
echo "  Passed: $TESTS_PASSED"
echo "  Failed: $TESTS_FAILED"
echo "==================================="

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo "✓ All capability registry tests passed!"
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi

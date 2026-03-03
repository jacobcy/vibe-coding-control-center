#!/usr/bin/env zsh
# tests/test_v3_architecture.sh - Full v3 architecture validation

set -e

export VIBE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VIBE_LIB="$VIBE_ROOT/lib"

echo "=== Vibe v3 Architecture Validation ==="
echo ""

# Test 1: Verify core layer structure
echo "1. Verifying core layer structure..."
[[ -f "$VIBE_LIB/core/router.sh" ]] || { echo "  ✗ router.sh missing"; exit 1; }
[[ -f "$VIBE_LIB/core/lifecycle.sh" ]] || { echo "  ✗ lifecycle.sh missing"; exit 1; }
[[ -f "$VIBE_LIB/core/capability_registry.sh" ]] || { echo "  ✗ capability_registry.sh missing"; exit 1; }
echo "  ✓ Core layer complete"
echo ""

# Test 2: Verify utilities structure
echo "2. Verifying utilities structure..."
[[ -f "$VIBE_LIB/utils/colors.sh" ]] || { echo "  ✗ colors.sh missing"; exit 1; }
[[ -f "$VIBE_LIB/utils/logging.sh" ]] || { echo "  ✗ logging.sh missing"; exit 1; }
[[ -f "$VIBE_LIB/utils/helpers.sh" ]] || { echo "  ✗ helpers.sh missing"; exit 1; }
echo "  ✓ Utilities complete"
echo ""

# Test 3: Verify capability templates
echo "3. Verifying capability templates..."
[[ -f "$VIBE_LIB/capabilities/template.sh" ]] || { echo "  ✗ template.sh missing"; exit 1; }
[[ -f "$VIBE_LIB/capabilities/demo.sh" ]] || { echo "  ✗ demo.sh missing (optional)"; }
echo "  ✓ Capability templates complete"
echo ""

# Test 4: Load and verify core modules
echo "4. Loading core modules..."
source "$VIBE_LIB/utils.sh"
source "$VIBE_LIB/core/capability_registry.sh"
source "$VIBE_LIB/core/lifecycle.sh"
source "$VIBE_LIB/core/router.sh"
echo "  ✓ Core modules loaded successfully"
echo ""

# Test 5: Verify capability registration
echo "5. Testing capability registration..."
vibe_register_capability "test" "1.0.0" "Test capability"
if vibe_lookup_capability "test"; then
    echo "  ✓ Capability registration works"
else
    echo "  ✗ Capability registration failed"
    exit 1
fi
echo ""

# Test 6: Verify lifecycle hooks
echo "6. Testing lifecycle hooks..."
hook_executed=""
test_hook() { hook_executed="yes"; }
vibe_register_before_hook "test_cmd" "test_hook"
_vibe_execute_before_hooks "test_cmd"
if [[ "$hook_executed" == "yes" ]]; then
    echo "  ✓ Lifecycle hooks work"
else
    echo "  ✗ Lifecycle hooks failed"
    exit 1
fi
echo ""

# Summary
echo "==================================="
echo "✓ All v3 architecture tests passed!"
echo "==================================="
echo ""
echo "Summary:"
echo "  - Core layer: 3/3 modules verified"
echo "  - Utilities: 3/3 modules verified"
echo "  - Capabilities: templates verified"
echo "  - Integration: all tests passed"

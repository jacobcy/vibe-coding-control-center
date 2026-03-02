#!/usr/bin/env zsh
# tests/test_core.bats - Unit tests for v3 core layer
# Tests router, lifecycle, and capability registry

# ── Test Setup ────────────────────────────────────────────
setup() {
    # Source test utilities
    source "$BATS_TEST_DIRNAME/../lib/utils.sh"

    # Set up test environment
    export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
    export VIBE_LIB="$VIBE_ROOT/lib"
    export VIBE_CONFIG="$VIBE_ROOT/config"
}

# ── Router Tests ───────────────────────────────────────────
@test "router: vibe_discover_capabilities finds no capabilities initially" {
    source "$VIBE_LIB/core/router.sh"

    # Create empty capabilities directory
    mkdir -p "$VIBE_ROOT/lib/capabilities"

    vibe_discover_capabilities

    [[ ${#_VIBE_CAPABILITY_MAP[@]} -eq 0 ]]
}

@test "router: vibe_discover_capabilities finds capability modules" {
    source "$VIBE_LIB/core/router.sh"

    # Create test capability
    mkdir -p "$VIBE_ROOT/lib/capabilities"
    cat > "$VIBE_ROOT/lib/capabilities/test.sh" <<'EOF'
vibe_test() {
    echo "test capability"
}
EOF

    vibe_discover_capabilities

    [[ -n "${_VIBE_CAPABILITY_MAP[test]:-}" ]]
    [[ "${_VIBE_CAPABILITY_MAP[test]}" == *"test.sh" ]]

    # Cleanup
    rm -f "$VIBE_ROOT/lib/capabilities/test.sh"
}

@test "router: vibe_route_command routes to capability" {
    source "$VIBE_LIB/core/router.sh"

    # Create test capability
    mkdir -p "$VIBE_ROOT/lib/capabilities"
    cat > "$VIBE_ROOT/lib/capabilities/test.sh" <<'EOF'
vibe_test() {
    echo "test executed: $@"
}
EOF

    vibe_discover_capabilities

    run vibe_route_command test arg1 arg2

    [[ $status -eq 0 ]]
    [[ "$output" == *"test executed: arg1 arg2"* ]]

    # Cleanup
    rm -f "$VIBE_ROOT/lib/capabilities/test.sh"
}

@test "router: vibe_route_command handles unknown command" {
    source "$VIBE_LIB/core/router.sh"

    vibe_discover_capabilities

    run vibe_route_command unknown_command

    [[ $status -eq 1 ]]
    [[ "$output" == *"Unknown command"* ]]
}

# ── Lifecycle Tests ────────────────────────────────────────
@test "lifecycle: vibe_register_before_hook registers hook" {
    source "$VIBE_LIB/core/lifecycle.sh"

    test_hook() { echo "before"; }

    vibe_register_before_hook "test" "test_hook"

    [[ ${#_VIBE_BEFORE_HOOKS[@]} -gt 0 ]]
}

@test "lifecycle: vibe_register_after_hook registers hook" {
    source "$VIBE_LIB/core/lifecycle.sh"

    test_hook() { echo "after"; }

    vibe_register_after_hook "test" "test_hook"

    [[ ${#_VIBE_AFTER_HOOKS[@]} -gt 0 ]]
}

@test "lifecycle: _vibe_execute_before_hooks executes hooks" {
    source "$VIBE_LIB/core/lifecycle.sh"

    local executed=""
    test_hook() { executed="yes"; }

    vibe_register_before_hook "test" "test_hook"
    _vibe_execute_before_hooks "test"

    [[ "$executed" == "yes" ]]
}

@test "lifecycle: _vibe_execute_after_hooks executes hooks" {
    source "$VIBE_LIB/core/lifecycle.sh"

    local executed=""
    test_hook() { executed="yes"; }

    vibe_register_after_hook "test" "test_hook"
    _vibe_execute_after_hooks "test" 0

    [[ "$executed" == "yes" ]]
}

@test "lifecycle: vibe_execute_with_lifecycle runs full lifecycle" {
    source "$VIBE_LIB/core/lifecycle.sh"

    local before_executed=""
    local after_executed=""
    local command_executed=""

    before_hook() { before_executed="yes"; }
    after_hook() { after_executed="yes"; }
    test_command() { command_executed="yes"; return 0; }

    vibe_register_before_hook "test" "before_hook"
    vibe_register_after_hook "test" "after_hook"

    vibe_execute_with_lifecycle "test" test_command

    [[ "$before_executed" == "yes" ]]
    [[ "$command_executed" == "yes" ]]
    [[ "$after_executed" == "yes" ]]
}

# ── Capability Registry Tests ──────────────────────────────
@test "registry: vibe_register_capability registers capability" {
    source "$VIBE_LIB/core/capability_registry.sh"

    vibe_register_capability "test" "1.0.0" "Test capability"

    [[ -n "${_VIBE_CAPABILITY_REGISTRY[test]:-}" ]]
    [[ "${_VIBE_CAPABILITY_METADATA[test]}" == *"version=1.0.0"* ]]
}

@test "registry: vibe_lookup_capability finds registered capability" {
    source "$VIBE_LIB/core/capability_registry.sh"

    vibe_register_capability "test" "1.0.0" "Test capability"

    vibe_lookup_capability "test"
    [[ $? -eq 0 ]]

    vibe_lookup_capability "nonexistent"
    [[ $? -eq 1 ]]
}

@test "registry: vibe_get_capability_metadata returns metadata" {
    source "$VIBE_LIB/core/capability_registry.sh"

    vibe_register_capability "test" "1.0.0" "Test capability"

    local metadata
    metadata=$(vibe_get_capability_metadata "test")

    [[ "$metadata" == *"version=1.0.0"* ]]
    [[ "$metadata" == *"description=Test capability"* ]]
}

@test "registry: vibe_declare_deps declares dependencies" {
    source "$VIBE_LIB/core/capability_registry.sh"

    vibe_declare_deps "test" "dep1" "dep2"

    [[ "${_VIBE_CAPABILITY_DEPS[test]}" == *"dep1"* ]]
    [[ "${_VIBE_CAPABILITY_DEPS[test]}" == *"dep2"* ]]
}

@test "registry: vibe_resolve_deps checks dependencies" {
    source "$VIBE_LIB/core/capability_registry.sh"

    # Register dependency
    vibe_register_capability "dep1" "1.0.0" "Dependency 1"

    # Register capability with dependency
    vibe_register_capability "test" "1.0.0" "Test capability"
    vibe_declare_deps "test" "dep1"

    # Should succeed
    vibe_resolve_deps "test"
    [[ $? -eq 0 ]]

    # Register capability with missing dependency
    vibe_register_capability "test2" "1.0.0" "Test 2"
    vibe_declare_deps "test2" "missing_dep"

    # Should fail
    run vibe_resolve_deps "test2"
    [[ $status -eq 1 ]]
}

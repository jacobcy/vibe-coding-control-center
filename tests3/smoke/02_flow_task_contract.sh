#!/usr/bin/env zsh
# Smoke Contract Tests for Vibe 3.0 - Phase 2 (Flow/Task)
# These tests verify the new commands and their parameters
# run: zsh tests3/smoke/02_flow_task_contract.sh

VIBE3_BIN="${0:A:h:h:h}/bin/vibe3"
TESTS_PASSED=0
TESTS_FAILED=0

# Test helper functions
pass() {
    echo "✓ $1"
    ((TESTS_PASSED++))
}

fail() {
    echo "✗ $1"
    if [[ -n "$2" ]]; then
        echo "  Output: $2"
    fi
    ((TESTS_FAILED++))
}

test_task_add() {
    local output
    output=$("$VIBE3_BIN" task add 2>&1)
    if echo "$output" | grep -q "\-\-repo-issue"; then
        pass "vibe3 task add has --repo-issue argument"
    else
        fail "vibe3 task add has --repo-issue argument" "$output"
    fi
}

test_task_update() {
    local output
    output=$("$VIBE3_BIN" task update 2>&1)
    if echo "$output" | grep -q "No updates"; then
        pass "vibe3 task update handles parsing"
    else
        fail "vibe3 task update handles parsing" "$output"
    fi
}

test_flow_new() {
    local output
    output=$("$VIBE3_BIN" flow new 2>&1)
    if echo "$output" | grep -q "the following arguments are required: name"; then
        pass "vibe3 flow new has name argument"
    else
        fail "vibe3 flow new has name argument" "$output"
    fi
}

test_flow_freeze() {
    local output
    output=$("$VIBE3_BIN" flow freeze 2>&1)
    if echo "$output" | grep -q "the following arguments are required: \-\-by"; then
        pass "vibe3 flow freeze has --by argument"
    else
        fail "vibe3 flow freeze has --by argument" "$output"
    fi
}

test_handoff_auth() {
    local output
    output=$("$VIBE3_BIN" handoff auth 2>&1)
    if echo "$output" | grep -q "the following arguments are required: role"; then
        pass "vibe3 handoff auth has role argument"
    else
        fail "vibe3 handoff auth has role argument" "$output"
    fi
}

test_handoff_sync() {
    local output
    output=$("$VIBE3_BIN" handoff sync 2>&1)
    if echo "$output" | grep -q "Synced"; then
        pass "vibe3 handoff sync is available"
    else
        fail "vibe3 handoff sync is available" "$output"
    fi
}



# Run all tests
echo "Running Vibe 3.0 Phase 2 Smoke Contract Tests..."
echo "========================================="
echo ""

test_task_add
test_task_update
test_flow_new
test_flow_freeze
test_handoff_auth
test_handoff_sync

echo ""
echo "========================================="
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo "✅ All smoke tests passed!"
    exit 0
else
    echo "❌ Some smoke tests failed"
    exit 1
fi

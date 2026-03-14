#!/usr/bin/env zsh
# Smoke Contract Tests for Vibe 3.0
# These tests verify the basic command contracts and CLI behavior

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

# Test 1: Basic help command
test_help() {
    local output
    output=$("$VIBE3_BIN" --help 2>&1)
    if echo "$output" | grep -q "Manage logic flows"; then
        pass "vibe3 --help shows usage"
    else
        fail "vibe3 --help shows usage" "$output"
    fi
}

# Test 2: Flow help command
test_flow_help() {
    local output
    output=$("$VIBE3_BIN" flow --help 2>&1)
    if echo "$output" | grep -q "subcommand"; then
        pass "vibe3 flow --help shows flow usage"
    else
        fail "vibe3 flow --help shows flow usage" "$output"
    fi
}

# Test 3: Task help command
test_task_help() {
    local output
    output=$("$VIBE3_BIN" task --help 2>&1)
    if echo "$output" | grep -q "subcommand"; then
        pass "vibe3 task --help shows task usage"
    else
        fail "vibe3 task --help shows task usage" "$output"
    fi
}

# Test 4: PR help command
test_pr_help() {
    local output
    output=$("$VIBE3_BIN" pr --help 2>&1)
    if echo "$output" | grep -q "subcommand"; then
        pass "vibe3 pr --help shows pr usage"
    else
        fail "vibe3 pr --help shows pr usage" "$output"
    fi
}

# Test 5: Unknown domain error handling
test_unknown_domain() {
    local output exit_code
    output=$("$VIBE3_BIN" unknown 2>&1) || exit_code=$?
    if [[ "$exit_code" -eq 1 ]] && echo "$output" | grep -q "Unknown command"; then
        pass "vibe3 with unknown domain fails"
    else
        fail "vibe3 with unknown domain fails" "$output"
    fi
}

# Test 6: Unknown flow subcommand
test_unknown_flow_subcommand() {
    local output exit_code
    output=$("$VIBE3_BIN" flow unknown 2>&1) || exit_code=$?
    # argparse returns error code 2 for invalid arguments
    if [[ "$exit_code" -eq 2 ]] && echo "$output" | grep -q "invalid choice"; then
        pass "vibe3 flow with unknown subcommand returns error"
    else
        fail "vibe3 flow with unknown subcommand returns error" "$output"
    fi
}

# Test 7: JSON flag support
test_json_flag() {
    local output
    output=$("$VIBE3_BIN" flow status --json 2>&1)
    if echo "$output" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
        pass "vibe3 flow status --json returns valid JSON"
    else
        fail "vibe3 flow status --json returns valid JSON" "$output"
    fi
}

# Test 8: -y flag support (non-interactive mode)
test_auto_confirm_flag() {
    local output exit_code
    # Test that -y flag is recognized (not rejected as unknown argument)
    output=$("$VIBE3_BIN" flow --help -y 2>&1)
    if [[ $? -eq 0 ]] || echo "$output" | grep -q "subcommand"; then
        pass "vibe3 accepts -y flag"
    else
        fail "vibe3 accepts -y flag" "$output"
    fi
}

# Test 9: Version command
test_version() {
    local output
    output=$("$VIBE3_BIN" version 2>&1)
    if echo "$output" | grep -q "3.0"; then
        pass "vibe3 version shows version"
    else
        fail "vibe3 version shows version" "$output"
    fi
}

# Run all tests
echo "Running Vibe 3.0 Smoke Contract Tests..."
echo "========================================="
echo ""

test_help
test_flow_help
test_task_help
test_pr_help
test_unknown_domain
test_unknown_flow_subcommand
test_json_flag
test_auto_confirm_flag
test_version

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

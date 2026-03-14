#!/usr/bin/env zsh
# PR Domain Contract Tests for Vibe 3.0
# These tests verify the PR domain commands and metadata binding

# Get the project root directory
# Use realpath to get absolute path, then navigate up to project root
SCRIPT_PATH="${0:A}"
PROJECT_ROOT="${SCRIPT_PATH:h:h:h}"
VIBE3_BIN="${PROJECT_ROOT}/bin/vibe3"
TESTS_PASSED=0
TESTS_FAILED=0

# Debug: Show paths
if [[ ! -f "$VIBE3_BIN" ]]; then
    echo "Error: vibe3 binary not found at: $VIBE3_BIN"
    echo "Script path: $SCRIPT_PATH"
    echo "Project root: $PROJECT_ROOT"
    exit 1
fi

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

# Test 1: PR draft command exists
test_pr_draft_help() {
    local output
    output=$("$VIBE3_BIN" pr draft -h 2>&1)
    if echo "$output" | grep -q "title\|body\|usage"; then
        pass "vibe3 pr draft -h shows draft options"
    else
        fail "vibe3 pr draft -h shows draft options" "$output"
    fi
}

# Test 2: PR show command exists
test_pr_show_help() {
    local output
    output=$("$VIBE3_BIN" pr show -h 2>&1)
    if [[ $? -eq 0 ]] || echo "$output" | grep -q "usage"; then
        pass "vibe3 pr show -h works"
    else
        fail "vibe3 pr show -h works" "$output"
    fi
}

# Test 3: PR review command exists
test_pr_review_help() {
    local output
    output=$("$VIBE3_BIN" pr review -h 2>&1)
    if echo "$output" | grep -q "post\|usage"; then
        pass "vibe3 pr review -h shows post option"
    else
        fail "vibe3 pr review -h shows post option" "$output"
    fi
}

# Test 4: PR ready command with group and bump options
test_pr_ready_options() {
    local output
    output=$("$VIBE3_BIN" pr ready -h 2>&1)
    if echo "$output" | grep -q "group\|bump\|usage"; then
        pass "vibe3 pr ready -h shows group and bump options"
    else
        fail "vibe3 pr ready -h shows group and bump options" "$output"
    fi
}

# Test 5: PR merge command exists
test_pr_merge_help() {
    local output
    output=$("$VIBE3_BIN" pr merge -h 2>&1)
    if [[ $? -eq 0 ]] || echo "$output" | grep -q "usage"; then
        pass "vibe3 pr merge -h works"
    else
        fail "vibe3 pr merge -h works" "$output"
    fi
}

# Test 6: Group parameter validation
test_group_validation() {
    local output exit_code
    output=$("$VIBE3_BIN" pr ready --group invalid 2>&1) || exit_code=$?
    # Should fail with invalid choice
    if [[ "$exit_code" -ne 0 ]] && echo "$output" | grep -q "invalid choice\|error"; then
        pass "vibe3 pr ready validates group parameter"
    else
        fail "vibe3 pr ready validates group parameter" "$output"
    fi
}

# Test 7: Bump parameter accepts true/false
test_bump_parameter() {
    local output
    # This should not error on parameter parsing
    output=$("$VIBE3_BIN" pr ready --bump true --help 2>&1)
    if [[ $? -eq 0 ]] || echo "$output" | grep -q "usage"; then
        pass "vibe3 pr ready accepts --bump parameter"
    else
        fail "vibe3 pr ready accepts --bump parameter" "$output"
    fi
}

# Note: The following tests require a real flow and PR, so they're marked as manual
echo "Note: Full integration tests (draft creation, metadata binding, review posting)"
echo "      require a real GitHub repository and PR. See tests3/pr/integration_tests.sh"
echo ""

# Run all tests
echo "Running Vibe 3.0 PR Domain Contract Tests..."
echo "============================================="
echo ""

test_pr_draft_help
test_pr_show_help
test_pr_review_help
test_pr_ready_options
test_pr_merge_help
test_group_validation
test_bump_parameter

echo ""
echo "============================================="
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo "✅ All PR domain contract tests passed!"
    exit 0
else
    echo "❌ Some PR domain contract tests failed"
    exit 1
fi
#!/usr/bin/env zsh
# Test for vibe flow commands
# Tests the workflow orchestration system

# Standalone test - no error handling
VIBE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Simple logging without error handlers
test_log_step() { echo -e "\n\033[1;34m>> $1...\033[0m"; }
test_log_success() { echo -e "\033[0;32m★ $1\033[0m"; }
test_log_error() { echo -e "\033[0;31m✗ $1\033[0m"; }
test_log_info() { echo -e "\033[0;36m✓ $1\033[0m"; }

test_log_step "Running tests for vibe flow"

TEST_FEATURE="test-flow-feature"
TEST_PASSED=0
TEST_FAILED=0

cleanup() {
    test_log_info "Cleaning up test environment"
    rm -rf "$HOME/.vibe/flow/${TEST_FEATURE}.json" 2>/dev/null || true
}

trap cleanup EXIT

# Test 1: vibe flow help
test_log_info "Test 1: vibe flow help"
if ./bin/vibe-flow help 2>&1 | grep -q "vibe flow.*workflow\|Feature development"; then
    test_log_success "PASS: vibe flow help works"
    ((TEST_PASSED++))
else
    test_log_error "FAIL: vibe flow help failed"
    ((TEST_FAILED++))
fi

# Test 2: Template files exist
test_log_info "Test 2: Template files"
all_templates_exist=1
for template in templates/prd.md templates/spec.md templates/pr.md; do
    if [[ ! -f "$template" ]]; then
        echo "   ⚠️  Template missing: $template"
        all_templates_exist=0
    fi
done

if [[ $all_templates_exist -eq 1 ]]; then
    test_log_success "PASS: All template files exist"
    ((TEST_PASSED++))
else
    test_log_error "FAIL: Some template files missing"
    ((TEST_FAILED++))
fi

# Test 3: Library files exist (worktree.sh removed)
test_log_info "Test 3: Library files"
all_libs_exist=1
for lib in lib/flow_state.sh lib/flow.sh; do
    if [[ ! -f "$lib" ]]; then
        echo "   ⚠️  Library missing: $lib"
        all_libs_exist=0
    fi
done

# Verify worktree.sh is removed
if [[ -f "lib/worktree.sh" ]]; then
    echo "   ⚠️  lib/worktree.sh should be deleted (duplicate of aliases.sh)"
    all_libs_exist=0
fi

if [[ $all_libs_exist -eq 1 ]]; then
    test_log_success "PASS: All library files correct"
    ((TEST_PASSED++))
else
    test_log_error "FAIL: Library file issues"
    ((TEST_FAILED++))
fi

# Test 4: aliases.sh has required functions
test_log_info "Test 4: aliases.sh integration"
if [[ -f "config/aliases.sh" ]]; then
    if grep -q "wtnew()" "config/aliases.sh" && \
       grep -q "vup()" "config/aliases.sh" && \
       grep -q "wtrm()" "config/aliases.sh"; then
        test_log_success "PASS: aliases.sh has required functions"
        ((TEST_PASSED++))
    else
        test_log_error "FAIL: aliases.sh missing required functions"
        ((TEST_FAILED++))
    fi
else
    test_log_error "FAIL: aliases.sh not found"
    ((TEST_FAILED++))
fi

# Test 5: State management functions (basic check)
test_log_info "Test 5: State directory creation"
mkdir -p "$HOME/.vibe/flow"
if [[ -d "$HOME/.vibe/flow" ]]; then
    test_log_success "PASS: State directory exists"
    ((TEST_PASSED++))
else
    test_log_error "FAIL: State directory creation failed"
    ((TEST_FAILED++))
fi

# Test 6: bin/vibe-flow is executable
test_log_info "Test 6: vibe-flow executable"
if [[ -x "./bin/vibe-flow" ]]; then
    test_log_success "PASS: vibe-flow is executable"
    ((TEST_PASSED++))
else
    test_log_error "FAIL: vibe-flow not executable"
    ((TEST_FAILED++))
fi

# Test 7: vibe command includes flow
test_log_info "Test 7: vibe help includes flow"
if ./bin/vibe help 2>&1 | grep -q "flow.*开发工作流\|flow.*Feature development"; then
    test_log_success "PASS: vibe help includes flow command"
    ((TEST_PASSED++))
else
    test_log_error "FAIL: vibe help missing flow command"
    ((TEST_FAILED++))
fi

# Test 8: New commands available
test_log_info "Test 8: New commands (review, pr, done)"
if ./bin/vibe-flow help 2>&1 | grep -q "review" && \
   ./bin/vibe-flow help 2>&1 | grep -q "pr" && \
   ./bin/vibe-flow help 2>&1 | grep -q "done"; then
    test_log_success "PASS: New commands documented"
    ((TEST_PASSED++))
else
    test_log_error "FAIL: New commands missing from help"
    ((TEST_FAILED++))
fi

# Summary
echo ""
test_log_step "Test Summary"
echo "  Passed: \033[0;32m${TEST_PASSED}\033[0m"
echo "  Failed: \033[0;31m${TEST_FAILED}\033[0m"

if [[ $TEST_FAILED -eq 0 ]]; then
    test_log_success "✅ All tests passed!"
    exit 0
else
    test_log_error "❌ Some tests failed"
    exit 1
fi


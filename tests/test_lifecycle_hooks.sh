#!/usr/bin/env zsh
# tests/test_lifecycle_hooks.sh - Tests for lifecycle hooks

export VIBE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VIBE_LIB="$VIBE_ROOT/lib"

source "$VIBE_LIB/utils.sh"
source "$VIBE_LIB/core/lifecycle.sh"

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
echo "Lifecycle Hooks Tests:"
echo ""

# Test 1: Register before hook
echo "1. Before hook registration"
before_test_hook() { echo "before"; }
vibe_register_before_hook "test" "before_test_hook"
if [[ ${#_VIBE_BEFORE_HOOKS[@]} -gt 0 ]]; then
    pass "Register before hook"
else
    fail "Register before hook" "No hooks registered"
fi

# Test 2: Register after hook
echo "2. After hook registration"
after_test_hook() { echo "after"; }
vibe_register_after_hook "test" "after_test_hook"
if [[ ${#_VIBE_AFTER_HOOKS[@]} -gt 0 ]]; then
    pass "Register after hook"
else
    fail "Register after hook" "No hooks registered"
fi

# Test 3: Execute before hooks
echo "3. Execute before hooks"
typeset before_executed=""
test_before() { before_executed="yes"; }
_VIBE_BEFORE_HOOKS=()
vibe_register_before_hook "cmd" "test_before"
_vibe_execute_before_hooks "cmd" "arg1" "arg2"
if [[ "$before_executed" == "yes" ]]; then
    pass "Execute before hooks"
else
    fail "Execute before hooks" "Hook not executed"
fi

# Test 4: Execute after hooks
echo "4. Execute after hooks"
typeset after_executed=""
typeset received_exit_code=""
test_after() {
    after_executed="yes"
    received_exit_code="$1"
}
_VIBE_AFTER_HOOKS=()
vibe_register_after_hook "cmd" "test_after"
_vibe_execute_after_hooks "cmd" 42 "arg1" "arg2"
if [[ "$after_executed" == "yes" && "$received_exit_code" == "42" ]]; then
    pass "Execute after hooks with exit code"
else
    fail "Execute after hooks with exit code" "after=$after_executed code=$received_exit_code"
fi

# Test 5: Full lifecycle execution
echo "5. Full lifecycle execution"
typeset before_ran=""
typeset cmd_ran=""
typeset after_ran=""

hook_before_full() { before_ran="yes"; }
hook_after_full() { after_ran="yes"; }
test_command() { cmd_ran="yes"; return 0; }

_VIBE_BEFORE_HOOKS=()
_VIBE_AFTER_HOOKS=()
vibe_register_before_hook "full" "hook_before_full"
vibe_register_after_hook "full" "hook_after_full"

vibe_execute_with_lifecycle "full" test_command

if [[ "$before_ran" == "yes" && "$cmd_ran" == "yes" && "$after_ran" == "yes" ]]; then
    pass "Full lifecycle execution"
else
    fail "Full lifecycle execution" "before=$before_ran cmd=$cmd_ran after=$after_ran"
fi

# Test 6: Lifecycle stops on before hook failure
echo "6. Lifecycle stops on before hook failure"
typeset before_ran=""
typeset cmd_ran=""
typeset after_ran=""

failing_before() {
    before_ran="yes"
    return 1
}
never_run_cmd() { cmd_ran="yes"; }
never_run_after() { after_ran="yes"; }

_VIBE_BEFORE_HOOKS=()
_VIBE_AFTER_HOOKS=()
vibe_register_before_hook "fail" "failing_before"
vibe_register_after_hook "fail" "never_run_after"

vibe_execute_with_lifecycle "fail" never_run_cmd 2>/dev/null || true

if [[ "$before_ran" == "yes" && "$cmd_ran" == "" && "$after_ran" == "" ]]; then
    pass "Lifecycle stops on before hook failure"
else
    fail "Lifecycle stops on before hook failure" "before=$before_ran cmd=$cmd_ran after=$after_ran"
fi

# Test 7: Multiple hooks execution order
echo "7. Multiple hooks execution order"
typeset -a execution_order=()

hook1() { execution_order+=("hook1"); }
hook2() { execution_order+=("hook2"); }
hook3() { execution_order+=("hook3"); }

_VIBE_BEFORE_HOOKS=()
vibe_register_before_hook "multi" "hook1"
vibe_register_before_hook "multi" "hook2"
vibe_register_before_hook "multi" "hook3"

_vibe_execute_before_hooks "multi"

if [[ "${execution_order[1]}" == "hook1" && "${execution_order[2]}" == "hook2" && "${execution_order[3]}" == "hook3" ]]; then
    pass "Multiple hooks execute in registration order"
else
    fail "Multiple hooks execute in registration order" "Order: ${execution_order[@]}"
fi

# Test 8: Hook receives arguments
echo "8. Hook receives command arguments"
typeset received_args=""
args_hook() { received_args="$@"; }

_VIBE_BEFORE_HOOKS=()
vibe_register_before_hook "args" "args_hook"
_vibe_execute_before_hooks "args" "arg1" "arg2" "arg3"

if [[ "$received_args" == "arg1 arg2 arg3" ]]; then
    pass "Hook receives command arguments"
else
    fail "Hook receives command arguments" "Received: $received_args"
fi

# Test 9: After hook receives exit code
echo "9. After hook receives exit code"
typeset received_code=""
exit_hook() { received_code="$1"; }

_VIBE_AFTER_HOOKS=()
vibe_register_after_hook "exit" "exit_hook"
_vibe_execute_after_hooks "exit" 99 "arg"

if [[ "$received_code" == "99" ]]; then
    pass "After hook receives exit code"
else
    fail "After hook receives exit code" "Received: $received_code"
fi

# ── Summary ────────────────────────────────────────────────
echo ""
echo "==================================="
echo "Test Results:"
echo "  Passed: $TESTS_PASSED"
echo "  Failed: $TESTS_FAILED"
echo "==================================="

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo "✓ All lifecycle hooks tests passed!"
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi

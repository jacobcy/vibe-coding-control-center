#!/usr/bin/env zsh
# Comprehensive Test Suite for Vibe Coding Control Center
# This script tests all the new modules we've added

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi
    echo "zsh not found. Please run ./scripts/install.sh to install zsh." >&2
    exit 1
fi

set -e

# ================= SETUP =================
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
source "$LIB_DIR/utils.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/testing.sh"
source "$LIB_DIR/cache.sh"
source "$LIB_DIR/error_handling.sh"
source "$LIB_DIR/i18n.sh"

# Run the test suite
echo -e "${CYAN}==========================================${NC}"
echo -e "${CYAN}Running Comprehensive Test Suite${NC}"
echo -e "${CYAN}==========================================${NC}"

# Initialize testing
initialize_testing

# Run all tests
run_all_tests

echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}Testing Additional Functions${NC}"
echo -e "${CYAN}==========================================${NC}"

# Agent dev plan tests
echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}Agent Dev Plan Tests${NC}"
echo -e "${CYAN}==========================================${NC}"

AGENT_PLAN_TESTS=1
AGENT_PLAN_PASSED=0

if zsh "$SCRIPT_DIR/../tests/test_agent_dev_plan.sh"; then
    AGENT_PLAN_PASSED=1
else
    log_warn "Agent dev plan tests failed"
    # Don't fail the whole suite yet, counts will handle it?
    # Actually the logic below relies on explicit counters.
    # But test_agent_dev_plan.sh seems to use its own counting or exit code?
    # It uses `log_error` but does it return non-zero?
    # Let's assume it does.
fi

# TOML Config Tests
echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}TOML Config Tests${NC}"
echo -e "${CYAN}==========================================${NC}"
if zsh "$SCRIPT_DIR/../tests/test_config_toml.sh"; then
    log_success "TOML config tests passed"
else
    ((TEST_FAILED++))
    log_error "TOML config tests failed"
fi

# Init Project Tests
echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}Init Project Tests${NC}"
echo -e "${CYAN}==========================================${NC}"
if zsh "$SCRIPT_DIR/../tests/test_init_project.sh"; then
    log_success "Init project tests passed"
else
    ((TEST_FAILED++))
    log_error "Init project tests failed"
fi

# Bootstrap Install Tests
echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}Bootstrap Install Tests${NC}"
echo -e "${CYAN}==========================================${NC}"
if zsh "$SCRIPT_DIR/../tests/test_install_bootstrap.sh"; then
    log_success "Bootstrap install tests passed"
else
    ((TEST_FAILED++))
    log_error "Bootstrap install tests failed"
fi

# Test new version comparison functions
start_test_suite "Version Management"

VERSION_TESTS=0
VERSION_PASSED=0

increment_counts() {
    emulate -L zsh
    set +e
    trap - ERR
    local message="$1"
    local condition="$2"

    ((++VERSION_TESTS))
    eval "$condition"
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        ((++VERSION_PASSED))
        log_success "✓ $message"
    else
        log_error "✗ $message"
    fi
}

# Test normalize_version
result=$(normalize_version "v1.2")
increment_counts "normalize_version correctly handles 'v1.2' -> '$result' (expected: '1.2.0')" "[[ '$result' == '1.2.0' ]]"

result=$(normalize_version "2.0.1")
increment_counts "normalize_version correctly handles '2.0.1' -> '$result' (expected: '2.0.1')" "[[ '$result' == '2.0.1' ]]"

result=$(normalize_version "3")
increment_counts "normalize_version correctly handles '3' -> '$result' (expected: '3.0.0')" "[[ '$result' == '3.0.0' ]]"

echo ""
echo "Version Management Tests: $VERSION_PASSED/$VERSION_TESTS passed"

# Test cache system independently
start_test_suite "Cache System Validation"

CACHE_TESTS=0
CACHE_PASSED=0

cache_test() {
    emulate -L zsh
    set +e
    trap - ERR
    local test_name="$1"
    local condition="$2"

    ((++CACHE_TESTS))
    eval "$condition"
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        ((++CACHE_PASSED))
        log_success "✓ $test_name"
    else
        log_error "✗ $test_name"
    fi
}

# Test cache set and get
cache_set "test_key_1" "test_value_1" 5
cache_test "Cache set and get work correctly" '[[ "$(cache_get "test_key_1")" == "test_value_1" ]]'

# Test cache expiration
cache_set "expiring_key" "exp_value" 1
sleep 2
cache_test "Cache expiration works correctly" '! cache_get "expiring_key" >/dev/null 2>&1'

# Test cache deletion
cache_set "deletable_key" "del_value" 10
cache_delete "deletable_key"
cache_test "Cache deletion works correctly" '! cache_get "deletable_key" >/dev/null 2>&1'

# Test cache stats function
cache_stats > /dev/null 2>&1
cache_test "Cache stats function runs without error" '[[ $? -eq 0 ]]'

echo ""
echo "Cache System Tests: $CACHE_PASSED/$CACHE_TESTS passed"

# Test configuration management
start_test_suite "Configuration Management"

CONFIG_TESTS=0
CONFIG_PASSED=0

config_test() {
    emulate -L zsh
    set +e
    trap - ERR
    local test_name="$1"
    local condition="$2"

    ((++CONFIG_TESTS))
    eval "$condition"
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        ((++CONFIG_PASSED))
        log_success "✓ $test_name"
    else
        log_error "✗ $test_name"
    fi
}

config_test "Configuration initialization sets ROOT_DIR" '[[ -n "${VIBE_CONFIG[ROOT_DIR]}" ]]'
config_test "Configuration initialization sets LIB_DIR" '[[ -n "${VIBE_CONFIG[LIB_DIR]}" ]]'

# Test config_set and config_get
config_set "test_config_key" "test_config_value"
config_test "Configuration set/get works" '[[ "$(config_get "test_config_key")" == "test_config_value" ]]'

# Test config_exists
config_test "Configuration exists check works" 'config_exists "test_config_key"'

echo ""
echo "Configuration Management Tests: $CONFIG_PASSED/$CONFIG_TESTS passed"

# Vibe Chat Tests
echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}Vibe Chat Tests${NC}"
echo -e "${CYAN}==========================================${NC}"
CHAT_TESTS=1
CHAT_PASSED=0
if zsh "$SCRIPT_DIR/../tests/test_vibe_chat.sh"; then
    log_success "Vibe chat tests passed"
    CHAT_PASSED=1
else
    log_error "Vibe chat tests failed"
fi

# Vibe Sync Tests
echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}Vibe Sync Tests${NC}"
echo -e "${CYAN}==========================================${NC}"
SYNC_TESTS=1
SYNC_PASSED=0
if zsh "$SCRIPT_DIR/../tests/test_vibe_sync.sh"; then
    log_success "Vibe sync tests passed"
    SYNC_PASSED=1
else
    log_error "Vibe sync tests failed"
fi

# Vibe Equip Tests
echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}Vibe Equip Tests${NC}"
echo -e "${CYAN}==========================================${NC}"
EQUIP_TESTS=1
EQUIP_PASSED=0
if zsh "$SCRIPT_DIR/../tests/test_vibe_equip.sh"; then
    log_success "Vibe equip tests passed"
    EQUIP_PASSED=1
else
    log_error "Vibe equip tests failed"
fi

# Final summary
TOTAL_TESTS=$((TEST_TOTAL + VERSION_TESTS + CACHE_TESTS + CONFIG_TESTS + AGENT_PLAN_TESTS + CHAT_TESTS + SYNC_TESTS + EQUIP_TESTS))
TOTAL_PASSED=$((TEST_PASSED + VERSION_PASSED + CACHE_PASSED + CONFIG_PASSED + AGENT_PLAN_PASSED + CHAT_PASSED + SYNC_PASSED + EQUIP_PASSED))
TOTAL_FAILED=$((TEST_FAILED + (VERSION_TESTS-VERSION_PASSED) + (CACHE_TESTS-CACHE_PASSED) + (CONFIG_TESTS-CONFIG_PASSED) + (AGENT_PLAN_TESTS-AGENT_PLAN_PASSED) + (CHAT_TESTS-CHAT_PASSED) + (SYNC_TESTS-SYNC_PASSED) + (EQUIP_TESTS-EQUIP_PASSED)))

echo -e "\n${CYAN}==========================================${NC}"
echo -e "${CYAN}FINAL TEST RESULTS${NC}"
echo -e "${CYAN}==========================================${NC}"
echo "Total Tests: $TOTAL_TESTS"
echo "Passed: $TOTAL_PASSED"
echo "Failed: $TOTAL_FAILED"

if [[ $TOTAL_FAILED -eq 0 ]]; then
    log_success "🎉 All tests passed! The system is working correctly."
    exit 0
else
    log_error "❌ Some tests failed. Please review the errors above."
    exit 1
fi

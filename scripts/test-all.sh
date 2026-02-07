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
    local test_name="$1"
    local condition="$2"

    ((CONFIG_TESTS++))
    if eval "$condition"; then
        ((CONFIG_PASSED++))
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

# Final summary
TOTAL_TESTS=$((TEST_TOTAL + VERSION_TESTS + CACHE_TESTS + CONFIG_TESTS))
TOTAL_PASSED=$((TEST_PASSED + VERSION_PASSED + CACHE_PASSED + CONFIG_PASSED))
TOTAL_FAILED=$((TEST_FAILED + (VERSION_TESTS-VERSION_PASSED) + (CACHE_TESTS-CACHE_PASSED) + (CONFIG_TESTS-CONFIG_PASSED)))

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

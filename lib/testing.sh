#!/usr/bin/env zsh
# Testing Framework for Vibe Coding Control Center

# Test result counters
TEST_TOTAL=0
TEST_PASSED=0
TEST_FAILED=0

# Test output file
TEST_OUTPUT_FILE=""

# Initialize testing framework
initialize_testing() {
    TEST_TOTAL=0
    TEST_PASSED=0
    TEST_FAILED=0
    TEST_OUTPUT_FILE=""
    log_info "Testing framework initialized"
}

# Start a test suite
start_test_suite() {
    local suite_name="$1"
    echo "=================================="
    echo "Starting Test Suite: $suite_name"
    echo "=================================="
    initialize_testing
}

# Finish a test suite
finish_test_suite() {
    echo ""
    echo "=================================="
    echo "Test Suite Results:"
    echo "  Total: $TEST_TOTAL"
    echo "  Passed: $TEST_PASSED"
    echo "  Failed: $TEST_FAILED"
    echo "=================================="

    if [[ $TEST_FAILED -eq 0 ]]; then
        log_success "All tests passed!"
        return 0
    else
        log_error "$TEST_FAILED tests failed!"
        return 1
    fi
}

# Assert function for testing
assert_true() {
    emulate -L zsh
    set +e
    local condition="$1"
    local message="${2:-Assertion failed}"

    ((++TEST_TOTAL))

    trap - ERR
    eval "$condition"
    local status=$?

    if [[ $status -eq 0 ]]; then
        log_success "✓ $message"
        ((++TEST_PASSED))
    else
        log_error "✗ $message"
        ((++TEST_FAILED))
    fi
}

assert_false() {
    emulate -L zsh
    set +e
    local condition="$1"
    local message="${2:-Assertion failed}"

    ((++TEST_TOTAL))

    trap - ERR
    eval "$condition"
    local status=$?

    if [[ $status -ne 0 ]]; then
        log_success "✓ $message"
        ((++TEST_PASSED))
    else
        log_error "✗ $message"
        ((++TEST_FAILED))
    fi
}

assert_equals() {
    local expected="$1"
    local actual="$2"
    local message="${3:-Values are not equal}"

    ((++TEST_TOTAL))

    if [[ "$expected" == "$actual" ]]; then
        log_success "✓ $message (Expected: '$expected', Got: '$actual')"
        ((++TEST_PASSED))
    else
        log_error "✗ $message (Expected: '$expected', Got: '$actual')"
        ((++TEST_FAILED))
    fi
}

assert_not_equals() {
    local expected="$1"
    local actual="$2"
    local message="${3:-Values should not be equal}"

    ((++TEST_TOTAL))

    if [[ "$expected" != "$actual" ]]; then
        log_success "✓ $message (Expected: '$expected' != '$actual')"
        ((++TEST_PASSED))
    else
        log_error "✗ $message (Expected: '$expected' != '$actual')"
        ((++TEST_FAILED))
    fi
}

# Mock function for testing
mock_command() {
    local cmd="$1"
    local return_code="${2:-0}"
    local output="${3:-}"

    # Create a mock function that returns the specified values
    eval "
    $cmd() {
        echo '$output'
        return $return_code
    }
    "
}

# Function to temporarily replace a function for testing
stub_function() {
    local func_name="$1"
    local new_behavior="$2"

    # Save original function
    local orig_func_content
    orig_func_content=$(declare -f "$func_name" 2>/dev/null)

    if [[ -n "$orig_func_content" ]]; then
        eval "original_${func_name//-/_}() ${orig_func_content#*$func_name}"
    fi

    # Replace with stub
    eval "$func_name() { $new_behavior; }"
}

# Run tests with specific timeout
run_test_with_timeout() {
    local test_func="$1"
    local timeout="${2:-10}"  # Default 10 seconds

    echo "Running test with timeout ($timeout sec): $test_func"

    # Run test with timeout
    if timeout "$timeout" zsh -c "source '$SCRIPT_DIR/../lib/utils.sh'; source '$SCRIPT_DIR/../lib/testing.sh'; $test_func"; then
        log_success "✓ $test_func completed within timeout"
        ((++TEST_PASSED))
    else
        log_error "✗ $test_func timed out or failed"
        ((++TEST_FAILED))
    fi
    ((++TEST_TOTAL))
}

# Test utilities module
test_utilities() {
    echo "Testing utility functions..."

    # Test validate_input function
    assert_true "validate_input 'hello' 'false'" "validate_input should accept valid input"
    assert_true "validate_input '' 'true'" "validate_input should accept empty input when allowed"
    assert_false "validate_input '' 'false'" "validate_input should reject empty input when not allowed"

    # Test validate_path function
    assert_true "validate_path '/tmp' 'Invalid path'" "validate_path should accept valid path"
    assert_false "validate_path '../..' 'Invalid path'" "validate_path should reject path traversal"

    # Test validate_filename function
    assert_true "validate_filename 'valid_filename.txt'" "validate_filename should accept valid filename"
    assert_false "validate_filename '../forbidden.txt'" "validate_filename should reject path with parent directory reference"
}

# Test security functions
test_security() {
    echo "Testing security functions..."

    # Test path traversal protection
    assert_false "validate_path '../../../etc/passwd' 'Path traversal blocked'" "Path traversal should be blocked"
    assert_false "validate_path '/normal/path'/'../../../forbidden' 'Path traversal blocked'" "Complex path traversal should be blocked"

    # Test command injection prevention
    assert_false "validate_input 'malicious; rm -rf /' 'false'" "Command injection should be blocked"
    assert_false "validate_input 'echo hello && rm -rf /' 'false'" "Command chaining should be blocked"
}

# Test configuration management
test_config() {
    echo "Testing configuration management..."

    # Initialize config
    initialize_config

    # Test that config values are set
    assert_true "[[ -n \"\${VIBE_CONFIG[ROOT_DIR]}\" ]]" "Config ROOT_DIR should be set"
    assert_true "[[ -n \"\${VIBE_CONFIG[LIB_DIR]}\" ]]" "Config LIB_DIR should be set"

    # Test config_get function
    local root_dir_val
    root_dir_val=$(config_get "ROOT_DIR")
    assert_not_equals "" "$root_dir_val" "config_get should return value for ROOT_DIR"

    # Test config_set function
    config_set "TEST_VALUE" "test_data"
    local test_val
    test_val=$(config_get "TEST_VALUE")
    assert_equals "test_data" "$test_val" "config_set and config_get should work together"
}

# Test cache system
test_cache() {
    echo "Testing cache system..."

    # Test cache set/get
    cache_set "test_key" "test_value" 10
    local cached_value
    cached_value=$(cache_get "test_key")
    assert_equals "test_value" "$cached_value" "cache_get should return previously set value"

    # Test cache expiration
    cache_set "expiring_key" "expiring_value" 1
    sleep 2  # Wait for expiration
    if cache_get "expiring_key"; then
        assert_false "true" "Expired cache should not be retrievable"
    else
        assert_true "true" "Expired cache correctly removed"
    fi

    # Test cache deletion
    cache_set "deletable_key" "deletable_value" 10
    cache_delete "deletable_key"
    if cache_get "deletable_key"; then
        assert_false "true" "Deleted cache should not be retrievable"
    else
        assert_true "true" "Deleted cache correctly removed"
    fi
}

# Run all tests
run_all_tests() {
    start_test_suite "Complete Test Suite"

    test_utilities
    test_security
    test_config
    test_cache

    finish_test_suite
}

# Run specific test
run_single_test() {
    local test_name="$1"

    start_test_suite "Single Test: $test_name"

    case "$test_name" in
        "utilities") test_utilities ;;
        "security") test_security ;;
        "config") test_config ;;
        "cache") test_cache ;;
        *)
            log_error "Unknown test: $test_name"
            return 1
            ;;
    esac

    finish_test_suite
}

# Initialize testing framework
initialize_testing

#!/usr/bin/env zsh
# Test script for the new configuration loading system

# Source required libraries
source "$(pwd)/lib/utils.sh"
source "$(pwd)/lib/config_loader.sh"

# Function to run a test
run_test() {
    local test_name="$1"
    local expected_result="$2"
    shift 2
    echo -n "Testing $test_name... "

    local output
    output=$("$@" 2>&1)
    local result=$?

    if [[ $result -eq $expected_result ]]; then
        echo "✓ PASS"
        return 0
    else
        echo "✗ FAIL (expected $expected_result, got $result)"
        echo "  Output: $output"
        return 1
    fi
}

# Save original directory
ORIGINAL_PWD=$(pwd)

# Set up test environment
setup_test_env() {
    # Create a temporary directory for testing
    TEST_DIR=$(mktemp -d)
    export HOME="$TEST_DIR"

    # Create .vibe directory and keys.env for testing
    mkdir -p "$TEST_DIR/.vibe"
    echo 'TEST_KEY="test_value"' > "$TEST_DIR/.vibe/keys.env"
    echo 'API_KEY="secret123"' >> "$TEST_DIR/.vibe/keys.env"

    # Create a project-level config for testing
    PROJECT_DIR="$TEST_DIR/project"
    mkdir -p "$PROJECT_DIR/.vibe"
    echo 'TEST_KEY="project_override"' > "$PROJECT_DIR/.vibe/keys.env"
    echo 'PROJECT_ONLY="exists"' >> "$PROJECT_DIR/.vibe/keys.env"

    # Change to project directory for tests
    cd "$PROJECT_DIR"
}

teardown_test_env() {
    cd "$ORIGINAL_PWD"
    rm -rf "$TEST_DIR"
}

echo "Running configuration loader tests..."

# Setup test environment
setup_test_env

total_tests=0
passed_tests=0

# Test 1: Load configuration successfully
if run_test "Configuration loading" 0 load_configuration; then
    passed_tests=$((passed_tests + 1))
fi
total_tests=$((total_tests + 1))

# Test 2: Get config value from global config
if run_test "Get global config value" 0 zsh -f -c 'source "'"$ORIGINAL_PWD/lib/config_loader.sh"'"; load_configuration; value=$(get_config_value "TEST_KEY"); [[ "$value" == "project_override" ]]'; then
    passed_tests=$((passed_tests + 1))
fi
total_tests=$((total_tests + 1))

# Test 3: Get config value that exists only in project config
if run_test "Get project-only config value" 0 zsh -f -c 'source "'"$ORIGINAL_PWD/lib/config_loader.sh"'"; load_configuration; value=$(get_config_value "PROJECT_ONLY"); [[ "$value" == "exists" ]]'; then
    passed_tests=$((passed_tests + 1))
fi
total_tests=$((total_tests + 1))

# Test 4: Get non-existent config value with default
if run_test "Get non-existent config value with default" 0 zsh -f -c 'source "'"$ORIGINAL_PWD/lib/config_loader.sh"'"; load_configuration; value=$(get_config_value "NONEXISTENT" "default"); [[ "$value" == "default" ]]'; then
    passed_tests=$((passed_tests + 1))
fi
total_tests=$((total_tests + 1))

# Test 5: Test secure path validation (valid path)
if run_test "Secure path validation (valid)" 0 validate_secure_path "$HOME/.vibe/keys.env"; then
    passed_tests=$((passed_tests + 1))
fi
total_tests=$((total_tests + 1))

# Test 6: Test secure path validation (invalid path with traversal)
if run_test "Secure path validation (invalid traversal)" 1 validate_secure_path "$HOME/.vibe/../keys.env"; then
    passed_tests=$((passed_tests + 1))
fi
total_tests=$((total_tests + 1))

# Test 7: Test cache functionality (performance)
start_time=$(date +%s.%N)
load_configuration
first_load_time=$(date +%s.%N)
load_configuration  # This should use cache
second_load_time=$(date +%s.%N)
cache_time=$(echo "$second_load_time - $first_load_time" | bc)
if (( $(echo "$cache_time < 0.01" | bc -l) )); then
    echo "Testing cache performance... ✓ PASS (cached load was fast)"
    passed_tests=$((passed_tests + 1))
else
    echo "Testing cache performance... ✗ SLOW (cache may not be working)"
fi
total_tests=$((total_tests + 1))

# Teardown test environment
teardown_test_env

echo
echo "Tests completed: $passed_tests/$total_tests passed"

if [[ $passed_tests -eq $total_tests ]]; then
    echo "✓ All tests passed! Configuration loader is working correctly."
    exit 0
else
    echo "✗ Some tests failed. Please review the configuration loader implementation."
    exit 1
fi
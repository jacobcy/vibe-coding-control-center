#!/bin/bash
# simple_test.sh
# Simple test to debug validation functions

# Source the enhanced utils
SCRIPT_DIR="$(dirname "$0")"
source "$SCRIPT_DIR/../../lib/utils.sh"

echo "Testing basic functionality..."

# Test simple logging
log_info "Simple logging test passed"

# Test validate_input with a simple string
test_string="hello world"
if validate_input "$test_string" "false"; then
    echo "validate_input test passed for: $test_string"
else
    echo "validate_input test FAILED for: $test_string"
fi

# Test validate_path with a simple path
test_path="/tmp/simple_test"
if validate_path "$test_path" "simple test"; then
    echo "validate_path test passed for: $test_path"
else
    echo "validate_path test FAILED for: $test_path"
fi

# Test the command injection detection
injection_test="normal_string"
if validate_input "$injection_test" "false"; then
    echo "Injection detection test passed for: $injection_test"
else
    echo "Injection detection test FAILED for: $injection_test"
fi

# Test potential injection strings (this should fail as expected)
potentially_bad="test && echo bad"
if ! validate_input "$potentially_bad" "false"; then
    echo "Command injection correctly blocked: $potentially_bad"
else
    echo "Command injection NOT blocked: $potentially_bad"
fi

# Test another injection variant
potentially_bad2="test | echo bad"
if ! validate_input "$potentially_bad2" "false"; then
    echo "Command injection correctly blocked: $potentially_bad2"
else
    echo "Command injection NOT blocked: $potentially_bad2"
fi

# Test safe string with special chars (but not injection)
safe_test="test-string_with.Various-chars"
if validate_input "$safe_test" "false"; then
    echo "Safe string correctly allowed: $safe_test"
else
    echo "Safe string incorrectly blocked: $safe_test"
fi

echo "Simple tests completed"
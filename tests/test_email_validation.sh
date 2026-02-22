#!/usr/bin/env zsh
# tests/test_email_validation.sh
# Test suite for email validation logic

# Source the library to test
source "lib/email_validation.sh"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Test runner
run_test() {
    local email="$1"
    local expected="$2"
    local message="$3"
    
    if validate_email "$email"; then
        actual=0
    else
        actual=1
    fi
    
    if [[ "$actual" == "$expected" ]]; then
        echo "${GREEN}PASS${NC}: $message ($email)"
        return 0
    else
        echo "${RED}FAIL${NC}: $message ($email) - Expected $expected, Got $actual"
        return 1
    fi
}

echo "Running Email Validation Tests..."
FAILED=0

# Valid Cases
run_test "user@example.com" 0 "Standard valid email" || FAILED=1
run_test "firstname.lastname@example.com" 0 "Dot in local part" || FAILED=1
run_test "email@subdomain.example.com" 0 "Subdomain" || FAILED=1
run_test "1234567890@example.com" 0 "Digits in local part" || FAILED=1
run_test "email@example-one.com" 0 "Hyphen in domain" || FAILED=1
run_test "_______@example.com" 0 "Underscore in local part" || FAILED=1
run_test "email@example.name" 0 "New TLD" || FAILED=1
run_test "email@example.museum" 0 "Long TLD" || FAILED=1
run_test "email@example.co.jp" 0 "Country code TLD" || FAILED=1
run_test "firstname+lastname@example.com" 0 "Plus sign" || FAILED=1

# Invalid Cases - SHOULD FAIL (return 1)
run_test "plainaddress" 1 "Missing @ domain" || FAILED=1
run_test "#@%^%#$@#$@#.com" 1 "Garbage" || FAILED=1
run_test "@example.com" 1 "Missing local part" || FAILED=1
run_test "Joe Smith <email@example.com>" 1 "Name and brackets" || FAILED=1
run_test "email.example.com" 1 "No @" || FAILED=1
run_test "email@example@example.com" 1 "Two @" || FAILED=1
run_test ".email@example.com" 1 "Leading dot in local part" || FAILED=1
run_test "email.@example.com" 1 "Trailing dot in local part" || FAILED=1
run_test "email..email@example.com" 1 "Consecutive dots in local part" || FAILED=1
run_test "email@example.com (Joe Smith)" 1 "Comment" || FAILED=1
run_test "email@example" 1 "Missing TLD" || FAILED=1
run_test "email@-example.com" 1 "Leading hyphen in domain" || FAILED=1
run_test "email@example.web" 0 "Valid TLD" || FAILED=1 # This is valid actually
run_test "email@111.222.333.44444" 1 "Invalid IP format" || FAILED=1
run_test "email@example..com" 1 "Consecutive dots in domain" || FAILED=1
run_test "Abc..123@example.com" 1 "Double dot local" || FAILED=1

if [[ $FAILED -eq 0 ]]; then
    echo "${GREEN}ALL TESTS PASSED${NC}"
    exit 0
else
    echo "${RED}SOME TESTS FAILED${NC}"
    exit 1
fi

#!/usr/bin/env zsh
# Test for TOML configuration loading

set -e

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
source "$LIB_DIR/utils.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/testing.sh"

start_test_suite "TOML Configuration"

# Create a temporary TOML file
TEST_TOML=$(mktemp)
echo 'test_key = "test_value"' > "$TEST_TOML"
echo 'number_key = 123' >> "$TEST_TOML"
echo 'quoted_key = "quoted"' >> "$TEST_TOML"
# echo '[section]' >> "$TEST_TOML" # Sections are currently skipped
# echo 'section_key = "ignored"' >> "$TEST_TOML"

# Load the config
load_toml_config "$TEST_TOML"

# Verify values
val1=$(config_get "test_key")
assert_equals "test_value" "$val1" "Simple string value loaded"

val2=$(config_get "number_key")
assert_equals "123" "$val2" "Number value loaded"

val3=$(config_get "quoted_key")
assert_equals "quoted" "$val3" "Quoted string value loaded"

# Cleanup
rm "$TEST_TOML"

finish_test_suite

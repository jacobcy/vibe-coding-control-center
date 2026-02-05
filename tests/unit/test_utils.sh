#!/bin/bash
# test_utils.sh
# Test script for the enhanced utils.sh

# Source the enhanced utils
SCRIPT_DIR=$(dirname "$0")
source "$SCRIPT_DIR/../../lib/utils.sh"

# Test basic logging
log_step "Testing basic logging functions"
log_info "This is an info message"
log_warn "This is a warning message"
log_error "This is an error message"
log_success "This is a success message"
log_critical "This is a critical message"

# Test input validation
log_step "Testing input validation"
if validate_input "normal_input" "false"; then
    log_info "✓ Valid input accepted"
else
    log_error "✗ Valid input rejected"
fi

if ! validate_input "" "false"; then
    log_info "✓ Empty input correctly rejected"
else
    log_error "✗ Empty input incorrectly accepted"
fi

if validate_input "" "true"; then
    log_info "✓ Empty input accepted when allowed"
else
    log_error "✗ Empty input rejected when allowed"
fi

# Test path validation
log_step "Testing path validation"
if validate_path "/tmp/test" "Path test"; then
    log_info "✓ Valid path accepted"
else
    log_error "✗ Valid path rejected"
fi

if ! validate_path "../../../../etc/passwd" "Path traversal test"; then
    log_info "✓ Path traversal attack blocked"
else
    log_error "✗ Path traversal attack allowed"
fi

# Test filename validation
log_step "Testing filename validation"
if validate_filename "valid_filename.txt" "Filename test"; then
    log_info "✓ Valid filename accepted"
else
    log_error "✗ Valid filename rejected"
fi

if ! validate_filename "../invalid_file.txt" "Filename traversal test"; then
    log_info "✓ Filename with path traversal blocked"
else
    log_error "✗ Filename with path traversal allowed"
fi

# Test secure file operations
log_step "Testing secure file operations"
TEST_FILE="/tmp/test_secure_file.txt"
TEST_CONTENT="This is test content for secure file operations."

if secure_write_file "$TEST_FILE" "$TEST_CONTENT" "600"; then
    log_info "✓ Secure file write successful"
else
    log_error "✗ Secure file write failed"
fi

if secure_append_file "$TEST_FILE" "\nAdditional content" 2>/dev/null; then
    log_info "✓ Secure file append successful"
else
    log_error "✗ Secure file append failed"
fi

# Clean up
rm -f "$TEST_FILE"

# Test user prompts
log_step "Testing user prompts (will skip automatically in non-interactive mode)"
# Skip actual prompts in automated test

log_success "All tests completed!"
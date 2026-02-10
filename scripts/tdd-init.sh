#!/usr/bin/env zsh
# tdd-init.sh
# Standardized TDD Cycle Initializer

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

FEATURE_NAME="$1"

if [[ -z "$FEATURE_NAME" ]]; then
    log_error "Usage: tdd-init.sh <feature-name>"
    exit 1
fi

log_step "Initializing TDD Cycle for: $FEATURE_NAME"

# 1. Create Test File
TEST_FILE="tests/test_${FEATURE_NAME}.sh"
if [[ -f "$TEST_FILE" ]]; then
    log_warn "Test file already exists: $TEST_FILE"
else
    mkdir -p tests
    cat > "$TEST_FILE" << EOF
#!/usr/bin/env zsh
# $TEST_FILE
# TDD Test for $FEATURE_NAME

source "lib/utils.sh"
source "lib/config.sh"

log_step "Running tests for $FEATURE_NAME..."

# TODO: Implement test cases
# Example:
# if some_command; then
#     log_success "PASS"
# else
#     log_error "FAIL"
#     exit 1
# fi

log_error "Test not implemented yet! (Standard TDD Red Phase)"
exit 1
EOF
    chmod +x "$TEST_FILE"
    log_success "Created test template: $TEST_FILE"
fi

# 2. Recommendation
log_info "Next Steps:"
echo "1. Edit $TEST_FILE to define expected behavior."
echo "2. Run it: ./$TEST_FILE (It should FAIL)."
echo "3. Implement logic until it passes."
echo "----------------------------------------"

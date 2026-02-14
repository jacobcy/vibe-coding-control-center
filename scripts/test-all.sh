#!/usr/bin/env zsh
# scripts/test-all.sh
# Run all tests for the Vibe Coding Control Center

set -e

# Get project root directory
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source utility functions
source "$PROJECT_ROOT/lib/utils.sh"

log_step "Starting all tests..."

# Function to run shellcheck on all scripts
run_shellcheck() {
    log_info "Running shellcheck on all scripts..."
    if command -v shellcheck >/dev/null 2>&1; then
        find "$PROJECT_ROOT" -name "*.sh" -not -path "*/node_modules/*" -exec shellcheck {} \;
        log_success "Shellcheck passed"
    else
        log_warn "shellcheck not found, skipping"
    fi
}

# Function to run syntax check on all scripts
run_syntax_check() {
    log_info "Running syntax check on all scripts..."
    local errors_found=0

    while IFS= read -r -d '' file; do
        if ! zsh -n "$file" 2>/dev/null; then
            log_error "Syntax error in: $file"
            zsh -n "$file"  # Show actual error
            errors_found=1
        fi
    done < <(find "$PROJECT_ROOT" -name "*.sh" -not -path "*/node_modules/*" -print0)

    if [[ $errors_found -eq 0 ]]; then
        log_success "Syntax check passed"
    else
        log_error "Syntax check failed"
        return 1
    fi
}

# Function to run unit tests (if any exist)
run_unit_tests() {
    log_info "Running unit tests..."
    local test_dir="$PROJECT_ROOT/tests"

    if [[ -d "$test_dir" ]]; then
        for test_script in "$test_dir"/test_*.sh; do
            if [[ -f "$test_script" && -r "$test_script" && -x "$test_script" ]]; then
                log_info "Running $test_script..."
                if "$test_script"; then
                    log_success "Test $test_script passed"
                else
                    log_error "Test $test_script failed"
                    return 1
                fi
            fi
        done
    else
        log_info "No test directory found, skipping unit tests"
    fi
}

# Function to run integration tests
run_integration_tests() {
    log_info "Running integration tests..."
    local integration_test_dir="$PROJECT_ROOT/tests"

    # Specifically run the integration test that exists
    if [[ -f "$integration_test_dir/test_integration_config_strict.sh" ]]; then
        log_info "Running config integration test..."
        if "$integration_test_dir/test_integration_config_strict.sh"; then
            log_success "Integration test passed"
        else
            log_error "Integration test failed"
            return 1
        fi
    else
        log_warn "No integration tests found"
    fi
}

# Function to run configuration validation
run_config_validation() {
    log_info "Running configuration validation..."

    # Test that the config loader script can be sourced without errors
    if zsh -c "source '$PROJECT_ROOT/lib/config_loader.sh'; echo 'Config loader sourced successfully'"; then
        log_success "Config loader validation passed"
    else
        log_error "Config loader validation failed"
        return 1
    fi

    # Test that the utils script can be sourced without errors
    if zsh -c "source '$PROJECT_ROOT/lib/utils.sh'; echo 'Utils sourced successfully'"; then
        log_success "Utils validation passed"
    else
        log_error "Utils validation failed"
        return 1
    fi
}

# Main execution
main() {
    local start_time
    start_time=$(date +%s)

    log_info "Starting comprehensive test suite..."

    # Run all test functions
    run_shellcheck
    run_syntax_check
    run_config_validation
    run_unit_tests
    run_integration_tests

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_success "All tests completed successfully in ${duration}s!"
    return 0
}

# Handle command line arguments
case "${1:-}" in
    --syntax)
        run_syntax_check
        ;;
    --shellcheck)
        run_shellcheck
        ;;
    --unit)
        run_unit_tests
        ;;
    --integration)
        run_integration_tests
        ;;
    --config)
        run_config_validation
        ;;
    *)
        main
        ;;
esac

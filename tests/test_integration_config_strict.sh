#!/usr/bin/env zsh
# tests/test_integration_config_strict.sh
# Integration test to verify configuration loading robustness under strict mode (set -e)

# Ensure we are running from the project root
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source utility functions for logging
source "$PROJECT_ROOT/lib/utils.sh"

# Define the test function
run_integration_test() {
    log_step "Starting integration test: Configuration loading with strict mode"

    # Create a temporary test directory
    local test_dir
    test_dir=$(mktemp -d)
    local test_home="$test_dir/home"
    mkdir -p "$test_home/.vibe"
    
    # 1. Create a bad configuration file (unreadable)
    local bad_config="$test_home/.vibe/keys.env"
    echo "KEY=VALUE" > "$bad_config"
    chmod 000 "$bad_config"
    
    # 2. Create a test script that uses the library with set -e
    local test_script="$test_dir/test_script.sh"
    cat > "$test_script" <<EOF
#!/usr/bin/env zsh
set -e

# Mock HOME to point to our test directory
export HOME="$test_home"

# Source the config loader
source "$PROJECT_ROOT/lib/config_loader.sh"

echo "Attempting to load configuration..."
# This call should NOT crash the script despite the bad config
load_configuration

echo "SUCCESS: Script continued execution"
EOF
    
    chmod +x "$test_script"
    
    # 3. Run the test script
    log_step "Running test script..."
    local output
    if output=$("$test_script" 2>&1); then
        # Check if the success message is present
        if [[ "$output" == *"SUCCESS: Script continued execution"* ]]; then
            log_success "Integration test PASSED: System handled bad config gracefully under set -e"
            log_info "Output log:"
            echo "$output" | sed 's/^/  /'
        else
            log_error "Integration test FAILED: Script exited with 0 but did not reach end"
            log_info "Output log:"
            echo "$output" | sed 's/^/  /'
            return 1
        fi
    else
        log_error "Integration test FAILED: Script crashed (exit code $?)"
        log_info "Output log:"
        echo "$output" | sed 's/^/  /'
        return 1
    fi
    
    # Cleanup
    chmod 700 "$bad_config" # Restore permissions to allow deletion
    rm -rf "$test_dir"
    
    return 0
}

# Run the test
run_integration_test

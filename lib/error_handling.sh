#!/bin/bash
# Enhanced Error Handling and Retry Mechanism for Vibe Coding Control Center

# Error code definitions
declare -A ERROR_CODES=(
    ["CONFIG_ERROR"]="Configuration error (E001)"
    ["PERMISSION_DENIED"]="Permission denied (E002)"
    ["NETWORK_ERROR"]="Network error (E003)"
    ["VALIDATION_FAILED"]="Validation failed (E004)"
    ["FILE_NOT_FOUND"]="File not found (E005)"
    ["COMMAND_FAILED"]="Command failed (E006)"
)

# Global error tracking
LAST_ERROR_CODE=""
LAST_ERROR_MESSAGE=""

# Set up error trap
setup_error_handling() {
    trap 'handle_error' ERR
}

# Enhanced error handler
handle_error() {
    local exit_code=$?
    local line_no=${BASH_LINENO[0]:-unknown}
    local func_name=${FUNCNAME[1]:-unknown}

    log_error "Error in function '$func_name' at line $line_no (exit code: $exit_code)"

    # Log stack trace if debugging is enabled
    if [[ "${DEBUG:-false}" == "true" ]]; then
        log_debug "Stack trace:"
        for i in "${!BASH_SOURCE[@]}"; do
            log_debug "  ${BASH_SOURCE[$i]}:${BASH_LINENO[$i-1]:-0} ${FUNCNAME[$i]}"
        done
    fi

    # Store error information
    LAST_ERROR_CODE="$exit_code"
    LAST_ERROR_MESSAGE="Error in $func_name at line $exit_code"

    exit $exit_code
}

# Retry operation with exponential backoff
retry_operation() {
    local operation="$1"
    local max_attempts="${2:-3}"
    local base_delay="${3:-1}"  # Base delay in seconds
    local attempt=1

    # Validate inputs
    if ! validate_input "$operation" "false"; then
        log_error "Invalid operation for retry: $operation"
        return 1
    fi

    if ! [[ "$max_attempts" =~ ^[0-9]+$ ]] || [[ "$max_attempts" -lt 1 ]]; then
        log_error "Invalid max_attempts value: $max_attempts"
        return 1
    fi

    if ! [[ "$base_delay" =~ ^[0-9]+\.?[0-9]*$ ]] || (( $(echo "$base_delay <= 0" | bc -l 2>/dev/null || echo 1) )); then
        log_error "Invalid base_delay value: $base_delay"
        return 1
    fi

    while [[ $attempt -le $max_attempts ]]; do
        log_debug "Attempt $attempt of $max_attempts for operation: $operation"

        if eval "$operation"; then
            log_debug "Operation succeeded on attempt $attempt"
            return 0
        else
            local exit_code=$?
            log_warn "Attempt $attempt failed with exit code $exit_code, retrying in $((base_delay * attempt)) seconds..."

            # Calculate delay with exponential backoff
            local delay=$(echo "$base_delay * $attempt" | bc 2>/dev/null)
            if [[ $? -ne 0 ]]; then
                # Fallback if bc is not available
                delay=$((base_delay * attempt))
            fi

            sleep "$delay"
            ((attempt++))
        fi
    done

    log_error "Operation failed after $max_attempts attempts: $operation"
    return 1
}

# Circuit breaker pattern implementation
declare -A CB_STATES  # States: closed, open, half_open
declare -A CB_FAILURE_COUNT
declare -A CB_LAST_FAILURE_TIME
CB_THRESHOLD=5
CB_TIMEOUT=60  # Reset timeout in seconds

circuit_breaker_call() {
    local operation="$1"
    local cb_name="${2:-default_circuit_breaker}"

    # Check circuit state
    local current_state="${CB_STATES[$cb_name]:-closed}"
    local current_time=$(date +%s)

    case "$current_state" in
        "open")
            # Check if timeout has passed
            local last_failure="${CB_LAST_FAILURE_TIME[$cb_name]:-$current_time}"
            if (( current_time - last_failure > CB_TIMEOUT )); then
                # Transition to half-open state
                CB_STATES["$cb_name"]="half_open"
                log_debug "Circuit breaker $cb_name transitioning to half-open state"
            else
                log_warn "Circuit breaker $cb_name is OPEN, blocking call"
                return 5  # Circuit breaker open
            fi
            ;;
        "half_open")
            # Allow one call to test recovery
            ;;
        *)
            # Circuit is closed, allow call
            ;;
    esac

    if eval "$operation"; then
        # Success: reset failure count and close circuit
        CB_FAILURE_COUNT["$cb_name"]=0
        CB_STATES["$cb_name"]="closed"
        return 0
    else
        # Failure: increment failure count
        local failure_count="${CB_FAILURE_COUNT[$cb_name]:-0}"
        ((failure_count++))
        CB_FAILURE_COUNT["$cb_name"]=$failure_count
        CB_LAST_FAILURE_TIME["$cb_name"]=$current_time

        # Open circuit if threshold exceeded
        if (( failure_count >= CB_THRESHOLD )); then
            CB_STATES["$cb_name"]="open"
            log_warn "Circuit breaker $cb_name TRIPPED (threshold exceeded: $failure_count)"
        else
            log_debug "Circuit breaker $cb_name failure count: $failure_count/$CB_THRESHOLD"
        fi

        return 1
    fi
}

# Safe command execution with timeout
safe_execute_with_timeout() {
    local command="$1"
    local timeout_duration="${2:-30}"  # Default 30 seconds

    # Validate inputs
    if ! validate_input "$command" "false"; then
        log_error "Invalid command for timeout execution: $command"
        return 1
    fi

    if ! [[ "$timeout_duration" =~ ^[0-9]+$ ]] || [[ "$timeout_duration" -lt 1 ]]; then
        log_error "Invalid timeout duration: $timeout_duration"
        return 1
    fi

    # Execute with timeout
    if command timeout "$timeout_duration" bash -c "$command"; then
        return 0
    else
        local exit_code=$?
        case $exit_code in
            124) log_error "Command timed out after $timeout_duration seconds" ;;
            *) log_error "Command failed with exit code: $exit_code" ;;
        esac
        return $exit_code
    fi
}

# Initialize error handling system
setup_error_handling
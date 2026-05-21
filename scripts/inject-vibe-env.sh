#!/usr/bin/env zsh
# Inject environment variables into a running tmux session
#
# Modes:
#   1. Default mode: Inject specific VIBE_* variables from ~/.zshrc
#      (see DEFAULT_VIBE_VARS for the exact list)
#   2. Command mode: Inject only variables specified as KEY=VALUE arguments
#
# Usage:
#   ./inject-vibe-env.sh <session-name>
#   ./inject-vibe-env.sh <session-name> KEY=VALUE [KEY=VALUE ...]
#
# Examples:
#   # Inject default VIBE vars
#   ./inject-vibe-env.sh vibe3-orchestra-serve
#
#   # Inject only specific variables (ignores ~/.zshrc)
#   ./inject-vibe-env.sh vibe3-orchestra-serve \
#       VIBE_BACKEND_SUPERVISOR=gemini
#
#   # Inject multiple variables
#   ./inject-vibe-env.sh vibe3-orchestra-serve DEBUG=true VIBE_BACKEND=gemini

# Show help if no arguments
if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <session-name> [KEY=VALUE ...]"
    echo ""
    echo "Inject environment variables into a running tmux session."
    echo ""
    echo "Modes:"
    echo "  1. Default: No KEY=VALUE args → inject default VIBE vars from ~/.zshrc"
    echo "  2. Command: With KEY=VALUE args → inject only specified variables"
    echo ""
    echo "Default VIBE vars injected in default mode:"
    echo "  VIBE_BACKEND_SUPERVISOR, VIBE_MODEL_SUPERVISOR"
    echo "  VIBE_BACKEND_GOVERNANCE, VIBE_MODEL_GOVERNANCE"
    echo "  VIBE_DEFAULT_BACKEND, VIBE_DEFAULT_MODEL"
    echo ""
    echo "Examples:"
    echo "  # Default mode: inject default VIBE vars from ~/.zshrc"
    echo "  $0 vibe3-orchestra-serve"
    echo ""
    echo "  # Command mode: inject only specified variables"
    echo "  $0 vibe3-orchestra-serve VIBE_BACKEND_SUPERVISOR=gemini"
    echo ""
    echo "  # Multiple variables (any variable name allowed)"
    echo "  $0 vibe3-orchestra-serve DEBUG=true VIBE_MODEL=gpt-4 FOO=bar"
    echo ""
    echo "Available sessions:"
    tmux list-sessions 2>/dev/null || echo "  (no tmux sessions)"
    exit 0
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_success() { echo "${GREEN}✓${NC} $1"; }
echo_info() { echo "${YELLOW}→${NC} $1"; }
echo_error() { echo "${RED}✗${NC} $1"; }

# Default VIBE variables to inject (from ~/.zshrc)
DEFAULT_VIBE_VARS=(
    VIBE_BACKEND_SUPERVISOR
    VIBE_MODEL_SUPERVISOR
    VIBE_BACKEND_GOVERNANCE
    VIBE_MODEL_GOVERNANCE
    VIBE_DEFAULT_BACKEND
    VIBE_DEFAULT_MODEL
)

# Parse arguments
session_name="$1"
shift || {
    echo_error "Missing session-name argument"
    echo_info "Run without arguments for usage examples."
    exit 1
}

# Check for KEY=VALUE arguments
typeset -A cmd_vars
has_cmd_vars=false

for arg in "$@"; do
    if [[ "$arg" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
        var_name="${match[1]}"
        var_value="${match[2]}"
        cmd_vars[$var_name]="$var_value"
        has_cmd_vars=true
    else
        echo_error "Invalid argument: $arg"
        echo_info "Expected format: KEY=VALUE (e.g., VIBE_BACKEND=gemini)"
        exit 1
    fi
done

# Check if tmux session exists
if ! tmux has-session -t "$session_name" 2>/dev/null; then
    echo_error "Tmux session '$session_name' does not exist"
    echo_info "Available sessions:"
    tmux list-sessions 2>/dev/null || echo "  (no sessions)"
    exit 1
fi

# Extract variable from ~/.zshrc using safe evaluation
extract_var_from_zshrc() {
    local var_name="$1"
    local value

    # Try to get from current environment first
    if [[ -n "${(P)var_name}" ]]; then
        echo "${(P)var_name}"
        return
    fi

    # Fallback: safely evaluate in a clean zsh process
    # This properly handles quotes, variable expansion, and inline comments
    value=$(zsh -c "source ~/.zshrc 2>/dev/null && echo \"\${(P)var_name}\"" 2>/dev/null)
    echo "$value"
}

# Determine mode and collect variables to inject
typeset -A vars_to_inject

if [[ "$has_cmd_vars" == "true" ]]; then
    # Command mode: use only command-line variables
    echo_info "Mode: Command (injecting specified variables)"
    vars_to_inject=("${(@kv)cmd_vars}")
else
    # Default mode: read from ~/.zshrc
    echo_info "Mode: Default (reading VIBE_* vars from ~/.zshrc)"
    for var in "${DEFAULT_VIBE_VARS[@]}"; do
        value=$(extract_var_from_zshrc "$var")
        if [[ -n "$value" ]]; then
            vars_to_inject[$var]="$value"
        fi
    done
fi

# Inject variables
if [[ ${#vars_to_inject[@]} -eq 0 ]]; then
    echo_info "No variables to inject."
    exit 0
fi

echo_info "Injecting into session: $session_name"
echo ""

injected_count=0

for var value in "${(@kv)vars_to_inject}"; do
    # Method 1: Set session-level environment (for new windows/panes)
    if ! tmux set-environment -t "$session_name" "$var" "$value" 2>&1; then
        echo_error "  Failed to set $var in session environment"
        continue
    fi

    # Method 2: Also export in all existing panes (for immediate effect)
    # Only inject into panes that appear to be at a shell prompt
    panes=$(tmux list-panes -t "$session_name" -F "#{pane_id} #{pane_current_command}" 2>/dev/null || true)
    for pane_info in $=panes; do
        pane_id="${pane_info%% *}"
        pane_cmd="${pane_info#* }"

        # Skip panes running interactive programs (vim, less, etc.)
        # Only inject into shells (zsh, bash, sh)
        if [[ "$pane_cmd" =~ ^(zsh|bash|sh)$ ]]; then
            # Safely escape the value for shell injection
            escaped_value=$(printf '%q' "$value")
            if ! tmux send-keys -t "$pane_id" "export $var=$escaped_value" C-m 2>&1; then
                echo_error "    Failed to inject into pane $pane_id"
            fi
        fi
    done

    echo_success "  $var=$value"
    injected_count=$((injected_count + 1))
done

echo ""
echo_info "Summary: $injected_count variable(s) injected"
echo ""
echo_success "Done! Session '$session_name' updated."
echo_info "Note: New panes will inherit these variables automatically."
echo_info "Existing panes have been updated via 'export' commands."

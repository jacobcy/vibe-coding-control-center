#!/usr/bin/env zsh
# Vibe 3.0 Shell Wrapper (Hub)
# All logic should eventually be handled by Python core in scripts/python/

set -e

# --- Context ---
VIBE3_LIB_DIR="$(cd "$(dirname "${(%):-%x:A}")" && pwd)"
VIBE3_ROOT="$(cd "$VIBE3_LIB_DIR/.." && pwd)"
VIBE3_PYTHON_CORE="$VIBE3_ROOT/scripts/python/vibe3/cli.py"

# --- Colors ---
if [ -t 1 ]; then
    BOLD='\033[1m'
    CYAN='\033[0;36m'
    GREEN='\033[0;32m'
    NC='\033[0m' # No Color
else
    BOLD=''
    CYAN=''
    GREEN=''
    NC=''
fi

vibe3_help() {
    echo "${BOLD}Vibe 3.0 (Preview Rebuild)${NC}"
    echo ""
    echo "Usage: ${CYAN}vibe3 <command>${NC} [args]"
    echo ""
    echo "Commands:"
    echo "  ${GREEN}flow${NC}     Manage logic flows (branch-centric)"
    echo "  ${GREEN}task${NC}     Manage execution tasks"
    echo "  ${GREEN}pr${NC}       Manage Pull Requests"
    echo "  ${GREEN}version${NC}  Show version"
    echo ""
    echo "Global Flags:"
    echo "  ${GREEN}--json${NC}   Output in JSON format"
    echo "  ${GREEN}-y${NC}       Auto-confirm prompts (non-interactive)"
    echo ""
    echo "💡 This is a parallel implementation. Your existing vibe (2.x) is untouched."
}

vibe3_version() {
    echo "3.0.0-dev"
}

# Main command handling
command="${1:-help}"

case "$command" in
    version|--version|-v)
        vibe3_version
        exit 0
        ;;
    help|--help|-h)
        vibe3_help
        exit 0
        ;;
    flow|task|pr|check)
        shift 1 2>/dev/null || true
        # Dispatch to Python core
        if [[ -f "$VIBE3_PYTHON_CORE" ]]; then
            # Run as module from scripts/python directory
            cd "$VIBE3_ROOT/scripts/python"
            python3 -m vibe3.cli "$command" "$@"
            cd "$VIBE3_ROOT"
        else
            echo "Error: Python core not found at $VIBE3_PYTHON_CORE"
            exit 1
        fi
        ;;
    *)
        if [[ "$command" == -* ]]; then
             # Handle global flags without domain
             vibe3_help
             exit 0
        fi
        echo "Unknown command: $command"
        vibe3_help
        exit 1
        ;;
esac

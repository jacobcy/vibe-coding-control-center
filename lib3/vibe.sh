#!/usr/bin/env zsh
# Vibe 3.0 Shell Wrapper (Hub)
# All logic should eventually be handled by Python core in src/

set -e

# --- Context ---
VIBE3_LIB_DIR="$(cd "$(dirname "${(%):-%x:A}")" && pwd)"
VIBE3_ROOT="$(cd "$VIBE3_LIB_DIR/.." && pwd)"

# Smart redirect: if running from global install and inside a git repo, prefer repo version
VIBE3_REAL_ROOT="$(cd "$VIBE3_ROOT" && pwd -P 2>/dev/null || echo "$VIBE3_ROOT")"
VIBE3_REAL_HOME="$(cd "$HOME/.vibe" 2>/dev/null && pwd -P || echo "$HOME/.vibe")"

if [[ "$VIBE3_REAL_ROOT" == "$VIBE3_REAL_HOME" ]] && command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    REPO_VIBE3="${REPO_ROOT}/lib3/vibe.sh"
    if [[ -n "$REPO_ROOT" && -f "$REPO_VIBE3" && "$REPO_VIBE3" != "${VIBE3_LIB_DIR}/vibe.sh" ]]; then
        exec zsh "$REPO_VIBE3" "$@"
    fi
fi

VIBE3_PYTHON_CORE="$VIBE3_ROOT/src/vibe3/cli.py"

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
    echo "  ${GREEN}inspect${NC}  Code analysis and metrics"
    echo "  ${GREEN}review${NC}   Code review workflow"
    echo "  ${GREEN}hooks${NC}    Manage Git hooks"
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
    flow|task|pr|check|inspect|review|hooks|roadmap)
        shift 1 2>/dev/null || true
        # Dispatch to Python core
        if [[ -f "$VIBE3_PYTHON_CORE" ]]; then
            # Run with uv to ensure dependencies
            cd "$VIBE3_ROOT"
            uv run python src/vibe3/cli.py "$command" "$@"
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

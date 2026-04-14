#!/usr/bin/env zsh
# Vibe 3.0 Shell Wrapper (Hub)
# Keep this wrapper thin: repo redirect + dispatch to Python core.

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
[[ -f "$VIBE3_PYTHON_CORE" ]] || {
    echo "Error: Python core not found at $VIBE3_PYTHON_CORE"
    exit 1
}

cd "$VIBE3_ROOT"
export VIBE3_PROG_NAME="vibe3"

if [[ "${1:-}" == "--version" || "${1:-}" == "-v" ]]; then
    shift 1 2>/dev/null || true
    exec uv run python src/vibe3/cli.py version "$@"
fi

exec uv run python src/vibe3/cli.py "$@"

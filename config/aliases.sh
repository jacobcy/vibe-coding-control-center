#!/usr/bin/env zsh
# ======================================================
# Vibe Coding Aliases (Level 2) - 主入口文件
# ======================================================
# Philosophy:
#   - Agents do the work unattended (auto-approve)
#   - You only review/commit (lazygit)
#   - Main branch is protected (guard)
# ======================================================

# ---------- 环境变量初始化 ----------
# Resolve VIBE_ROOT using the shared library logic
# Note: 不使用 local，因为 zsh 不允许在脚本顶层使用 local
_aliases_dir="$(dirname "${(%):-%x:A}")"
_aliases_real=""
_lib_config=""

# Resolve symlinks: if _aliases_dir ends in config, parent is the install root
if [[ -L "${(%):-%x}" ]]; then
    _aliases_real="$(readlink -f "${(%):-%x}" 2>/dev/null || readlink "${(%):-%x}")"
    _aliases_dir="$(dirname "$_aliases_real")"
fi
_lib_config="$_aliases_dir/../lib/config.sh"

if [[ -f "$_lib_config" ]]; then
    source "$_lib_config"
else
    VIBE_ROOT="$(cd "$_aliases_dir/.." && pwd)"
    VIBE_HOME="$VIBE_ROOT/.vibe"
fi

# Detect actual repository root from Git when inside a worktree
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    VIBE_REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
else
    VIBE_REPO="$(dirname "$VIBE_ROOT")"
fi
# Determine VIBE_MAIN - could be the repo root itself or a 'main' subdirectory
if [[ -d "$VIBE_REPO/main" && (-d "$VIBE_REPO/main/.git" || -f "$VIBE_REPO/main/.git") ]]; then
    VIBE_MAIN="$VIBE_REPO/main"
else
    VIBE_MAIN="$VIBE_REPO"
fi
VIBE_SESSION="${VIBE_SESSION:-vibe}"

# ---------- 工具函数 ----------
# Check if a command exists (enhanced with common path fallback)
vibe_has() {
    local cmd="$1"
    if command -v "$cmd" >/dev/null 2>&1; then
        return 0
    fi
    # Try common locations for specific commands
    case "$cmd" in
        git)
            for path in /opt/homebrew/bin/git /usr/local/bin/git /usr/bin/git; do
                [[ -x "$path" ]] && return 0
            done
            ;;
        tmux)
            for path in /opt/homebrew/bin/tmux /usr/local/bin/tmux /usr/bin/tmux; do
                [[ -x "$path" ]] && return 0
            done
            ;;
        *)
            [[ -x "/usr/bin/$cmd" || -x "/bin/$cmd" ]] && return 0
            ;;
    esac
    return 1
}

vibe_die() { echo "❌ $*" >&2; return 1; }

vibe_require() {
  local miss=()
  for c in "$@"; do vibe_has "$c" || miss+=("$c"); done
  ((${#miss[@]}==0)) || vibe_die "Missing commands: ${miss[*]}"
}

vibe_now() { date +"%Y-%m-%d %H:%M:%S"; }

# Find a command in PATH or common locations
vibe_find_cmd() {
    local cmd="$1"
    if command -v "$cmd" >/dev/null 2>&1; then
        command -v "$cmd"
        return 0
    fi
    if [[ "$cmd" == "git" ]]; then
        for path in /opt/homebrew/bin/git /usr/local/bin/git /usr/bin/git; do
            if [[ -x "$path" ]]; then
                echo "$path"
                return 0
            fi
        done
    fi
    return 1
}

# Helper to load local keys.env if present in PWD or Git root
vibe_load_context() {
    if typeset -f load_configuration >/dev/null 2>&1; then
        load_configuration
    else
        local config_loader=""
        if [[ -f "$_aliases_dir/lib/config_loader.sh" ]]; then
            config_loader="$_aliases_dir/lib/config_loader.sh"
        elif [[ -f "$_aliases_dir/../lib/config_loader.sh" ]]; then
            config_loader="$_aliases_dir/../lib/config_loader.sh"
        fi
        if [[ -n "$config_loader" ]]; then
            source "$config_loader"
            load_configuration
        fi
    fi
}

# ---------- 加载分类 Aliases ----------
# Source all category files if they exist
_aliases_src_dir="$_aliases_dir/aliases"

# Load git helper functions (required by worktree.sh)
[[ -f "$_aliases_src_dir/git.sh" ]] && source "$_aliases_src_dir/git.sh"

# Load tmux functions (required by worktree.sh)
[[ -f "$_aliases_src_dir/tmux.sh" ]] && source "$_aliases_src_dir/tmux.sh"

# Load worktree commands
[[ -f "$_aliases_src_dir/worktree.sh" ]] && source "$_aliases_src_dir/worktree.sh"

# Load other categories
[[ -f "$_aliases_src_dir/claude.sh" ]] && source "$_aliases_src_dir/claude.sh"
[[ -f "$_aliases_src_dir/opencode.sh" ]] && source "$_aliases_src_dir/opencode.sh"
[[ -f "$_aliases_src_dir/openspec.sh" ]] && source "$_aliases_src_dir/openspec.sh"
[[ -f "$_aliases_src_dir/vibe.sh" ]] && source "$_aliases_src_dir/vibe.sh"

# Clean up
unset _aliases_dir
unset _aliases_real
unset _aliases_src_dir
unset _lib_config

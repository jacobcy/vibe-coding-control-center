#!/usr/bin/env zsh
# Vibe Center - Global Update Command
# Idempotent sync from repo to ~/.vibe with cleanup

set -euo pipefail

# Load config and utils
source "${0:A:h}/config.sh"

vibe_update() {
    local command="${1:-help}"
    shift 2>/dev/null || true

    case "$command" in
        help|--help|-h)
            _usage
            ;;
        run)
            _update_run "$@"
            ;;
        *)
            log_error "Unknown update subcommand: $command"
            _usage
            exit 1
            ;;
    esac
}

_usage() {
    echo "${BOLD}vibe update${NC} - Global distribution sync"
    echo ""
    echo "Usage: ${CYAN}vibe update run${NC} [options]"
    echo ""
    echo "Synchronizes Vibe distribution from current repo to ${CYAN}~/.vibe${NC}:"
    echo "  • Syncs: bin, lib, lib3, config, scripts, src, skills, supervisor"
    echo "  • Cleans: stale files not in source"
    echo "  • Preserves: config/keys.env, settings.yaml"
    echo "  • Idempotent: safe to run multiple times"
    echo ""
    echo "Options:"
    echo "  -n, --dry-run    Show what would be updated without making changes"
    echo "  -v, --verbose    Show detailed sync operations"
    echo "  -h, --help       Show this help message"
    echo ""
    echo "Effect semantics:"
    echo "  • Repo-local V2/V3 changes → immediate effect in current worktree"
    echo "  • Global changes → run ${CYAN}vibe update${NC}"
    echo "  • Loader/alias changes → ${CYAN}source ~/.zshrc${NC} or restart shell"
    exit 0
}

_update_run() {
    local dry_run=false
    local verbose=false

    for arg in "$@"; do
        case "$arg" in
            -n|--dry-run) dry_run=true ;;
            -v|--verbose) verbose=true ;;
            -h|--help) _usage ;;
        esac
    done

    log_step "Global update starting..."

    local INSTALL_DIR="$HOME/.vibe"
    local SOURCE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
    local CURRENT_REPO_ROOT=""
    local REAL_SOURCE_ROOT="$(cd "$SOURCE_ROOT" && pwd -P 2>/dev/null || echo "$SOURCE_ROOT")"
    local REAL_INSTALL_DIR="$INSTALL_DIR"

    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        CURRENT_REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
        if [[ -n "$CURRENT_REPO_ROOT" && -f "$CURRENT_REPO_ROOT/lib/utils.sh" && -f "$CURRENT_REPO_ROOT/bin/vibe" ]]; then
            SOURCE_ROOT="$CURRENT_REPO_ROOT"
            REAL_SOURCE_ROOT="$(cd "$SOURCE_ROOT" && pwd -P 2>/dev/null || echo "$SOURCE_ROOT")"
        fi
    fi

    if [[ -d "$INSTALL_DIR" ]]; then
        REAL_INSTALL_DIR="$(cd "$INSTALL_DIR" && pwd -P 2>/dev/null || echo "$INSTALL_DIR")"
    fi

    log_info "Source: $SOURCE_ROOT"
    log_info "Target: $INSTALL_DIR"

    # Pre-flight checks
    log_step "Running pre-flight checks..."

    # Check we're in a Vibe repo
    if [[ ! -f "$SOURCE_ROOT/lib/utils.sh" ]]; then
        log_error "Not in a Vibe Center repository: $SOURCE_ROOT"
        log_error "Please run 'vibe update' from a Vibe repo or worktree"
        exit 1
    fi

    # Check target directory exists (should exist if install.sh ran)
    if [[ ! -d "$INSTALL_DIR" ]]; then
        log_error "Global install directory not found: $INSTALL_DIR"
        log_error "Please run 'scripts/install.sh' first"
        exit 1
    fi

    if [[ "$REAL_SOURCE_ROOT" == "$REAL_INSTALL_DIR" ]]; then
        if [[ -n "$CURRENT_REPO_ROOT" ]]; then
            log_error "Current repo is not a Vibe Center repository: $CURRENT_REPO_ROOT"
        else
            log_error "vibe update must run from a Vibe Center repository or worktree"
        fi
        log_error "Open your vibe-center checkout and run 'vibe update run' there"
        exit 1
    fi

    log_success "Pre-flight checks passed"

    # Sync core components
    for dir in bin lib lib3 config scripts src skills supervisor; do
        _sync_component "$SOURCE_ROOT/$dir" "$INSTALL_DIR/$dir" "$dir" || {
            log_error "Failed to sync $dir"
            exit 1
        }
    done

    # Sync Python project files
    for file in pyproject.toml uv.lock; do
        if [[ -f "$SOURCE_ROOT/$file" ]]; then
            if [[ "$dry_run" == "true" ]]; then
                log_info "[DRY-RUN] Would copy: $file"
            else
                cp "$SOURCE_ROOT/$file" "$INSTALL_DIR/"
                [[ "$verbose" == "true" ]] && log_success "Copied: $file"
            fi
        fi
    done

    # Sync Python dependencies
    if [[ -f "$SOURCE_ROOT/pyproject.toml" ]]; then
        if [[ "$dry_run" == "true" ]]; then
            log_info "[DRY-RUN] Would sync Python dependencies: uv sync --all-extras"
        else
            log_info "Syncing Python dependencies..."
            cd "$SOURCE_ROOT"
            if command -v uv >/dev/null 2>&1; then
                uv sync --all-extras
                log_success "Python dependencies synced"
            else
                log_warn "uv not found, skipping dependency sync"
            fi
        fi
    fi

    log_success "Global update complete!"
    echo ""
    echo "${BOLD}What changed:${NC}"
    echo "  • V2/V3 core components synced to ${CYAN}~/.vibe${NC}"
    echo "  • Stale files cleaned up"
    echo "  • User configs preserved (keys.env, settings.yaml)"
    echo ""
    echo "${BOLD}Effect semantics:${NC}"
    echo "  • Shell loader changes → ${CYAN}source ~/.zshrc${NC}"
    echo "  • Python dependencies → synced via ${CYAN}uv sync${NC}"
    echo "  • Python code changes → effective immediately (local src resolution)"
    echo "  • Alias changes → ${CYAN}vibe alias${NC} or restart shell"
    echo ""
    echo "${BOLD}Next steps:${NC}"
    echo "  • Run ${CYAN}vibe doctor${NC} to verify environment"
    echo "  • Run ${CYAN}vibe keys check${NC} to verify API keys"
}

_clean_stale_files() {
    local dst_dir="$1"
    local src_dir="$2"
    local component_name="$3"

    if [[ ! -d "$dst_dir" ]]; then
        return 0
    fi

    if [[ "$dry_run" == "true" ]]; then
        log_info "[DRY-RUN] Would clean stale files in $dst_dir"
        return 0
    fi

    local cleaned=0
    while IFS= read -r -d '' file; do
        local rel_path="${file#$dst_dir/}"
        local src_path="$src_dir/$rel_path"

        # Skip preserved files
        if [[ "$component_name" == "config" && "$rel_path" == "keys.env" ]]; then
            continue
        fi

        if [[ ! -e "$src_path" ]]; then
            if [[ "$verbose" == "true" ]]; then
                log_warn "Removing stale: $rel_path"
            fi
            rm -f "$file"
            cleaned=$((cleaned + 1)) || true
        fi
    done < <(find "$dst_dir" -type f -print0 2>/dev/null)

    if [[ $cleaned -gt 0 ]]; then
        log_info "Cleaned $cleaned stale file(s) in $component_name"
    fi
}

_sync_component() {
    local src_dir="$1"
    local dst_dir="$2"
    local component_name="$3"

    if [[ ! -d "$src_dir" ]]; then
        log_warn "Source directory $src_dir not found, skipping $component_name"
        return 0
    fi

    # Clean stale files first
    _clean_stale_files "$dst_dir" "$src_dir" "$component_name"

    if [[ "$dry_run" == "true" ]]; then
        log_info "[DRY-RUN] Would sync: $src_dir → $dst_dir"
        return 0
    fi

    mkdir -p "$dst_dir"

    # Special handling for config/ to preserve keys.env
    if [[ "$component_name" == "config" ]]; then
        # Sync everything except keys.env
        for item in "$src_dir"/*; do
            local name=$(basename "$item")
            if [[ "$name" == "keys.env" ]]; then
                continue
            fi
            cp -R "$item" "$dst_dir/" 2>/dev/null || {
                log_error "Failed to sync: $component_name/$name"
                return 1
            }
        done
        log_info "Synced: $component_name (preserved keys.env)"
        return 0
    fi

    # Normal sync for other components
    if cp -R "$src_dir/." "$dst_dir/" 2>/dev/null; then
        if [[ "$verbose" == "true" ]]; then
            log_success "Synced: $component_name"
        else
            log_info "Synced: $component_name"
        fi
    else
        log_error "Failed to sync: $component_name"
        return 1
    fi
}

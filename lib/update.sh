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
    echo "  • Syncs: bin, lib, lib3, config, scripts, alias, src, skills"
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

    # TODO: Implement sync logic in next tasks
    log_info "Sync logic will be implemented in Task 3-6"

    log_success "Update complete!"
}

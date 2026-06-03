#!/usr/bin/env zsh
# Shared utilities for install.sh and update.sh
# Sourced by both scripts to avoid duplication

# Migrate stale paths in settings.yaml: assets/* → canonical paths
_migrate_settings_yaml_paths() {
    local settings_file="$1/settings.yaml"
    [[ -f "$settings_file" ]] || return 0

    if grep -q 'assets/prompts' "$settings_file" 2>/dev/null; then
        sed -i.bak 's|assets/prompts|config/prompts|g' "$settings_file"
        rm -f "$settings_file.bak"
        log_info "Migrated prompts_root path in settings.yaml"
    fi
    if grep -q 'assets/policies' "$settings_file" 2>/dev/null; then
        sed -i.bak 's|assets/policies|supervisor/policies|g' "$settings_file"
        rm -f "$settings_file.bak"
        log_info "Migrated policies_root path in settings.yaml"
    fi
}

# Verify critical runtime assets exist after install/update
_check_runtime_assets() {
    local install_dir="$1"
    local check_files=(
        "src/vibe3/environment/runtime_assets.py"
        "config/prompts/prompts.yaml"
        "config/prompts/prompt-recipes.yaml"
        "supervisor/manager.md"
        "supervisor/policies/run.md"
        "supervisor/policies/plan.md"
        "supervisor/policies/review.md"
        "skills/vibe-commit/SKILL.md"
    )
    local missing=0
    for rel in "${check_files[@]}"; do
        if [[ ! -f "$install_dir/$rel" ]]; then
            log_warn "Runtime asset missing: $rel"
            missing=$((missing + 1))
        fi
    done
    if [[ $missing -gt 0 ]]; then
        log_error "Runtime asset sanity check failed: $missing file(s) missing"
        log_error "Run 'vibe update run' to sync, or re-run scripts/install.sh"
        return 1
    fi
    log_success "Runtime asset sanity check passed"
    return 0
}

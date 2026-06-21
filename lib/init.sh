#!/usr/bin/env zsh
# vibe init - Project Initialization
# Initializes project directory structure and configuration

# --- Helper Functions ---
_log_info() { echo "${CYAN}ℹ️  $1${NC}"; }
_log_success() { echo "${GREEN}✅ $1${NC}"; }
_log_warning() { echo "${YELLOW}⚠️  $1${NC}"; }
_log_error() { echo "${RED}❌ $1${NC}" >&2; }

# --- Help Function (sourced from init_help.sh) ---
source "$(cd "$(dirname "${(%):-%x:A}")" && pwd)/init_help.sh"
# --- Template Generation Function ---
_generate_claude_md() {
    local profile_name="$1"
    local repo_root="$2"
    local output_file="$repo_root/CLAUDE.md"

    local template_dir
    template_dir="$(cd "$(dirname "${(%):-%x:A}")" && pwd)/templates/claude_md"
    local template_file="$template_dir/${profile_name}.md"

    if [[ -f "$template_file" ]]; then
        cp "$template_file" "$output_file"
    else
        _log_warning "Template not found: $template_file (skipping CLAUDE.md generation)"
    fi
}

_copy_claude_asset_if_missing() {
    local source_root="$1"
    local repo_root="$2"
    local asset_path="$3"

    local source_path="$source_root/.claude/$asset_path"
    local target_path="$repo_root/.claude/$asset_path"

    [[ -e "$source_path" ]] || return 0

    if [[ -d "$source_path" ]]; then
        mkdir -p "$target_path"
        local copied_any=false
        local item
        for item in "$source_path"/*(N); do
            local item_name
            item_name="$(basename "$item")"
            if [[ ! -e "$target_path/$item_name" ]]; then
                cp -R "$item" "$target_path/$item_name"
                copied_any=true
            fi
        done
        [[ "$copied_any" == true ]] && _log_success "Seeded: .claude/$asset_path"
        return 0
    fi

    if [[ ! -e "$target_path" ]]; then
        mkdir -p "$(dirname "$target_path")"
        cp "$source_path" "$target_path"
        _log_success "Seeded: .claude/$asset_path"
    fi
}

_seed_claude_assets() {
    local profile_name="$1"
    local repo_root="$2"

    case "$profile_name" in
        github-flow|vibe-center)
            local source_root="${VIBE_ROOT:-}"
            [[ -n "$source_root" && -d "$source_root/.claude" ]] || return 0
            _copy_claude_asset_if_missing "$source_root" "$repo_root" "settings.json"
            _copy_claude_asset_if_missing "$source_root" "$repo_root" "hooks"
            _copy_claude_asset_if_missing "$source_root" "$repo_root" "agents"
            mkdir -p "$repo_root/.claude/rules"
            ;;
    esac
}

_generate_settings_yaml() {
    local repo_root="$1"
    local settings_file="$repo_root/.vibe/settings.yaml"
    local init_lib_dir
    init_lib_dir="$(cd "$(dirname "${(%):-%x:A}")" && pwd)"
    local source_root="${VIBE_ROOT:-$(cd "$init_lib_dir/.." && pwd)}"
    local template_file="$source_root/config/v3/settings.yaml.template"

    if [[ -f "$settings_file" ]]; then
        _log_info "Already exists: .vibe/settings.yaml (skipped, not overwritten)"
        return 0
    fi

    if [[ ! -f "$template_file" ]]; then
        _log_error "Settings template not found: $template_file"
        return 1
    fi

    cp "$template_file" "$settings_file"

    _log_success "Created: .vibe/settings.yaml"
}

_seed_project_policies() {
    local repo_root="$1"
    local policies_dir="$repo_root/.vibe/policies"
    local common_md="$policies_dir/common.md"

    mkdir -p "$policies_dir"

    if [[ -f "$common_md" ]]; then
        _log_info "Already exists: .vibe/policies/common.md (skipped, not overwritten)"
        return 0
    fi

    cat > "$common_md" << 'POLICIES_EOF'
# Project-Specific Rules

> **Scope**: project scope — 追加到 `~/.vibe/policies/common.md` (user scope) 之后
> **用途**: 在此添加本项目的专属规则和约定

<!-- 在此处添加项目专属内容 -->
POLICIES_EOF

    _log_success "Created: .vibe/policies/common.md"
}

# --- Main Function ---
vibe_init() {
    # Enable strict mode for this function only
    set -euo pipefail

    # Load profiles definitions - use VIBE_LIB from current repo, not global
    local INIT_LIB_DIR="$(cd "$(dirname "${(%):-%x:A}")" && pwd)"
    source "$INIT_LIB_DIR/profiles.sh"

    # Parse arguments
    local SKIP_CONFIRM=false
    local SKIP_LABELS=false
    local PROFILE_NAME=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                vibe_init_help
                return 0
                ;;
            -l|--list-profiles)
                list_profiles
                return 0
                ;;
            -p|--profile)
                if [[ $# -lt 2 ]]; then
                    _log_error "Missing profile name after $1"
                    echo "Use: vibe init --profile <minimal|github-flow|vibe-center>"
                    return 1
                fi
                PROFILE_NAME="$2"
                shift 2
                ;;
            -y|--yes)
                SKIP_CONFIRM=true
                shift
                ;;
            --skip-labels)
                SKIP_LABELS=true
                shift
                ;;
            *)
                _log_error "Unknown option: $1"
                vibe_init_help
                return 1
                ;;
        esac
    done

    # Default profile if not specified
    if [[ -z "$PROFILE_NAME" ]]; then
        PROFILE_NAME="github-flow"
        _log_info "Using default profile: github-flow"
        echo "   Use --profile <name> to specify a different profile"
        echo ""
    fi

    # Validate profile
    if ! validate_profile "$PROFILE_NAME"; then
        return 1
    fi

    # Get profile configuration (sets global PROFILE_CONFIG_ARRAY)
    if ! get_profile_config "$PROFILE_NAME"; then
        return 1
    fi

    # --- Pre-flight checks ---
    _log_info "Checking project environment..."

    # Get profile features (needed for both pre-flight checks and execution)
    local ENABLE_GITHUB_LABELS=$(get_profile_feature "github_labels")
    local ENABLE_AGENT=$(get_profile_feature "agent")
    local ENABLE_LOCAL_SKILLS=$(get_profile_feature "local_skills")
    local ENABLE_GLOBAL_SKILLS=$(get_profile_feature "global_skills")
    local ENABLE_SUPERVISOR=$(get_profile_feature "supervisor")

    # 1. Check git environment
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        _log_error "Not in a git repository"
        echo "   Please run this command in a git repository."
        return 1
    fi

    local REPO_ROOT
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "$REPO_ROOT" ]]; then
        _log_error "Failed to determine repository root"
        return 1
    fi

    _log_success "Git repository detected: $REPO_ROOT"

    # 1b. Check for legacy features.skills in existing config (backward compat)
    local LEGACY_CONFIG="$REPO_ROOT/.vibe/config.yaml"
    if [[ -f "$LEGACY_CONFIG" ]]; then
        local _has_skills _has_local _has_global
        _has_skills=$(grep -c "^\s*skills:" "$LEGACY_CONFIG" 2>/dev/null || true)
        _has_local=$(grep -c "local_skills:" "$LEGACY_CONFIG" 2>/dev/null || true)
        _has_global=$(grep -c "global_skills:" "$LEGACY_CONFIG" 2>/dev/null || true)
        if [[ "$_has_skills" -gt 0 && "$_has_local" -eq 0 && "$_has_global" -eq 0 ]]; then
            _log_warning "Detected legacy config: features.skills is deprecated"
            echo "   Use features.local_skills + features.global_skills instead."
            echo "   Re-running init will migrate your config to the new format."
        fi
    fi

    # 2. Check GitHub CLI (only if profile requires labels)
    if [[ "$ENABLE_GITHUB_LABELS" == true && "$SKIP_LABELS" != true ]]; then
        if ! command -v gh >/dev/null 2>&1; then
            _log_warning "GitHub CLI (gh) not found"
            echo "   GitHub labels creation will be skipped."
            SKIP_LABELS=true
        elif ! git remote get-url origin >/dev/null 2>&1; then
            _log_warning "No GitHub remote found"
            echo "   GitHub labels creation will be skipped."
            _log_info "Add a remote with: git remote add origin <url>"
            _log_info "Then re-run: vibe init --profile github-flow"
            SKIP_LABELS=true
        fi
    fi

    # --- Confirmation ---
    if [[ "$SKIP_CONFIRM" != true ]]; then
        echo ""
        echo "${BOLD}Project Initialization - Profile: $PROFILE_NAME${NC}"
        echo ""
        echo "This will:"
        echo "  - Create .vibe/config.yaml (profile: $PROFILE_NAME)"
        echo "  - Create .vibe/settings.yaml (project override template)"
        echo "  - Create .vibe/policies/common.md (project-specific rules)"

        # Show profile-specific actions (variables already defined above)
        if [[ "$ENABLE_AGENT" == true ]]; then
            echo "  - Create .agent/ directory structure"
        fi

        if [[ "$ENABLE_LOCAL_SKILLS" == true ]]; then
            echo "  - Create skills/ structure"
        fi

        if [[ "$ENABLE_GLOBAL_SKILLS" == true ]]; then
            echo "  - Setup .claude/skills symlinks"
        fi

        if [[ "$ENABLE_GITHUB_LABELS" == true && "$SKIP_LABELS" != true ]]; then
            echo "  - Create GitHub labels ($(get_profile_convention "labels.state_prefix")*)"
        fi

        if [[ "$ENABLE_SUPERVISOR" == true ]]; then
            echo "  - Enable supervisor orchestration"
        fi

        echo ""

        read -q "REPLY?Continue? (y/N) " || return 1
        echo ""
    fi

    # --- Main Initialization Flow ---
    _log_info "Initializing project with profile: $PROFILE_NAME..."

    # 3. Create .vibe directory and config
    _log_info "Creating .vibe configuration..."
    mkdir -p "$REPO_ROOT/.vibe"
    generate_vibe_config_yaml "$PROFILE_NAME" "$REPO_ROOT"
    _log_success "Created: .vibe/config.yaml"

    # 3b. Create .vibe/settings.yaml override template
    _generate_settings_yaml "$REPO_ROOT"

    # 3c. Seed .vibe/policies/common.md for project-specific rules
    _seed_project_policies "$REPO_ROOT"

    # 4. Create necessary directories (profile-dependent)
    _log_info "Creating directory structure..."

    # Always create basic structure
    mkdir -p "$REPO_ROOT/.claude/skills"
    mkdir -p "$REPO_ROOT/.claude/commands"

    # Create .agent/ if profile requires
    if [[ "$ENABLE_AGENT" == true ]]; then
        mkdir -p "$REPO_ROOT/.agent/skills"
        mkdir -p "$REPO_ROOT/.agent/workflows"
        _log_success "Created: .agent/ directory structure"
    fi

    # Create skills/ if profile requires
    if [[ "$ENABLE_LOCAL_SKILLS" == true ]]; then
        mkdir -p "$REPO_ROOT/skills"
        _log_success "Created: skills/ directory"
    fi

    # Create supervisor structure if profile requires
    if [[ "$ENABLE_SUPERVISOR" == true ]]; then
        mkdir -p "$REPO_ROOT/supervisor"
        _log_success "Created: supervisor/ directory"
    fi

    _seed_claude_assets "$PROFILE_NAME" "$REPO_ROOT"

    _log_success "Directory structure created"

    # 5. Create GitHub labels (profile-dependent)
    if [[ "$ENABLE_GITHUB_LABELS" == true && "$SKIP_LABELS" != true ]]; then
        _log_info "Creating GitHub labels..."

        local STATE_PREFIX=$(get_profile_convention "labels.state_prefix")
        local VIBE_TASK=$(get_profile_convention "labels.vibe_task")

        # Define required labels based on profile
        local -a LABELS

        if [[ "$STATE_PREFIX" != "none" ]]; then
            LABELS=(
                "${STATE_PREFIX}ready:Ready for manager dispatch:EEEEEE"
                "${STATE_PREFIX}claimed:已认领,待进入执行:BFDADC"
                "${STATE_PREFIX}in-progress:执行中:0052CC"
                "${STATE_PREFIX}blocked:阻塞中:D73A4A"
                "${STATE_PREFIX}handoff:待交接:FBCA04"
                "${STATE_PREFIX}review:待 review:5319E7"
                "${STATE_PREFIX}merge-ready:已满足合并条件:0E8A16"
                "${STATE_PREFIX}done:已完成:0E8A16"
                "${STATE_PREFIX}failed:Execution failed and needs recovery:B60205"
            )
        fi

        if [[ "$VIBE_TASK" != "none" ]]; then
            LABELS+=("$VIBE_TASK:Track issues intended for vibe roadmap/task intake:5319E7")
        fi

        for label_def in "${LABELS[@]}"; do
            IFS=':' read -r name description color <<< "$label_def"

            if gh label create "$name" --description "$description" --color "$color" 2>/dev/null; then
                _log_success "Created label: $name"
            else
                # Label might already exist
                if gh label edit "$name" --description "$description" --color "$color" 2>/dev/null; then
                    _log_info "Updated label: $name"
                else
                    _log_warning "Failed to create/update label: $name"
                fi
            fi
        done

        _log_success "GitHub labels created"
    fi

    # 6. Setup .claude/skills symlinks (profile-dependent)
    if [[ "$ENABLE_GLOBAL_SKILLS" == true ]]; then
        _log_info "Setting up .claude/skills symlinks..."

        local VIBE_SKILLS_DIR="$HOME/.vibe/skills"

        if [[ -d "$VIBE_SKILLS_DIR" ]]; then
            # Use (N) glob qualifier to suppress "no matches" error
            for skill in "$VIBE_SKILLS_DIR"/vibe-*(N); do
                if [[ -d "$skill" ]]; then
                    local skill_name
                    skill_name="$(basename "$skill")"
                    local target_link="$REPO_ROOT/.claude/skills/$skill_name"

                    if [[ ! -e "$target_link" ]]; then
                        ln -sfn "$skill" "$target_link"
                        _log_success "Linked skill: $skill_name"
                    else
                        _log_info "Skill already linked: $skill_name"
                    fi
                fi
            done

            # Check if any skills were processed
            local skills_count
            skills_count=$(find "$VIBE_SKILLS_DIR" -maxdepth 1 -name "vibe-*" -type d | wc -l)
            if [[ "$skills_count" -eq 0 ]]; then
                _log_warning "No vibe-* skills found in $VIBE_SKILLS_DIR"
            fi
        else
            _log_warning "Global skills directory not found: $VIBE_SKILLS_DIR"
            echo "   Run 'scripts/install.sh' first to setup global environment."
        fi
    fi

    # 7. Verify project support
    _log_info "Verifying project support..."

    # Check for essential files (profile-dependent)
    if [[ "$PROFILE_NAME" == "minimal" ]]; then
        # minimal: auto-generate CLAUDE.md when absent.
        # Intentional behavior change: minimal profile no longer warns about missing AGENTS.md.
        # AGENTS.md is a vibe-center convention; minimal profile uses CLAUDE.md as the sole
        # AI agent context file. AGENTS.md is not required and not checked for this profile.
        if [[ -f "$REPO_ROOT/CLAUDE.md" ]]; then
            _log_success "Found: CLAUDE.md"
        else
            _generate_claude_md "$PROFILE_NAME" "$REPO_ROOT"
            _log_success "Generated: CLAUDE.md (minimal template)"
        fi
    elif [[ "$PROFILE_NAME" == "github-flow" ]]; then
        # github-flow: check and generate CLAUDE.md, warn for AGENTS.md
        for file in "CLAUDE.md" "AGENTS.md"; do
            if [[ -f "$REPO_ROOT/$file" ]]; then
                _log_success "Found: $file"
            elif [[ "$file" == "CLAUDE.md" ]]; then
                _generate_claude_md "$PROFILE_NAME" "$REPO_ROOT"
                _log_success "Generated: CLAUDE.md (github-flow template)"
            else
                _log_warning "Missing: $file (recommended for AI agent support)"
            fi
        done
    else
        # vibe-center and other profiles: check and warn, no auto-generation
        local -a ESSENTIAL_FILES=(
            "CLAUDE.md"
            "AGENTS.md"
        )

        for file in "${ESSENTIAL_FILES[@]}"; do
            if [[ -f "$REPO_ROOT/$file" ]]; then
                _log_success "Found: $file"
            else
                _log_warning "Missing: $file (recommended for AI agent support)"
            fi
        done

        # vibe-center profile requires additional files
        if [[ "$PROFILE_NAME" == "vibe-center" ]]; then
            local -a VIBE_CENTER_FILES=(
                "SOUL.md"
                "STRUCTURE.md"
            )

            for file in "${VIBE_CENTER_FILES[@]}"; do
                if [[ -f "$REPO_ROOT/$file" ]]; then
                    _log_success "Found: $file"
                else
                    _log_warning "Missing: $file (Vibe Center governance file)"
                fi
            done
        fi
    fi

    # 8. Finalize
    echo ""
    _log_success "Project initialization complete!"
    _log_success "Profile: $PROFILE_NAME"
    echo ""
    echo "Configuration:"
    echo "  - Config file: ${CYAN}.vibe/config.yaml${NC}"
    echo "  - Settings override: ${CYAN}.vibe/settings.yaml${NC}"
    echo "  - Profile: ${GREEN}$PROFILE_NAME${NC}"
    echo ""

    echo "Next steps:"
    if [[ "$PROFILE_NAME" == "minimal" ]]; then
        echo "  1. Run ${CYAN}/vibe-project-check${NC} to verify your environment"
        echo "  2. Configure manager-bot token (${CYAN}VIBE_MANAGER_GITHUB_TOKEN${NC}) if you need orchestra"
        echo "  3. Optional: start orchestra with ${CYAN}vibe3 serve${NC}"
        echo "  4. Prompts and policies come from: ${CYAN}~/.vibe${NC}"
    elif [[ "$PROFILE_NAME" == "github-flow" ]]; then
        echo "  1. Run ${CYAN}/vibe-project-check${NC} to verify your environment"
        echo "  2. Configure manager-bot token (${CYAN}VIBE_MANAGER_GITHUB_TOKEN${NC}) if you need orchestra"
        if [[ "$SKIP_LABELS" == true ]]; then
            echo "  3. Create GitHub labels manually if needed"
        else
            echo "  3. Check GitHub labels: ${CYAN}gh label list | grep ${STATE_PREFIX}${NC}"
        fi
        echo "  4. Optional: start orchestra with ${CYAN}vibe3 serve${NC}"
        echo "  5. Review created directories: ${CYAN}.agent/${NC} and ${CYAN}.claude/${NC}"
        echo "  6. Prompts and policies come from: ${CYAN}~/.vibe${NC}"
    elif [[ "$PROFILE_NAME" == "vibe-center" ]]; then
        echo "  1. Run ${CYAN}/vibe-project-check${NC} to verify your environment"
        echo "  2. Configure manager-bot token (${CYAN}VIBE_MANAGER_GITHUB_TOKEN${NC}) if you need orchestra"
        if [[ "$SKIP_LABELS" == true ]]; then
            echo "  3. Create GitHub labels manually if needed"
        else
            echo "  3. Check GitHub labels: ${CYAN}gh label list | grep ${STATE_PREFIX}${NC}"
        fi
        echo "  4. Optional: start orchestra with ${CYAN}vibe3 serve${NC}"
        echo "  5. Review created directories: ${CYAN}.agent/${NC}, ${CYAN}skills/${NC}, ${CYAN}.claude/${NC}"
        echo "  6. Policies and prompts from: ${CYAN}supervisor/policies/${NC} and ${CYAN}config/prompts${NC}"
        echo "  7. Supervisor orchestration: ${CYAN}supervisor/${NC}"
    fi
    echo ""
}

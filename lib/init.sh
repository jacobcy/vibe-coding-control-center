#!/usr/bin/env zsh
# vibe init - Project Initialization
# Initializes project directory structure and configuration

set -euo pipefail

# --- Helper Functions ---
_log_info() { echo "${CYAN}ℹ️  $1${NC}"; }
_log_success() { echo "${GREEN}✅ $1${NC}"; }
_log_warning() { echo "${YELLOW}⚠️  $1${NC}"; }
_log_error() { echo "${RED}❌ $1${NC}" >&2; }

# --- Help Function ---
vibe_init_help() {
    echo "${BOLD}vibe init${NC} - Project Initialization"
    echo ""
    echo "此命令负责项目运行环境初始化："
    echo "  1. 检查 git 环境"
    echo "  2. 创建必要的目录结构"
    echo "  3. 创建 GitHub labels（state/* 标签）"
    echo "  4. 复制 .claude/skills 符号链接"
    echo "  5. 验证项目运行支持"
    echo ""
    echo "Usage: ${CYAN}vibe init${NC} [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help        显示此帮助信息"
    echo "  -y, --yes         跳过确认提示"
    echo "  --skip-labels     跳过 GitHub labels 创建"
    echo ""
}

# --- Main Function ---
vibe_init() {
    # Parse arguments
    local SKIP_CONFIRM=false
    local SKIP_LABELS=false

    for arg in "$@"; do
        case "$arg" in
            -h|--help) vibe_init_help; return 0 ;;
            -y|--yes) SKIP_CONFIRM=true ;;
            --skip-labels) SKIP_LABELS=true ;;
        esac
    done

    # --- Pre-flight checks ---
    _log_info "Checking project environment..."

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

    # 2. Check GitHub CLI
    if ! command -v gh >/dev/null 2>&1; then
        _log_warning "GitHub CLI (gh) not found"
        echo "   GitHub labels creation will be skipped."
        SKIP_LABELS=true
    fi

    # --- Confirmation ---
    if [[ "$SKIP_CONFIRM" != true ]]; then
        echo ""
        echo "${BOLD}Project Initialization${NC}"
        echo ""
        echo "This will:"
        echo "  - Create necessary directories"
        if [[ "$SKIP_LABELS" != true ]]; then
            echo "  - Create GitHub labels (state/* tags)"
        fi
        echo "  - Setup .claude/skills symlinks"
        echo ""

        read -q "REPLY?Continue? (y/N) " || return 1
        echo ""
    fi

    # --- Main Initialization Flow ---
    _log_info "Initializing project..."

    # 3. Create necessary directories
    _log_info "Creating directory structure..."

    mkdir -p "$REPO_ROOT/.agent/skills"
    mkdir -p "$REPO_ROOT/.agent/workflows"
    mkdir -p "$REPO_ROOT/.claude/skills"
    mkdir -p "$REPO_ROOT/.claude/commands"

    _log_success "Directory structure created"

    # 4. Create GitHub labels
    if [[ "$SKIP_LABELS" != true ]]; then
        _log_info "Creating GitHub labels..."

        # Define required labels
        local -a LABELS
        LABELS=(
            "state/ready:Ready for manager dispatch:0E8A16"
            "state/claimed:Claimed and waiting for planning:1D76DB"
            "state/in-progress:Execution in progress:FBCA04"
            "state/blocked:Blocked and waiting for follow-up:D93F0B"
            "state/handoff:Waiting for manager handoff decision:5319E7"
            "state/review:Waiting for review execution:0052CC"
            "state/merge-ready:Ready to merge:0E8A16"
            "state/done:Flow completed:6A737D"
            "vibe-task:Track issues intended for vibe roadmap/task intake:5319E7"
        )

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

    # 5. Setup .claude/skills symlinks
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

    # 6. Verify project support
    _log_info "Verifying project support..."

    # Check for essential files
    local -a ESSENTIAL_FILES
    ESSENTIAL_FILES=(
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

    # 7. Finalize
    echo ""
    _log_success "Project initialization complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Review created directories: ${CYAN}.agent/${NC} and ${CYAN}.claude/${NC}"
    if [[ "$SKIP_LABELS" == true ]]; then
        echo "  2. Create GitHub labels manually if needed"
    else
        echo "  2. Check GitHub labels: ${CYAN}gh label list | grep state/${NC}"
    fi
    echo "  3. Start using vibe commands"
    echo ""
}

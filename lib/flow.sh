#!/usr/bin/env zsh
# lib/flow.sh
# Core workflow orchestration for vibe flow
# Integrates with existing tools: wtnew, vup, gh, tmux, lazygit

# Ensure required libraries are loaded
if [[ -z "${VIBE_ROOT:-}" ]]; then
    log_error "VIBE_ROOT not set. This library must be sourced after config.sh"
    return 1
fi

# Load dependencies
source "$VIBE_ROOT/lib/flow_state.sh"

# Load aliases.sh to access wtnew, vup, vnew functions
if [[ -f "$VIBE_ROOT/config/aliases.sh" ]]; then
    source "$VIBE_ROOT/config/aliases.sh"
fi

# Helper: Detect current feature from worktree directory name
detect_current_feature() {
    local dir_name=$(basename "$PWD")
    
    # Pattern: wt-<agent>-<feature>
    if [[ "$dir_name" =~ ^wt-[^-]+-(.+)$ ]]; then
        echo "${match[1]}"
        return 0
    fi
    
    return 1
}

# Helper: Check if a command exists
has_command() {
    command -v "$1" &>/dev/null
}

# =============================================================================
# COMMAND: vibe flow start
# =============================================================================

flow_cmd_start() {
    local feature="$1"
    local agent="${2:-claude}"
    local base="${3:-main}"
    
    if [[ -z "$feature" ]]; then
        log_error "Usage: vibe flow start <feature-name> [--agent=claude] [--base=main]"
        return 1
    fi
    
    # Parse options
    local opt
    for opt in "$@"; do
        case "$opt" in
            --agent=*)
                agent="${opt#*=}"
                ;;
            --base=*)
                base="${opt#*=}"
                ;;
        esac
    done
    
    echo -e "\n${YELLOW}🚀 Starting new feature: $feature${NC}\n"
    
    # Step 1: Create worktree using wtnew from aliases.sh
    log_step "Creating worktree and setting up environment"
    
    # Call wtnew which handles: worktree creation + git identity
    if ! wtnew "$feature" "$agent" "$base"; then
        log_error "Failed to create worktree"
        return 1
    fi
    
    # wtnew already cd'd into the worktree, get the path
    local wt_path="$PWD"
    local wt_dir=$(basename "$wt_path")
    local full_branch="${agent}/${feature}"
    
    # Step 2: Create PRD from template
    log_step "Creating PRD document"
    local prd_dir="docs/prds"
    mkdir -p "$prd_dir"
    
    local prd_path="$prd_dir/${feature}.md"
    local template_path="$VIBE_ROOT/templates/prd.md"
    
    if [[ -f "$template_path" ]]; then
        local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
        sed -e "s/{FEATURE_NAME}/$feature/g" \
            -e "s/{TIMESTAMP}/$timestamp/g" \
            -e "s/{AGENT}/Agent-${(C)agent}/g" \
            "$template_path" > "$prd_path"
        log_success "Created PRD: docs/prds/${feature}.md"
    else
        log_warn "Template not found, creating basic PRD"
        cat > "$prd_path" <<EOF
# PRD: $feature

## 背景

_TODO: 描述为什么需要这个功能_

## 目标

_TODO: 描述功能目标_

## 需求清单

- [ ] 需求1
- [ ] 需求2

EOF
        log_success "Created basic PRD: docs/prds/${feature}.md"
    fi
    
    # Step 3: Initialize flow state
    log_step "Initializing workflow state"
    if flow_state_init "$feature" "$full_branch" "$wt_path" "$agent"; then
        flow_state_update "$feature" "prd_path" "docs/prds/${feature}.md"
        flow_state_checklist "$feature" "prd_created" "true"
    else
        log_warn "Failed to initialize flow state (continuing anyway)"
    fi
    
    # Step 4: Set up tmux workspace (optional)
    if has_command tmux && [[ -n "${TMUX:-}" || "${VIBE_TMUX_AUTO:-false}" == "true" ]]; then
        log_step "Setting up tmux workspace"
        if vup "$wt_dir" "$agent" 2>/dev/null; then
            log_success "tmux workspace created"
        else
            log_info "Skipping tmux setup (run 'vup $wt_dir' manually if needed)"
        fi
    fi
    
    # Success summary
    echo ""
    log_success "Feature workflow started!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Edit PRD: ${CYAN}docs/prds/${feature}.md${NC}"
    echo "   2. Write spec: ${CYAN}vibe flow spec${NC}"
    echo "   3. Check status: ${CYAN}vibe flow status${NC}"
    echo ""
    echo "💡 Current directory: ${CYAN}$wt_path${NC}"
    
    if has_command tmux; then
        echo "💡 tmux workspace: ${CYAN}vup $wt_dir${NC} (if not auto-started)"
    fi
    
    echo ""
    
    return 0
}

# =============================================================================
# COMMAND: vibe flow spec
# =============================================================================

flow_cmd_spec() {
    local feature="${1:-$(detect_current_feature)}"
    
    if [[ -z "$feature" ]]; then
        log_error "Unable to detect feature. Run from worktree or specify: vibe flow spec <feature>"
        return 1
    fi
    
    echo -e "\n${YELLOW}📋 Creating technical specification for: $feature${NC}\n"
    
    # Create spec document from template
    local spec_dir="docs/specs"
    mkdir -p "$spec_dir"
    
    local spec_path="$spec_dir/${feature}-spec.md"
    local template_path="$VIBE_ROOT/templates/spec.md"
    local prd_path="docs/prds/${feature}.md"
    
    if [[ -f "$spec_path" ]]; then
        log_warn "Spec already exists: $spec_path"
        if ! confirm_action "Overwrite existing spec?"; then
            log_info "Keeping existing spec"
            return 0
        fi
    fi
    
    if [[ -f "$template_path" ]]; then
        local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
        local prd_abs_path="$(cd "$(dirname "$prd_path")" && pwd)/$(basename "$prd_path")"
        
        sed -e "s|{FEATURE_NAME}|$feature|g" \
            -e "s|{TIMESTAMP}|$timestamp|g" \
            -e "s|{AGENT}|$(git config user.name 2>/dev/null || echo 'Unknown')|g" \
            -e "s|{PRD_PATH}|$prd_abs_path|g" \
            "$template_path" > "$spec_path"
        
        log_success "Created spec: $spec_path"
    else
        log_warn "Template not found, creating basic spec"
        cat > "$spec_path" <<EOF
# 技术规格：$feature

## Overview

_TODO: 描述技术实现方案_

## API 设计

_TODO: 定义接口_

## 测试计划

- [ ] 测试场景1
- [ ] 测试场景2

EOF
        log_success "Created basic spec: $spec_path"
    fi
    
    # Update flow state
    flow_state_update "$feature" "spec_path" "$spec_path" 2>/dev/null || true
    flow_state_update "$feature" "current_phase" "specification" 2>/dev/null || true
    flow_state_checklist "$feature" "spec_written" "true" 2>/dev/null || true
    
    echo ""
    echo "📝 Next steps:"
    echo "   1. Define API interfaces and data structures"
    echo "   2. Create test plan: ${CYAN}vibe flow test${NC}"
    echo ""
    
    return 0
}

# =============================================================================
# COMMAND: vibe flow test
# =============================================================================

flow_cmd_test() {
    local feature="${1:-$(detect_current_feature)}"
    
    if [[ -z "$feature" ]]; then
        log_error "Unable to detect feature. Run from worktree or specify: vibe flow test <feature>"
        return 1
    fi
    
    echo -e "\n${YELLOW}🧪 Initializing tests for: $feature${NC}\n"
    
    # Create test file (similar to vibe tdd new)
    local test_file="tests/test_${feature}.sh"
    
    if [[ -f "$test_file" ]]; then
        log_warn "Test file already exists: $test_file"
        if ! confirm_action "Overwrite existing test?"; then
            log_info "Keeping existing test"
            return 0
        fi
    fi
    
    mkdir -p tests
    
    cat > "$test_file" <<EOF
#!/usr/bin/env zsh
# Test for $feature
# Generated by vibe flow test

source "lib/utils.sh"
source "lib/config.sh"

log_step "Running tests for $feature..."

# TODO: Implement test cases
# Example test structure:
#
# test_case_1() {
#     if some_command; then
#         log_success "PASS: test case 1"
#         return 0
#     else
#         log_error "FAIL: test case 1"
#         return 1
#     fi
# }
#
# test_case_1 || exit 1

log_error "Tests not implemented yet! (TDD Red Phase)"
log_info "Next: Implement test cases, then run: ./$test_file"
exit 1
EOF
    
    chmod +x "$test_file"
    log_success "Created test file: $test_file"
    
    # Update flow state
    flow_state_update "$feature" "test_path" "$test_file" 2>/dev/null || true
    flow_state_update "$feature" "current_phase" "testing" 2>/dev/null || true
    flow_state_checklist "$feature" "tests_initialized" "true" 2>/dev/null || true
    
    # Try to run the test (should fail - Red Phase)
    echo ""
    log_info "Running initial test (should FAIL - Red Phase)..."
    echo ""
    
    if ./"$test_file" 2>&1 | head -20; then
        log_warn "Test passed unexpectedly!"
    else
        log_info "✅ Test failed as expected (Red Phase)"
    fi
    
    echo ""
    echo "📝 Next steps:"
    echo "   1. Implement test cases in: ${CYAN}$test_file${NC}"
    echo "   2. Start development: ${CYAN}vibe flow dev${NC}"
    echo "   3. Run tests: ${CYAN}./$test_file${NC}"
    echo ""
    
    return 0
}

# =============================================================================
# COMMAND: vibe flow dev
# =============================================================================

flow_cmd_dev() {
    local feature="${1:-$(detect_current_feature)}"
    
    if [[ -z "$feature" ]]; then
        log_error "Unable to detect feature. Run from worktree or specify: vibe flow dev <feature>"
        return 1
    fi
    
    echo -e "\n${YELLOW}🔄 TDD Development Loop${NC}\n"
    
    # Show current status
    local test_path=$(flow_state_get "$feature" "test_path" 2>/dev/null)
    
    echo "${BOLD}Development Workflow:${NC}"
    echo "  1. ${RED}Red${NC}: Write a failing test"
    echo "  2. ${GREEN}Green${NC}: Make the test pass"
    echo "  3. 🔧 ${CYAN}Refactor${NC}: Improve the code"
    echo ""
    
    if [[ -n "$test_path" && "$test_path" != "null" ]]; then
        echo "Run tests: ${CYAN}./$test_path${NC}"
        echo ""
    fi
    
    echo "${BOLD}Recommended Agent Tools:${NC}"
    if has_command claude; then
        echo "  • ${CYAN}claude${NC} - Claude Code (interactive)"
    fi
    if has_command opencode; then
        echo "  • ${CYAN}opencode${NC} - OpenCode (interactive)"
    fi
    if has_command codex; then
        echo "  • ${CYAN}codex --yes${NC} - Codex (auto-approve mode)"
    fi
    echo ""
    
    echo "${BOLD}Code Review:${NC}"
    if has_command lazygit; then
        echo "  • ${CYAN}lazygit${NC} - Review changes and commit"
    else
        echo "  • ${CYAN}git status${NC} - Check changes"
    fi
    echo ""
    
    echo "💡 When tests pass, run: ${CYAN}vibe flow review${NC}"
    echo ""
    
    return 0
}

# =============================================================================
# COMMAND: vibe flow review
# =============================================================================

flow_cmd_review() {
    local feature="${1:-$(detect_current_feature)}"
    
    if [[ -z "$feature" ]]; then
        log_error "Unable to detect feature. Run from worktree or specify: vibe flow review <feature>"
        return 1
    fi
    
    echo -e "\n${YELLOW}🔍 Code Review Checklist${NC}\n"
    
    # Run tests first
    local test_path=$(flow_state_get "$feature" "test_path" 2>/dev/null)
    if [[ -n "$test_path" && "$test_path" != "null" && -f "$test_path" ]]; then
        log_step "Running tests"
        if ./"$test_path"; then
            log_success "All tests passed!"
            flow_state_checklist "$feature" "tests_passing" "true" 2>/dev/null || true
        else
            log_error "Tests failed. Fix them before review."
            return 1
        fi
        echo ""
    fi
    
    # Show review checklist
    echo "${BOLD}Review Checklist:${NC}"
    echo "  [ ] Code follows project conventions"
    echo "  [ ] All tests pass"
    echo "  [ ] No debug code or console.log"
    echo "  [ ] Error handling is appropriate"
    echo "  [ ] Documentation is updated"
    echo "  [ ] No sensitive data in code"
    echo ""
    
    # Launch lazygit if available
    if has_command lazygit; then
        echo "💡 Opening lazygit for code review..."
        echo ""
        if confirm_action "Open lazygit now?"; then
            lazygit
            flow_state_checklist "$feature" "code_reviewed" "true" 2>/dev/null || true
        fi
    else
        log_info "Install lazygit for better code review experience"
        echo "   Or use: ${CYAN}git diff${NC} and ${CYAN}git add${NC}"
    fi
    
    echo ""
    echo "📝 Next step: ${CYAN}vibe flow pr${NC}"
    echo ""
    
    return 0
}

# =============================================================================
# COMMAND: vibe flow pr
# =============================================================================

flow_cmd_pr() {
    local feature="${1:-$(detect_current_feature)}"
    
    if [[ -z "$feature" ]]; then
        log_error "Unable to detect feature. Run from worktree or specify: vibe flow pr <feature>"
        return 1
    fi
    
    echo -e "\n${YELLOW}📤 Creating Pull Request${NC}\n"
    
    # Generate PR description from template
    local pr_file="temp/pr-${feature}.md"
    mkdir -p temp
    
    local template_path="$VIBE_ROOT/templates/pr.md"
    
    if [[ -f "$template_path" ]]; then
        local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
        local branch=$(git branch --show-current)
        
        # Get commit summary
        local commits=$(git log --oneline main..HEAD 2>/dev/null | head -10)
        
        sed -e "s|{FEATURE_NAME}|$feature|g" \
            -e "s|{TIMESTAMP}|$timestamp|g" \
            -e "s|{BRANCH}|$branch|g" \
            "$template_path" > "$pr_file"
        
        log_success "Generated PR description: $pr_file"
    fi
    
    # Try to create PR with gh
    if has_command gh; then
        echo ""
        log_info "GitHub CLI detected"
        
        if confirm_action "Create PR with gh now?"; then
            local pr_title="feat: $feature"
            
            if [[ -f "$pr_file" ]]; then
                gh pr create --title "$pr_title" --body-file "$pr_file"
            else
                gh pr create --title "$pr_title" --fill
            fi
            
            if [[ $? -eq 0 ]]; then
                log_success "PR created successfully!"
                flow_state_checklist "$feature" "pr_created" "true" 2>/dev/null || true
                
                # Get PR URL
                local pr_url=$(gh pr view --json url -q .url 2>/dev/null)
                if [[ -n "$pr_url" ]]; then
                    flow_state_update "$feature" "pr_url" "$pr_url" 2>/dev/null || true
                    echo "PR URL: ${CYAN}$pr_url${NC}"
                fi
            fi
        fi
    else
        log_warn "GitHub CLI (gh) not found"
        echo ""
        echo "Install gh: ${CYAN}brew install gh${NC}"
        echo "Or create PR manually using: ${CYAN}$pr_file${NC}"
    fi
    
    echo ""
    echo "📝 After PR is merged: ${CYAN}vibe flow done${NC}"
    echo ""
    
    return 0
}

# =============================================================================
# COMMAND: vibe flow done
# =============================================================================

flow_cmd_done() {
    local feature="${1:-$(detect_current_feature)}"
    
    if [[ -z "$feature" ]]; then
        log_error "Unable to detect feature. Run from worktree or specify: vibe flow done <feature>"
        return 1
    fi
    
    echo -e "\n${YELLOW}✅ Completing workflow: $feature${NC}\n"
    
    # Check if PR is merged (if gh available)
    if has_command gh; then
        local pr_state=$(gh pr view --json state -q .state 2>/dev/null)
        
        if [[ "$pr_state" == "MERGED" ]]; then
            log_success "PR is merged!"
            flow_state_checklist "$feature" "pr_merged" "true" 2>/dev/null || true
        elif [[ "$pr_state" == "OPEN" ]]; then
            log_warn "PR is still open. Merge it before running 'vibe flow done'"
            return 1
        fi
    fi
    
    # Verify tests pass
    local test_path=$(flow_state_get "$feature" "test_path" 2>/dev/null)
    if [[ -n "$test_path" && "$test_path" != "null" && -f "$test_path" ]]; then
        log_step "Running final tests"
        if ! ./"$test_path"; then
            log_error "Tests failed. Fix them before completing."
            return 1
        fi
        log_success "All tests passed!"
        echo ""
    fi
    
    # Archive flow state
    log_step "Archiving workflow state"
    if flow_state_archive "$feature"; then
        log_success "Workflow state archived"
    fi
    
    # Ask to remove worktree
    echo ""
    if confirm_action "Remove worktree for $feature?"; then
        local wt_dir="wt-*-${feature}"
        
        # Use wtrm from aliases.sh
        if wtrm "$wt_dir" 2>/dev/null; then
            log_success "Worktree removed"
        else
            log_warn "Failed to remove worktree (may need manual cleanup)"
        fi
    fi
    
    echo ""
    log_success "🎉 Feature complete: $feature"
    echo ""
    
    return 0
}

# =============================================================================
# COMMAND: vibe flow status
# =============================================================================

flow_cmd_status() {
    local feature="${1:-$(detect_current_feature)}"
    
    if [[ -z "$feature" ]]; then
        log_error "Unable to detect feature. Run from worktree or specify: vibe flow status <feature>"
        return 1
    fi
    
    echo -e "\n${YELLOW}📍 Workflow Status: $feature${NC}\n"
    
    # Get flow state
    local state_file=$(get_flow_state_file "$feature")
    
    if [[ ! -f "$state_file" ]]; then
        log_warn "No workflow state found for: $feature"
        echo "This feature may have been started before flow tracking was enabled."
        return 1
    fi
    
    # Display state information
    if command -v jq &>/dev/null; then
        local branch=$(jq -r '.branch' "$state_file")
        local worktree=$(jq -r '.worktree' "$state_file")
        local agent=$(jq -r '.agent' "$state_file")
        local phase=$(jq -r '.current_phase' "$state_file")
        
        echo "Current phase: ${CYAN}${phase}${NC}"
        echo "Worktree: $worktree"
        echo "Branch: $branch"
        echo "Agent: Agent-${(C)agent}"
        echo ""
        
        echo "${BOLD}Progress:${NC}"
        local prd_created=$(jq -r '.checklist.prd_created' "$state_file")
        local spec_written=$(jq -r '.checklist.spec_written' "$state_file")
        local tests_init=$(jq -r '.checklist.tests_initialized' "$state_file")
        local tests_pass=$(jq -r '.checklist.tests_passing' "$state_file")
        local reviewed=$(jq -r '.checklist.code_reviewed' "$state_file")
        local pr_created=$(jq -r '.checklist.pr_created' "$state_file")
        local pr_merged=$(jq -r '.checklist.pr_merged' "$state_file")
        
        [[ "$prd_created" == "true" ]] && echo "  ✅ PRD created" || echo "  ⬜ PRD created"
        [[ "$spec_written" == "true" ]] && echo "  ✅ Spec written" || echo "  ⬜ Spec written"
        [[ "$tests_init" == "true" ]] && echo "  ✅ Tests initialized" || echo "  ⬜ Tests initialized"
        [[ "$tests_pass" == "true" ]] && echo "  ✅ Tests passing" || echo "  🔄 Development in progress"
        [[ "$reviewed" == "true" ]] && echo "  ✅ Code reviewed" || echo "  ⬜ Code review"
        [[ "$pr_created" == "true" ]] && echo "  ✅ PR created" || echo "  ⬜ PR created"
        [[ "$pr_merged" == "true" ]] && echo "  ✅ Merged" || echo "  ⬜ Merged"
        
        echo ""
        echo "${BOLD}Next steps:${NC}"
        
        if [[ "$prd_created" != "true" ]]; then
            echo "  1. Edit PRD: vibe flow start"
        elif [[ "$spec_written" != "true" ]]; then
            echo "  1. Write spec: vibe flow spec"
        elif [[ "$tests_init" != "true" ]]; then
            echo "  1. Initialize tests: vibe flow test"
        elif [[ "$tests_pass" != "true" ]]; then
            echo "  1. Continue development: vibe flow dev"
            local test_path=$(jq -r '.test_path' "$state_file")
            [[ "$test_path" != "null" ]] && echo "  2. Run tests: ./$test_path"
        elif [[ "$reviewed" != "true" ]]; then
            echo "  1. Review code: vibe flow review"
        elif [[ "$pr_created" != "true" ]]; then
            echo "  1. Create PR: vibe flow pr"
        elif [[ "$pr_merged" != "true" ]]; then
            echo "  1. Waiting for PR merge..."
            echo "  2. After merge: vibe flow done"
        else
            echo "  ✨ Feature complete!"
        fi
    else
        log_warn "jq not available, showing raw state"
        cat "$state_file"
    fi
    
    echo ""
    return 0
}

# =============================================================================
# COMMAND: vibe flow rotate
# =============================================================================

flow_cmd_rotate() {
    local new_task="$1"
    
    if [[ -z "$new_task" ]]; then
        log_error "Usage: vibe flow rotate <new-task-name>"
        return 1
    fi
    
    # 1. Ensure we are in a worktree
    # Check if .git is a file (worktree) not a dir (main repo)
    if [[ -d ".git" ]]; then
         log_error "This command must be run from a worktree, not the main repository."
         return 1
    fi
    
    if [[ ! -f ".git" ]]; then
         log_error "Not a git repository."
         return 1
    fi

    echo -e "\n🔄 Rotating to new task: $new_task\n"

    # 2. Stash changes
    log_step "Stashing uncommitted changes"
    # Check for changes first
    if [[ -n "$(git status --porcelain)" ]]; then
        if git stash push -m "Rotate to $new_task: saved WIP from previous task"; then
            log_success "Stashed changes"
        else
            log_error "Failed to stash changes"
            return 1
        fi
    else
        log_info "No uncommitted changes to stash"
    fi

    # 3. Get current branch
    local old_branch=$(git branch --show-current)
    log_info "Current branch: $old_branch"

    # 4. Create new branch from main
    log_step "Creating new branch: $new_task"
    # Fetch main first to be up to date
    log_info "Fetching origin/main..."
    git fetch origin main
    
    # Create new branch based on origin/main
    # We use checkout -B to force create/reset if exists (or should we fail?)
    # User said "create new development branch", implies new.
    if ! git checkout -b "$new_task" origin/main; then
        log_error "Failed to create new branch $new_task"
        return 1
    fi

    # 5. Delete old branch
    log_step "Removing old branch: $old_branch"
    # User requirement: "删除已完成的分支" (delete completed branch)
    # We assume 'completed' means user is done with it, so we force delete.
    if git branch -D "$old_branch"; then
        log_success "Deleted $old_branch"
    else
        log_error "Failed to delete $old_branch"
    fi

    # 6. Pop stash
    log_step "Applying saved changes"
    # Check if we stashed something for this rotation
    # Note: git stash pop applies the top stash. If we stashed above, it's at stash@{0}
    if [[ -n "$(git stash list | grep "Rotate to $new_task")" ]]; then
         if git stash pop; then
             log_success "Applied changes to $new_task"
         else
             log_warn "Failed to pop stash (conflicts?). Manual intervention required."
         fi
    else
        log_info "No specific stash found to apply."
    fi

    echo ""
    log_success "✅ Task rotated successfully!"
    echo "  Old branch: $old_branch (Deleted)"
    echo "  New branch: $new_task"
    echo ""
    
    return 0
}

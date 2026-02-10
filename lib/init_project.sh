#!/usr/bin/env zsh
# init_project.sh
# Project initialization (local templates + AI mode)

if [[ -n "${VIBE_INIT_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
readonly VIBE_INIT_LOADED=1

# Collect basic answers for templates/AI prompt
vibe_collect_init_answers() {
    local preset_dir="${1:-}"
    typeset -gA VIBE_INIT_ANS

    if [[ -n "$preset_dir" ]]; then
        VIBE_INIT_ANS[project_dir]="$preset_dir"
    else
        VIBE_INIT_ANS[project_dir]=$(prompt_user "Enter project name (create dir) or '.' for current" "." "validate_input")
    fi

    VIBE_INIT_ANS[project_type]=$(prompt_user "Project type (web/cli/backend/lib)" "web" "validate_input")
    VIBE_INIT_ANS[language]=$(prompt_user "Primary language" "TypeScript" "validate_input")
    VIBE_INIT_ANS[framework]=$(prompt_user "Framework (optional)" "" "validate_input_allow_empty")
    VIBE_INIT_ANS[testing]=$(prompt_user "Test stack" "" "validate_input_allow_empty")
    VIBE_INIT_ANS[style]=$(prompt_user "Lint/format" "" "validate_input_allow_empty")
    VIBE_INIT_ANS[description]=$(prompt_user "Project description (optional)" "" "validate_content")
    VIBE_INIT_ANS[agents]=$(prompt_user "Need agent roles? (y/n)" "y" "validate_input")
}


# Resolve and prepare target directory
vibe_prepare_target_dir() {
    local target_dir="$1"

    # Sanitize input
    target_dir=$(sanitize_filename "$target_dir")

    if ! validate_path "$target_dir" "Project name validation failed"; then
        log_error "Invalid project path: $target_dir"
        return 1
    fi

    if [[ ! -d "$target_dir" ]]; then
        log_warn "Target directory $target_dir does not exist, creating..."
        if ! mkdir -p "$target_dir" 2>/dev/null; then
            log_critical "Failed to create target directory: $target_dir"
            return 1
        fi
    fi

    local abs
    if ! abs=$(cd "$target_dir" 2>/dev/null && pwd); then
        log_critical "Cannot access target directory: $target_dir"
        return 1
    fi

    if ! validate_path "$abs" "Absolute target directory validation failed"; then
        log_critical "Invalid absolute target directory: $abs"
        return 1
    fi

    echo "$abs"
}

# Initialize git repo if needed
vibe_ensure_git_init() {
    if ! command -v git >/dev/null 2>&1; then
        log_warn "git not found; skipping git init"
        return 0
    fi

    if [[ ! -d ".git" && ! -f ".git" ]]; then
        if git init >/dev/null 2>&1; then
            log_info "Initialized git repository"
        else
            log_warn "Git init failed; continuing without git"
        fi
    fi
}

# Write file if missing
vibe_write_if_missing() {
    local path="$1"
    local content="$2"

    if [[ -f "$path" ]]; then
        log_info "✓ $path already exists, skipping"
        return 0
    fi

    secure_write_file "$path" "$content" "644"
}

# Generate local templates
vibe_generate_local_templates() {
    local target_dir="$1"
    
    cd "$target_dir" || return 1
    vibe_ensure_git_init

    log_step "Initializing project-level rules (.cursor/rules/tech-stack.mdc)"
    mkdir -p .cursor/rules 2>/dev/null || {
        log_error "Failed to create .cursor/rules directory"
        return 1
    }

    local tech_stack_template="# Project Tech Stack Rules\n\n## Language & Framework\n- Language: ${VIBE_INIT_ANS[language]}\n- Framework: ${VIBE_INIT_ANS[framework]:-N/A}\n\n## Testing\n- Stack: ${VIBE_INIT_ANS[testing]:-N/A}\n\n## Lint/Format\n- ${VIBE_INIT_ANS[style]:-N/A}\n"

    vibe_write_if_missing ".cursor/rules/tech-stack.mdc" "$tech_stack_template" || return 1

    local soul_template="# SOUL (思维灵魂)\n\n- Purpose: ${VIBE_INIT_ANS[description]:-TBD}\n- Non‑negotiables: (始终保持安全性, 最小化改动, 保持工作空间整洁)\n- Values: (高效, 简洁, 自动化)\n"
    local memory_template="# MEMORY (长期记忆)\n\n## 关键决策\n- 初始化项目结构\n\n## 项目上下文\n- 类型: ${VIBE_INIT_ANS[project_type]}\n"
    local task_template="# TASK (任务看板)\n\n- [ ] 完成初始化配置\n"
    local workflow_template="# WORKFLOW (工作流)\n\n- 使用 \`/initialize\` 检查项目标准\n- 使用 \`/post-task\` 进行任务后维护\n"
    local agent_template="# AGENT (代理设定)\n\n- Role: Vibe Coding Agent\n- Persona: 专业的自动化编码助手\n"
    local rules_template="# RULES (行为守则)\n\n- 代码风格: ${VIBE_INIT_ANS[style]:-TBD}\n- 测试驱动: ${VIBE_INIT_ANS[testing]:-TBD}\n"

    local claude_md="# Project Context\n\n## Overview\n- Type: ${VIBE_INIT_ANS[project_type]}\n- Language: ${VIBE_INIT_ANS[language]}\n- Framework: ${VIBE_INIT_ANS[framework]:-N/A}\n\n## Linked Docs\n- SOUL.md\n- MEMORY.md\n- TASK.md\n- WORKFLOW.md\n- AGENT.md\n- RULES.md\n\n## Notes\n- Keep these docs consistent; CLAUDE.md only indexes them.\n"

    log_step "Generating base docs (SOUL/MEMORY/TASK/WORKFLOW/AGENT/RULES/CLAUDE.md)"
    vibe_write_if_missing "SOUL.md" "$soul_template" || return 1
    vibe_write_if_missing "MEMORY.md" "$memory_template" || return 1
    vibe_write_if_missing "TASK.md" "$task_template" || return 1
    vibe_write_if_missing "WORKFLOW.md" "$workflow_template" || return 1
    vibe_write_if_missing "AGENT.md" "$agent_template" || return 1
    vibe_write_if_missing "RULES.md" "$rules_template" || return 1
    vibe_write_if_missing "CLAUDE.md" "$claude_md" || return 1

    return 0
}

# Build AI prompt for content generation
vibe_build_ai_prompt() {
    
    cat <<PROMPT
You are generating project onboarding documents.

Context:
- Project type: ${VIBE_INIT_ANS[project_type]}
- Language: ${VIBE_INIT_ANS[language]}
- Framework: ${VIBE_INIT_ANS[framework]:-N/A}
- Testing: ${VIBE_INIT_ANS[testing]:-N/A}
- Lint/Format: ${VIBE_INIT_ANS[style]:-N/A}
- Description: ${VIBE_INIT_ANS[description]:-TBD}

Generate the following files in plain text with NO code fences.
Use the exact header format shown.

### FILE: SOUL.md
<content>
### FILE: MEMORY.md
<content>
### FILE: TASK.md
<content>
### FILE: WORKFLOW.md
<content>
### FILE: AGENT.md
<content>
### FILE: RULES.md
<content>
### FILE: CLAUDE.md
<content>

Constraints:
- SOUL.md: values and non-negotiables
- MEMORY.md: key decisions and context
- TASK.md: empty checklist skeleton
- WORKFLOW.md: documentation of workflows
- AGENT.md: roles and responsibilities
- RULES.md: behavior rules
- CLAUDE.md: only index/link to the other files and summarize project meta
PROMPT
}

# Parse AI output and write files
vibe_write_ai_output() {
    local target_dir="$1"
    local output="$2"

    cd "$target_dir" || return 1
    vibe_ensure_git_init

    local current_file=""
    local buffer=""

    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" == "### FILE: "* ]]; then
            if [[ -n "$current_file" ]]; then
                vibe_write_if_missing "$current_file" "$buffer" || return 1
            fi
            current_file="${line#"### FILE: "}"
            buffer=""
        else
            buffer+="$line"$'\n'
        fi
    done <<< "$output"

    if [[ -n "$current_file" ]]; then
        vibe_write_if_missing "$current_file" "$buffer" || return 1
    fi

    return 0
}

# AI generation path
vibe_generate_ai_templates() {
    local target_dir="$1"
    local tool="$2"

    local prompt
    prompt=$(vibe_build_ai_prompt)

    log_step "Generating docs via AI ($tool)"
    local output
    if ! output=$(vibe_run_ai_prompt "$tool" "$prompt"); then
        log_warn "AI generation failed; falling back to local templates"
        vibe_generate_local_templates "$target_dir"
        return $?
    fi

    if ! vibe_write_ai_output "$target_dir" "$output"; then
        log_warn "AI output parsing failed; falling back to local templates"
        vibe_generate_local_templates "$target_dir"
        return $?
    fi

    return 0
}

# Main entry
vibe_init_project() {
    local mode="$1"

    local target_dir
    target_dir=$(vibe_prepare_target_dir "${VIBE_INIT_ANS[project_dir]}") || return 1

    if [[ "$mode" == "ai" ]]; then
        local tool
        if ! tool=$(vibe_select_default_tool); then
            log_warn "No tools available; using local templates"
            vibe_generate_local_templates "$target_dir"
            return $?
        fi
        vibe_generate_ai_templates "$target_dir" "$tool"
    else
        vibe_generate_local_templates "$target_dir"
    fi
}

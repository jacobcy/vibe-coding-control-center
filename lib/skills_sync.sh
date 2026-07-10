#!/usr/bin/env zsh
# lib/skills_sync.sh - Skills sync internals

_vibe_skills_registry_file() { echo "$VIBE_ROOT/skills/vibe-skills-manager/registry.json"; }
_vibe_skills_count_entries() { [[ -d "$1" ]] && find "$1" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ' || echo 0; }
_vibe_skills_project_count() {
    find "$VIBE_ROOT/skills" -mindepth 1 -maxdepth 1 -type d -name 'vibe-*' | wc -l | tr -d ' '
}
_vibe_skills_expected_project_names() {
    local skill_dir
    for skill_dir in "$VIBE_ROOT"/skills/vibe-*(/N); do
        echo "${skill_dir:t}"
    done | sort -u
}
_vibe_skills_target_health() {
    local target="$1"
    local linked=0 missing=0 broken=0 name

    [[ -d "$target" ]] || {
        echo "skip|0|0"
        return 0
    }

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        if [[ -L "$target/$name" ]]; then
            if [[ -e "$target/$name" ]]; then
                linked=$((linked + 1))
            else
                broken=$((broken + 1))
            fi
        elif [[ -e "$target/$name" ]]; then
            linked=$((linked + 1))
        else
            missing=$((missing + 1))
        fi
    done < <(_vibe_skills_expected_project_names)

    echo "$linked|$missing|$broken"
}
_vibe_skills_target_missing_names() {
    local target="$1"
    local name

    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        [[ -e "$target/$name" ]] || echo "$name"
    done < <(_vibe_skills_expected_project_names)
}
_vibe_skills_claude_plugin_count() {
    if ! command -v claude >/dev/null 2>&1; then
        echo ""
        return 0
    fi
    claude plugin list 2>&1 | grep -c '^  ❯ ' | tr -d ' '
}

# Read agents list from skills-expected.yaml (replaced registry.json in #204)
_vibe_skills_expected_file() { echo "$VIBE_ROOT/skills/vibe-skills-manager/skills-expected.yaml"; }
_vibe_skills_manifest_file() {
    if [[ -f "$VIBE_ROOT/config/v3/skills.json" ]]; then
        echo "$VIBE_ROOT/config/v3/skills.json"
    elif [[ -f "$VIBE_ROOT/config/skills.json" ]]; then
        echo "$VIBE_ROOT/config/skills.json"
    else
        echo "$HOME/.vibe/skills.json"
    fi
}

_vibe_skills_global_agents() {
    local manifest="$(_vibe_skills_manifest_file)"
    if [[ -f "$manifest" ]] && command -v jq >/dev/null 2>&1; then
        jq -r '.global.agents[]?' "$manifest"
    fi
}

_vibe_skills_project_agents() {
    local manifest="$(_vibe_skills_manifest_file)"
    if [[ -f "$manifest" ]] && command -v jq >/dev/null 2>&1; then
        jq -r '.project.agents[]?' "$manifest"
    else
        echo "claude-code"
        echo "codex"
        echo "opencode"
        echo "agy"
    fi
}

_vibe_skills_superpowers() {
    echo "brainstorming"
    echo "systematic-debugging"
    echo "writing-plans"
    echo "executing-plans"
    echo "verification-before-completion"
}

_vibe_skills_agent_dir() {
    case "$1" in
        codex) echo "$HOME/.agents/skills" ;;
        *) echo "$HOME/.agents/skills/$1" ;;
    esac
}

_vibe_skills_project_targets() {
    local agent
    for agent in "$@"; do
        case "$agent" in
            claude-code) echo "$VIBE_ROOT/.claude/skills" ;;
            agy) echo "$VIBE_ROOT/.agent/skills" ;;
            *) echo "$VIBE_ROOT/.$agent/skills" ;;
        esac
    done
}

_vibe_skills_sync_claude_plugin() {
    local plugin_file="$HOME/.claude/plugins/installed_plugins.json"
    log_step "检查 Claude Code superpowers plugin"
    if [[ -f "$plugin_file" ]] && grep -q "superpowers@claude-plugins-official" "$plugin_file" 2>/dev/null; then
        log_success "Claude Code superpowers plugin 已安装"
    elif vibe_has claude && claude plugin add superpowers 2>/dev/null; then
        log_success "Claude Code superpowers plugin 安装成功"
    else
        log_warn "无法自动安装，请手动运行: claude plugin add superpowers"
    fi
}

_vibe_skills_codex_superpowers_installed() {
    command -v codex >/dev/null 2>&1 || return 1
    codex plugin list 2>/dev/null | grep -q '^superpowers@[^[:space:]]\+[[:space:]]\+installed, enabled'
}

_vibe_skills_sync_codex_plugin() {
    log_step "检查 Codex superpowers plugin"
    if _vibe_skills_codex_superpowers_installed; then
        log_success "Codex superpowers plugin 已安装"
        return 0
    fi
    if ! vibe_has codex; then
        log_warn "codex CLI 不可用，跳过 Codex superpowers plugin"
        return 0
    fi
    codex plugin marketplace add https://github.com/obra/superpowers.git >/dev/null 2>&1 || true
    if codex plugin add superpowers@superpowers-dev >/dev/null 2>&1; then
        log_success "Codex superpowers plugin 安装成功"
    else
        log_warn "无法自动安装，请手动运行: codex plugin marketplace add https://github.com/obra/superpowers.git && codex plugin add superpowers@superpowers-dev"
    fi
}

_vibe_skills_sync_agents_symlinks() {
    local agent agent_dir skill_dir skill_name
    mkdir -p "$HOME/.agents/skills"
    for agent in "$@"; do
        [[ "$agent" == "codex" ]] && continue
        agent_dir="$(_vibe_skills_agent_dir "$agent")"
        mkdir -p "$agent_dir"
        for skill_dir in "$HOME/.agents/skills"/*(/N); do
            skill_name="${skill_dir:t}"
            ln -sfn "$HOME/.agents/skills/$skill_name" "$agent_dir/$skill_name"
        done
    done
}

_vibe_skills_sync_global_superpowers() {
    local -a agents skills cmd
    local agent skill output
    local skills_cli_version superpowers_ref superpowers_source
    agents=(${(f)"$(_vibe_skills_global_agents | grep -Ev '^(codex|claude-code)$' || true)"})
    skills=(${(f)"$(_vibe_skills_superpowers)"})
    if (( ${#agents[@]} == 0 )); then
        log_success "无 npx Superpowers agent 需要同步（Codex/Claude 使用 plugin）"
        return 0
    fi
    (( ${#skills[@]} )) || { vibe_die "No superpowers skills found in registry"; return 1; }
    skills_cli_version="${VIBE_SKILLS_CLI_VERSION:-1.4.4}"
    superpowers_ref="${VIBE_SUPERPOWERS_REF:-e4a2375cb705ca5800f0833528ce36a3faf9017a}"
    superpowers_source="obra/superpowers@${superpowers_ref}"
    log_step "同步全局 Superpowers skills (${(j: :)agents})"
    cmd=(npx --yes --package "skills@${skills_cli_version}" skills add "$superpowers_source" -g --agent)
    for agent in "${agents[@]}"; do cmd+=("$agent"); done
    for skill in "${skills[@]}"; do cmd+=(--skill "$skill"); done
    cmd+=(-y)
    output="$("${cmd[@]}" 2>&1)" || {
        echo "$output" >&2
        return 1
    }
    echo "$output" | grep -E "(Installed|✓|already)" || true
    log_success "全局 Superpowers 已同步"
    _vibe_skills_sync_agents_symlinks "${agents[@]}"
    log_success "各 Agent skills 已同步"
}

_vibe_skills_sync_local_skills() {
    local -a agents targets
    local target skill_dir name count=0
    agents=(${(f)"$(_vibe_skills_project_agents)"})
    targets=(${(f)"$(_vibe_skills_project_targets "${agents[@]}")"})
    log_step "同步本地 vibe-* skills"
    for target in "${targets[@]}"; do mkdir -p "$target"; done
    for skill_dir in "$VIBE_ROOT"/skills/vibe-*(/N); do
        name="${skill_dir:t}"
        for target in "${targets[@]}"; do ln -sfn "$skill_dir" "$target/$name"; done
        count=$((count + 1))
    done
    log_success "已链接 $count 个本地 skills"
}

_vibe_skills_check_status() {
    local claude_plugins global_count project_count count agent agent_dir target
    local linked missing broken
    local -a agents
    local -a missing_names

    echo "${BOLD}Skills 状态检查${NC}"
    echo "---------------------------------"
    echo ""
    echo "${CYAN}Claude Code:${NC}"
    if command -v claude >/dev/null 2>&1; then
        claude_plugins="$(_vibe_skills_claude_plugin_count)"
        echo "  CLI: 已安装"
        if [[ -n "$claude_plugins" ]]; then
            echo "  Plugins: $claude_plugins 个（以 claude plugin list 为准）"
        else
            echo "  Plugins: 无法读取（claude plugin list 不可用）"
        fi
    else
        echo "  CLI: 未安装 claude"
    fi
    project_count="$(_vibe_skills_project_count)"
    target="$VIBE_ROOT/.claude/skills"
    IFS='|' read -r linked missing broken <<< "$(_vibe_skills_target_health "$target")"
    echo "  项目 Skills: $linked/$project_count"
    (( broken > 0 )) && echo "  Broken links: $broken"
    if (( missing > 0 )); then
        echo "  Missing links: $missing"
        missing_names=(${(f)"$(_vibe_skills_target_missing_names "$target")"})
        if (( ${#missing_names[@]} > 0 )); then
            echo "  缺失项: ${(j:, :)missing_names}"
        fi
        echo "  建议: ${CYAN}zsh scripts/init.sh${NC}"
    fi
    echo ""
    echo "${CYAN}Codex:${NC}"
    if command -v codex >/dev/null 2>&1; then
        echo "  CLI: 已安装"
        if _vibe_skills_codex_superpowers_installed; then
            echo "  Superpowers plugin: 已安装"
        else
            echo "  Superpowers plugin: 未安装"
            echo "  建议: ${CYAN}codex plugin marketplace add https://github.com/obra/superpowers.git && codex plugin add superpowers@superpowers-dev${NC}"
        fi
    else
        echo "  CLI: 未安装 codex"
    fi
    echo ""
    echo "${CYAN}全局共享 Skills (~/.agents/skills/，可选增强):${NC}"
    global_count="$(_vibe_skills_count_entries "$HOME/.agents/skills")"
    echo "  已安装: $global_count 个"
    echo ""
    echo "${CYAN}各 Agent 全局 Skills 镜像（非阻塞）:${NC}"
    agents=(${(f)"$(_vibe_skills_global_agents)"})
    for agent in "${agents[@]}"; do
        agent_dir="$(_vibe_skills_agent_dir "$agent")"
        if [[ "$agent" == "claude-code" ]]; then
            continue
        elif [[ "$agent" == "codex" ]]; then
            echo "  $agent: $global_count skills (共享 ~/.agents/skills，可选)"
        elif [[ -d "$agent_dir" ]]; then
            count="$(_vibe_skills_count_entries "$agent_dir")"
            echo "  $agent: $count/$global_count (可选)"
        else
            echo "  $agent: 未启用（目录不存在，跳过）"
        fi
    done
    echo ""
    echo "${CYAN}项目级 Skills 同步:${NC}"
    agents=(${(f)"$(_vibe_skills_project_agents)"})
    for target in ${(@f)"$(_vibe_skills_project_targets "${agents[@]}")"}; do
        IFS='|' read -r linked missing broken <<< "$(_vibe_skills_target_health "$target")"
        if [[ "$linked" == "skip" ]]; then
            echo "  ${target#$VIBE_ROOT/}: 未启用（目录不存在，跳过）"
            continue
        fi
        echo "  ${target#$VIBE_ROOT/}: $linked/$project_count"
        if (( missing > 0 )); then
            echo "    missing: $missing"
            missing_names=(${(f)"$(_vibe_skills_target_missing_names "$target")"})
            (( ${#missing_names[@]} > 0 )) && echo "    缺失项: ${(j:, :)missing_names}"
        fi
        (( broken > 0 )) && echo "    broken: $broken"
    done
    echo ""
    echo "修复建议:"
    echo "  - Claude / 项目级 skills 缺失：${CYAN}zsh scripts/init.sh${NC}"
    echo "  - 第三方能力优先使用各 agent plugin；npx skills 仅作为明确需要时的 legacy fallback"
    echo "  - 逻辑审计 / 推荐：${CYAN}/vibe-skills-manager${NC}"
    echo ""
    echo "结论:"
    echo "  - 只安装 Claude Code 也可以正常使用，本节其余项默认不阻塞"
    echo ""
}

_vibe_skills_run_audit() {
    local global_count project_count issues=0 linked target agent
    local -a agents project_agents
    echo ""
    echo "${BOLD}Skills 审计报告${NC}"
    echo "======================================"
    global_count="$(_vibe_skills_count_entries "$HOME/.agents/skills")"
    project_count="$(_vibe_skills_project_count)"
    agents=(${(f)"$(_vibe_skills_global_agents)"})
    project_agents=(${(f)"$(_vibe_skills_project_agents)"})
    echo ""
    echo "${CYAN}[1] Claude Code Plugin${NC}"
    if [[ -f "$HOME/.claude/plugins/installed_plugins.json" ]] && grep -q "superpowers@claude-plugins-official" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null; then
        echo "    OK superpowers plugin: 已安装"
    else
        echo "    X  superpowers plugin: 未安装"
        issues=$((issues + 1))
    fi
    echo ""
    echo "${CYAN}[1b] Codex Plugin${NC}"
    if _vibe_skills_codex_superpowers_installed; then
        echo "    OK superpowers plugin: 已安装"
    else
        echo "    X  superpowers plugin: 未安装"
        issues=$((issues + 1))
    fi
    echo ""
    echo "${CYAN}[2] 全局 Skills 覆盖${NC}"
    agents=(${(f)"$(_vibe_skills_global_agents | grep -Ev '^(codex|claude-code)$' || true)"})
    for agent in "${agents[@]}"; do
        linked="$global_count"
        [[ "$agent" == "codex" ]] || linked="$(_vibe_skills_count_entries "$(_vibe_skills_agent_dir "$agent")")"
        [[ "$linked" -ge 10 ]] && echo "    OK $agent: $linked skills" || {
            echo "    !  $agent: $linked skills (预期 >=10)"
            issues=$((issues + 1))
        }
    done
    echo ""
    echo "${CYAN}[3] 本地 vibe-* Symlink${NC}"
    for agent in "${project_agents[@]}"; do
        target="$(_vibe_skills_project_targets "$agent")"
        linked="$(_vibe_skills_count_entries "$target")"
        [[ "$linked" -eq "$project_count" ]] && echo "    OK $target: $linked/$project_count vibe-* skills" || {
            echo "    !  $target: $linked/$project_count vibe-* skills (不匹配)"
            issues=$((issues + 1))
        }
    done
    echo ""
    echo "======================================"
    (( issues == 0 )) && echo "${GREEN}审计通过，无问题${NC}" || echo "${YELLOW}发现 $issues 个问题，建议运行同步修复${NC}"
    echo ""
}

#!/usr/bin/env zsh
# scripts/sync-skills.sh - 一键同步 Skills 配置
# 用法: scripts/sync-skills.sh [--check]
# 配置源: skills/vibe-skills/registry.json

set -e

# ─── Colors ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log_step()    { echo "⏳ ${BOLD}$1${NC}"; }
log_success() { echo "✅ ${GREEN}$1${NC}"; }
log_info()    { echo "ℹ️  ${CYAN}$1${NC}"; }
log_warn()    { echo "⚠️  ${YELLOW}$1${NC}"; }
log_error()   { echo "❌ ${RED}$1${NC}" >&2; }

# ─── Config ───────────────────────────────────────────────
SKILLS_CONFIG="${HOME}/.vibe/skills.json"
REGISTRY_FILE="skills/vibe-skills/registry.json"

# ─── Registry 解析 ────────────────────────────────────────

# 检查 jq 是否可用
has_jq() {
    command -v jq &>/dev/null
}

# 从 registry.json 读取全局 agents 列表
get_global_agents() {
    if has_jq && [[ -f "$REGISTRY_FILE" ]]; then
        jq -r '.global._agents[]' "$REGISTRY_FILE" 2>/dev/null
    elif [[ -f "$REGISTRY_FILE" ]]; then
        grep -A 10 '"global"' "$REGISTRY_FILE" | grep '"_agents"' | \
            sed 's/.*"_agents": \[\(.*\)\].*/\1/' | tr -d '"' | tr ',' '\n' | tr -d ' '
    fi
}

# 从 registry.json 读取项目级 agents 列表
get_project_agents() {
    if has_jq && [[ -f "$REGISTRY_FILE" ]]; then
        jq -r '.project._agents[]' "$REGISTRY_FILE" 2>/dev/null
    elif [[ -f "$REGISTRY_FILE" ]]; then
        grep -A 10 '"project"' "$REGISTRY_FILE" | grep '"_agents"' | \
            sed 's/.*"_agents": \[\(.*\)\].*/\1/' | tr -d '"' | tr ',' '\n' | tr -d ' '
    fi
}

# 从 registry.json 读取 superpowers skills 列表
get_superpowers_skills() {
    if has_jq && [[ -f "$REGISTRY_FILE" ]]; then
        jq -r '.global.packages[] | select(.source == "obra/superpowers") | .skills[].name' "$REGISTRY_FILE" 2>/dev/null
    fi
}

# 获取 agent 的 skills 目录路径
get_agent_skills_dir() {
    local agent="$1"
    case "$agent" in
        antigravity) echo "$HOME/.gemini/antigravity/skills" ;;
        trae)        echo "$HOME/.trae/skills" ;;
        kiro)        echo "$HOME/.kiro/skills" ;;
        codex)       echo "$HOME/.agents/skills" ;;  # universal mode
        *)           echo "$HOME/.agents/skills/$agent" ;;
    esac
}

# 获取 agent 的 symlink 类型
get_agent_sync_type() {
    local agent="$1"
    case "$agent" in
        antigravity|trae|kiro) echo "symlinked" ;;
        codex)                 echo "universal" ;;
        *)                     echo "unknown" ;;
    esac
}

# ─── Functions ────────────────────────────────────────────

sync_claude_plugin() {
    log_step "检查 Claude Code superpowers plugin..."

    if [[ -f "$HOME/.claude/plugins/installed_plugins.json" ]]; then
        if grep -q "superpowers@claude-plugins-official" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null; then
            log_success "Claude Code superpowers plugin 已安装"
            return 0
        fi
    fi

    log_info "安装 Claude Code superpowers plugin..."
    echo "  运行: claude plugin add superpowers"
    if claude plugin add superpowers 2>/dev/null; then
        log_success "Claude Code superpowers plugin 安装成功"
    else
        log_warn "无法自动安装，请手动运行: claude plugin add superpowers"
    fi
}

sync_global_superpowers() {
    # 从 registry 读取 agents
    local agents=($(get_global_agents))
    local agents_str="${agents[*]}"
    log_step "同步全局 Superpowers skills ($agents_str)..."

    # 从 registry 读取 superpowers skills
    local skills=($(get_superpowers_skills))

    if [[ ${#skills[@]} -eq 0 ]]; then
        log_warn "无法从 registry.json 读取 superpowers skills，使用默认列表"
        skills=(
            "brainstorming" "systematic-debugging" "verification-before-completion"
            "writing-skills" "using-git-worktrees" "test-driven-development"
            "executing-plans" "writing-plans" "finishing-a-development-branch"
            "receiving-code-review" "requesting-code-review" "dispatching-parallel-agents"
            "subagent-driven-development" "using-superpowers"
        )
    fi

    # 构建 --skill 参数
    local skill_args=""
    for skill in "${skills[@]}"; do
        skill_args="$skill_args --skill $skill"
    done

    # 构建 --agent 参数（排除 codex，它使用 universal mode）
    local agent_args=""
    for agent in "${agents[@]}"; do
        if [[ "$agent" != "codex" ]]; then
            agent_args="$agent_args $agent"
        fi
    done

    # 安装到全局 + agents
    if [[ -n "$agent_args" ]]; then
        npx skills add obra/superpowers -g \
            --agent $agent_args \
            $skill_args -y 2>&1 | grep -E "(Installed|✓|already)" || true
    fi

    log_success "全局 Superpowers 已同步"

    # 同步到各 agent (symlink)
    sync_agents_symlinks "${agents[@]}"
}

sync_agents_symlinks() {
    local agents=("$@")
    log_step "同步全局 skills 到各 Agent..."

    # 全局 skills 目录中的所有 skills
    local global_skills_dir="$HOME/.agents/skills"

    for agent in "${agents[@]}"; do
        local sync_type=$(get_agent_sync_type "$agent")
        local agent_dir=$(get_agent_skills_dir "$agent")

        # codex 使用 universal mode，不需要 symlink
        if [[ "$sync_type" == "universal" ]]; then
            continue
        fi

        # 创建目录
        mkdir -p "$agent_dir"

        # 为全局 skills 创建 symlink
        for skill_dir in "$global_skills_dir"/*/; do
            [[ -d "$skill_dir" ]] || continue
            local skill_name=$(basename "$skill_dir")
            ln -sfn "../../../.agents/skills/$skill_name" "$agent_dir/$skill_name" 2>/dev/null || true
        done
    done

    log_success "各 Agent skills 已同步"
}

sync_local_skills() {
    # 从 registry 读取 project agents
    local agents=($(get_project_agents))
    log_step "同步本地 vibe-* skills (symlink)..."

    # 确定目标目录
    local targets=()
    for agent in "${agents[@]}"; do
        case "$agent" in
            antigravity)     targets+=(".agent/skills") ;;
            trae)            targets+=(".trae/skills") ;;
            claude-code)     targets+=(".claude/skills") ;;
            *)               targets+=(".$agent/skills") ;;
        esac
    done

    # 创建目标目录
    for target in "${targets[@]}"; do
        mkdir -p "$target"
    done

    # 链接 skills/vibe-*
    local count=0
    for skill_dir in skills/vibe-*/; do
        [ -d "$skill_dir" ] || continue
        name=$(basename "$skill_dir")

        for target in "${targets[@]}"; do
            ln -sfn "../../$skill_dir" "$target/$name" 2>/dev/null || true
        done
        count=$((count + 1))
    done

    log_success "已链接 $count 个本地 skills"
}

check_status() {
    echo ""
    echo "${BOLD}📊 Skills 状态检查${NC}"
    echo "─────────────────────────────────"

    # Claude Code plugin
    echo ""
    echo "${CYAN}Claude Code Plugin:${NC}"
    if grep -q "superpowers@claude-plugins-official" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null; then
        echo "  ✅ superpowers plugin 已安装"
    else
        echo "  ❌ superpowers plugin 未安装"
    fi

    # 全局 skills (从 ~/.agents/skills/ 读取)
    echo ""
    echo "${CYAN}全局 Skills (~/.agents/skills/):${NC}"
    local global_count=$(ls ~/.agents/skills/ 2>/dev/null | wc -l | tr -d ' ')
    echo "  已安装: $global_count 个"

    # 从 registry 读取并显示各 Agent 状态
    echo ""
    echo "${CYAN}各 Agent Skills 状态:${NC}"

    local agents=($(get_global_agents))
    for agent in "${agents[@]}"; do
        local sync_type=$(get_agent_sync_type "$agent")
        local agent_dir=$(get_agent_skills_dir "$agent")
        local count=0

        if [[ "$sync_type" == "universal" ]]; then
            count=$global_count
            echo "  $agent: $count skills (universal mode)"
        elif [[ -d "$agent_dir" ]]; then
            count=$(ls "$agent_dir" 2>/dev/null | wc -l | tr -d ' ')
            echo "  $agent: $count skills ($sync_type)"
        else
            echo "  $agent: 目录不存在 ($agent_dir)"
        fi
    done

    # 本地 skills
    echo ""
    echo "${CYAN}本地 vibe-* skills:${NC}"
    local project_count=$(ls skills/ 2>/dev/null | grep "^vibe-" | wc -l | tr -d ' ')
    echo "  项目级: $project_count 个"

    local linked=$(ls .agent/skills/ 2>/dev/null | grep "^vibe-" | wc -l | tr -d ' ')
    echo "  已链接: $linked 个"

    echo ""
}

run_audit() {
    echo ""
    echo "${BOLD}🔍 Skills 审计报告${NC}"
    echo "═══════════════════════════════════════════════════"

    local issues=0

    # 1. 检查 Claude Code plugin
    echo ""
    echo "${CYAN}[1] Claude Code Plugin${NC}"
    if grep -q "superpowers@claude-plugins-official" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null; then
        echo "    ✅ superpowers plugin: 已安装"
    else
        echo "    ❌ superpowers plugin: 未安装"
        echo "       → 运行: claude plugin add superpowers"
        issues=$((issues + 1))
    fi

    # 2. 检查各 Agent
    echo ""
    echo "${CYAN}[2] 全局 Skills 覆盖${NC}"

    local global_count=$(ls ~/.agents/skills/ 2>/dev/null | wc -l | tr -d ' ')
    local agents=($(get_global_agents))

    for agent in "${agents[@]}"; do
        local sync_type=$(get_agent_sync_type "$agent")
        local agent_dir=$(get_agent_skills_dir "$agent")
        local count=0

        if [[ "$sync_type" == "universal" ]]; then
            count=$global_count
        elif [[ -d "$agent_dir" ]]; then
            count=$(ls "$agent_dir" 2>/dev/null | wc -l | tr -d ' ')
        fi

        if [[ "$count" -ge 10 ]]; then
            echo "    ✅ $agent: $count skills ($sync_type)"
        else
            echo "    ⚠️  $agent: $count skills (预期 ≥10)"
            issues=$((issues + 1))
        fi
    done

    # 3. 检查本地 skills symlink
    echo ""
    echo "${CYAN}[3] 本地 vibe-* Symlink${NC}"
    local project_count=$(ls skills/ 2>/dev/null | grep "^vibe-" | wc -l | tr -d ' ')

    local project_agents=($(get_project_agents))
    for agent in "${project_agents[@]}"; do
        local target=""
        case "$agent" in
            antigravity)     target=".agent/skills" ;;
            trae)            target=".trae/skills" ;;
            claude-code)     target=".claude/skills" ;;
            *)               target=".$agent/skills" ;;
        esac

        if [[ -d "$target" ]]; then
            local linked=$(ls "$target" 2>/dev/null | grep "^vibe-" | wc -l | tr -d ' ')
            if [[ "$linked" -eq "$project_count" ]]; then
                echo "    ✅ $target: $linked/$project_count vibe-* skills"
            else
                echo "    ⚠️  $target: $linked/$project_count vibe-* skills (不匹配)"
                issues=$((issues + 1))
            fi
        else
            echo "    ❌ $target: 目录不存在"
            issues=$((issues + 1))
        fi
    done

    # 4. 检查 skills.json 配置
    echo ""
    echo "${CYAN}[4] skills.json 配置${NC}"
    if [[ -f "$SKILLS_CONFIG" ]]; then
        echo "    ✅ 配置文件存在: $SKILLS_CONFIG"
    else
        echo "    ⚠️  配置文件不存在: $SKILLS_CONFIG"
    fi

    # 总结
    echo ""
    echo "═══════════════════════════════════════════════════"
    if [[ "$issues" -eq 0 ]]; then
        echo "${GREEN}✅ 审计通过，无问题${NC}"
    else
        echo "${YELLOW}⚠️  发现 $issues 个问题，建议运行同步修复${NC}"
        echo "    → 运行: vibe skills sync"
    fi
    echo ""
}

show_usage() {
    echo ""
    echo "用法: scripts/sync-skills.sh [选项]"
    echo ""
    echo "选项:"
    echo "  (无参数)    完整同步所有 skills + 审计"
    echo "  --check     仅检查状态，不执行同步"
    echo "  --help      显示帮助"
    echo ""
    echo "💡 完整交互式审计请使用对话命令: /vibe-skills"
    echo ""
    echo "配置源: skills/vibe-skills/registry.json"
    echo ""
}

# ─── Main ─────────────────────────────────────────────────
echo ""
echo "🔄 Vibe Skills 同步工具"
echo ""

case "${1:-}" in
    --check)
        check_status
        ;;
    --help|-h)
        show_usage
        ;;
    *)
        # 完整同步
        sync_claude_plugin
        sync_global_superpowers
        sync_local_skills
        echo ""
        run_audit
        log_success "同步完成！"
        ;;
esac

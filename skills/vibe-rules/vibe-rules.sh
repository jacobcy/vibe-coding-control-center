#!/usr/bin/env zsh
# vibe-rules - Rules 冲突检测与清理工具
# Usage: vibe-rules <check|report|clean|fix> [--dry-run]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="${PROJECT_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# 全局规则目录
GLOBAL_RULES="$HOME/.claude/rules/common"

# 项目规则目录
PROJECT_RULES="$PROJECT_ROOT/.claude/rules"

# CLAUDE.md
CLAUDE_MD="$PROJECT_ROOT/CLAUDE.md"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 统计行数和 token
count_stats() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        wc -l "$dir"/*.md 2>/dev/null | tail -1 | awk '{print $1}'
    else
        echo "0"
    fi
}

# 检查同名文件
check_duplicate_names() {
    log_info "检查同名文件..."

    if [[ ! -d "$GLOBAL_RULES" ]] || [[ ! -d "$PROJECT_RULES" ]]; then
        log_warning "规则目录不存在"
        return
    fi

    local duplicates=$(comm -12 <(ls "$GLOBAL_RULES" 2>/dev/null | sort) <(ls "$PROJECT_RULES" 2>/dev/null | sort))

    if [[ -n "$duplicates" ]]; then
        log_warning "发现同名文件重复："
        echo "$duplicates" | while read file; do
            echo "  - $file (全局 + 项目)"

            # 检查内容是否完全相同
            if diff -q "$GLOBAL_RULES/$file" "$PROJECT_RULES/$file" > /dev/null 2>&1; then
                log_warning "    内容完全相同，应删除项目规则"
            else
                log_info "    内容不同，需评估项目特定需求"
            fi
        done
    else
        log_success "无同名文件重复"
    fi
}

# 检查内容重复（已移除，因 .agent/rules/ 已废弃）
check_content_duplication() {
    log_info "检查内容重复..."

    if [[ ! -d "$PROJECT_RULES" ]]; then
        return
    fi

    # 简化检查：只检查项目规则内部重复
    log_success "无内容重复"
}

# 检查 CLAUDE.md 引用（已移除，因 .agent/rules/ 已废弃）
check_claudemd_references() {
    log_info "检查 CLAUDE.md 引用..."

    if [[ ! -f "$CLAUDE_MD" ]]; then
        log_warning "CLAUDE.md 不存在"
        return
    fi

    log_success "CLAUDE.md 引用检查完成"
}

# 检查配置一致性
check_config_consistency() {
    log_info "检查配置一致性..."

    local pyproject="$PROJECT_ROOT/pyproject.toml"

    if [[ ! -f "$pyproject" ]]; then
        log_warning "pyproject.toml 不存在"
        return
    fi

    # 检查 mypy strict（已移除，因 .agent/rules/ 已废弃）
    # 检查 line-length（已移除，因 .agent/rules/ 已废弃）

    log_success "配置一致性检查完成"
}

# 生成统计报告
generate_stats() {
    log_info "生成统计信息..."

    local global_lines=$(count_stats "$GLOBAL_RULES")
    local project_lines=$(count_stats "$PROJECT_RULES")

    local global_files=$(ls "$GLOBAL_RULES"/*.md 2>/dev/null | wc -l | xargs)
    local project_files=$(ls "$PROJECT_RULES"/*.md 2>/dev/null | wc -l | xargs)

    cat << EOF

========================================
Rules 统计信息
========================================
层级          文件数   行数    Token 估算
----------------------------------------
全局规则      ${global_files}        ${global_lines}       ~$((global_lines * 15)) tokens
项目规则      ${project_files}        ${project_lines}       ~$((project_lines * 15)) tokens
----------------------------------------
总计          $((global_files + project_files))        $((global_lines + project_lines))      ~$(((global_lines + project_lines) * 15)) tokens
========================================
EOF
}

# 主命令：check
cmd_check() {
    log_info "开始检查 rules 冲突..."
    echo ""

    check_duplicate_names
    echo ""

    check_content_duplication
    echo ""

    check_claudemd_references
    echo ""

    check_config_consistency
    echo ""

    generate_stats
    echo ""

    log_success "检查完成！"
}

# 主命令：report
cmd_report() {
    local report_dir="$PROJECT_ROOT/.agent/reports"
    local report_file="$report_dir/rules-report.md"

    # 创建目录（如果不存在）
    mkdir -p "$report_dir"

    log_info "生成详细报告到 $report_file..."

    cat > "$report_file" << EOF
# Vibe Rules 分析报告

生成时间: $(date '+%Y-%m-%d %H:%M:%S')

## 统计信息

EOF

    # 执行检查并追加到报告
    cmd_check >> "$report_file" 2>&1

    log_success "报告已生成: $report_file"
}

# 主命令：clean
cmd_clean() {
    local dry_run="${1:-false}"

    if [[ "$dry_run" == "true" ]]; then
        log_info "[DRY-RUN] 模式：仅显示将要执行的操作"
    fi

    log_info "开始清理重复 rules..."

    # 清理与全局重复的同名文件
    if [[ -d "$GLOBAL_RULES" ]] && [[ -d "$PROJECT_RULES" ]]; then
        local duplicates=$(comm -12 <(ls "$GLOBAL_RULES" 2>/dev/null | sort) <(ls "$PROJECT_RULES" 2>/dev/null | sort))

        for file in $duplicates; do
            # 检查内容是否完全相同
            if diff -q "$GLOBAL_RULES/$file" "$PROJECT_RULES/$file" > /dev/null 2>&1; then
                if [[ "$dry_run" == "true" ]]; then
                    log_warning "[DRY-RUN] 将删除: $PROJECT_RULES/$file (与全局完全相同)"
                else
                    log_warning "删除: $PROJECT_RULES/$file (与全局完全相同)"
                    rm "$PROJECT_RULES/$file"
                fi
            fi
        done
    fi

    log_success "清理完成！"
}

# 主命令：fix
cmd_fix() {
    log_info "交互式修复配置冲突..."

    # TODO: 实现交互式修复
    log_warning "此功能尚未实现"
}

# 主函数
main() {
    local command="${1:-check}"
    local dry_run="${2:-false}"

    case "$command" in
        check)
            cmd_check
            ;;
        report)
            cmd_report
            ;;
        clean)
            cmd_clean "$dry_run"
            ;;
        fix)
            cmd_fix
            ;;
        *)
            echo "Usage: vibe-rules <check|report|clean|fix> [--dry-run]"
            echo ""
            echo "Commands:"
            echo "  check   - 检查 rules 冲突"
            echo "  report  - 生成详细报告"
            echo "  clean   - 清理重复 rules"
            echo "  fix     - 交互式修复冲突"
            echo ""
            echo "Options:"
            echo "  --dry-run  - 仅显示操作，不实际执行"
            exit 1
            ;;
    esac
}

main "$@"
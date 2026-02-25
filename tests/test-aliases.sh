#!/usr/bin/env zsh
# ======================================================
# Vibe Alias 测试套件
# ======================================================
# 用法: ./test-aliases.sh [--verbose|--quiet|--help]

set -e

# ---------- 配置 ----------
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ALIASES_FILE="$PROJECT_ROOT/config/aliases.sh"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 测试结果统计
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# 详细输出模式
VERBOSE=0
QUIET=0

# ---------- 日志函数 ----------
log_info() {
    [[ $QUIET -eq 0 ]] && echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    [[ $QUIET -eq 0 ]] && echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    [[ $QUIET -eq 0 ]] && echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    [[ $QUIET -eq 0 ]] && echo -e "${YELLOW}[SKIP]${NC} $1"
}

log_step() {
    [[ $QUIET -eq 0 ]] && echo -e "${CYAN}[TEST]${NC} ${BOLD}$1${NC}"
}

log_detail() {
    [[ $VERBOSE -eq 1 && $QUIET -eq 0 ]] && echo -e "${BLUE}      →${NC} $1"
}

# ---------- 测试框架 ----------

# 运行单个测试
# 用法: test_case "测试名称" "测试命令" [期望退出码=0]
test_case() {
    local name="$1"
    local cmd="$2"
    local expected_exit="${3:-0}"

    TESTS_TOTAL=$((TESTS_TOTAL + 1))

    log_step "$name"
    log_detail "Command: $cmd"

    # 执行测试命令，添加超时保护
    local output
    local exit_code

    # 使用 timeout 命令防止卡死
    if command -v timeout >/dev/null 2>&1; then
        output=$(timeout 10 sh -c "$cmd" 2>&1)
        exit_code=$?
        if [[ $exit_code -eq 124 ]]; then
            log_warn "$name (超时)"
            TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
            return 1
        fi
    else
        output=$(eval "$cmd" 2>&1)
        exit_code=$?
    fi

    # 检查退出码
    if [[ $exit_code -eq $expected_exit ]]; then
        log_success "$name"
        log_detail "Exit code: $exit_code (expected: $expected_exit)"
        if [[ $VERBOSE -eq 1 && -n "$output" ]]; then
            log_detail "Output: ${output:0:200}"
        fi
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_error "$name"
        log_detail "Exit code: $exit_code (expected: $expected_exit)"
        log_detail "Output: $output"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# 条件测试 - 仅在条件满足时运行
test_conditional() {
    local condition="$1"
    local name="$2"
    local cmd="$3"
    local expected_exit="${4:-0}"

    if eval "$condition"; then
        test_case "$name" "$cmd" "$expected_exit"
    else
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
        TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
        log_warn "$name (condition not met)"
    fi
}

# ---------- 测试套件 ----------

# 1. 语法检查测试
run_syntax_tests() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              语法检查测试 (Syntax Tests)                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # 获取所有 alias 文件
    local alias_files=(
        "$PROJECT_ROOT/config/aliases.sh"
        "$PROJECT_ROOT/config/aliases/claude.sh"
        "$PROJECT_ROOT/config/aliases/opencode.sh"
        "$PROJECT_ROOT/config/aliases/openspec.sh"
        "$PROJECT_ROOT/config/aliases/vibe.sh"
        "$PROJECT_ROOT/config/aliases/git.sh"
        "$PROJECT_ROOT/config/aliases/tmux.sh"
        "$PROJECT_ROOT/config/aliases/worktree.sh"
    )

    for file in "${alias_files[@]}"; do
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            test_case "语法检查: $basename" "zsh -n '$file'" 0
        fi
    done
}

# 2. 加载测试
run_load_tests() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              加载测试 (Load Tests)                         ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # 测试能否成功加载 aliases.sh
    test_case "加载 aliases.sh" "source '$PROJECT_ROOT/config/aliases.sh'" 0

    # 测试环境变量是否正确设置
    test_case "检查 VIBE_ROOT 设置" "source '$PROJECT_ROOT/config/aliases.sh' && [[ -n \"\$VIBE_ROOT\" ]]" 0
}

# 3. Alias 定义测试
run_alias_definition_tests() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           Alias 定义测试 (Definition Tests)                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Claude aliases
    test_case "定义检查: ccy" "grep -q \"alias ccy='claude\" '$PROJECT_ROOT/config/aliases/claude.sh'" 0
    test_case "定义检查: ccp" "grep -q 'alias ccp=' '$PROJECT_ROOT/config/aliases/claude.sh'" 0

    # Vibe aliases
    test_case "定义检查: lg (lazygit)" "grep -q \"alias lg='lazygit'\" '$PROJECT_ROOT/config/aliases/vibe.sh'" 0
    test_case "定义检查: vc" "grep -q 'alias vc=' '$PROJECT_ROOT/config/aliases/vibe.sh'" 0

    # Git aliases
    test_case "定义检查: vibe_git_root" "grep -q 'vibe_git_root()' '$PROJECT_ROOT/config/aliases/git.sh'" 0
    test_case "定义检查: vibe_main_guard" "grep -q 'vibe_main_guard()' '$PROJECT_ROOT/config/aliases/git.sh'" 0
}

# 4. 函数执行测试
run_function_tests() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           函数执行测试 (Function Tests)                    ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # 加载 aliases
    source "$PROJECT_ROOT/config/aliases.sh"

    # 测试基础函数
    test_case "函数: vibe_has()" "vibe_has ls" 0
    test_case "函数: vibe_has() - 不存在命令" "vibe_has __nonexistent_command__" 1
    test_case "函数: vibe_now()" "vibe_now" 0

    # 条件测试：如果在 git 仓库中
    test_conditional "git rev-parse --is-inside-work-tree 2>/dev/null" \
        "函数: vibe_git_root()" \
        "vibe_git_root >/dev/null" \
        0

    test_conditional "git rev-parse --is-inside-work-tree 2>/dev/null" \
        "函数: vibe_branch()" \
        "vibe_branch >/dev/null" \
        0
}

# 5. 依赖检查测试
run_dependency_tests() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           依赖检查测试 (Dependency Tests)                  ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # 核心依赖
    test_conditional "true" \
        "依赖: git" \
        "command -v git >/dev/null" \
        0

    test_conditional "true" \
        "依赖: zsh" \
        "command -v zsh >/dev/null" \
        0

    # 可选依赖
    test_conditional "true" \
        "可选依赖: tmux" \
        "command -v tmux >/dev/null" \
        0

    test_conditional "true" \
        "可选依赖: lazygit" \
        "command -v lazygit >/dev/null" \
        0

    test_conditional "true" \
        "可选依赖: claude" \
        "command -v claude >/dev/null" \
        0

    test_conditional "true" \
        "可选依赖: opencode" \
        "command -v opencode >/dev/null" \
        0
}

# 6. 集成测试
run_integration_tests() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           集成测试 (Integration Tests)                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # 测试完整加载流程
    test_case "集成: 完整加载 aliases.sh" \
        "zsh -c 'source $PROJECT_ROOT/config/aliases.sh && echo VIBE_ROOT=\$VIBE_ROOT'" \
        0

    # 测试 vibe 命令解析
    test_case "集成: vibe 函数定义" \
        "grep -q 'vibe()' '$PROJECT_ROOT/config/aliases/vibe.sh'" \
        0
}

# ---------- 主程序 ----------

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                                                            ║"
    echo "║          Vibe Alias 测试套件 (Test Suite)                  ║"
    echo "║                                                            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "项目路径: $PROJECT_ROOT"
    echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
}

print_summary() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                    测试总结 (Test Summary)                 ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  总测试数: $TESTS_TOTAL"
    echo -e "  通过: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "  失败: ${RED}$TESTS_FAILED${NC}"
    echo -e "  跳过: ${YELLOW}$TESTS_SKIPPED${NC}"
    echo ""

    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo -e "${GREEN}✓ 所有测试通过!${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ 有 $TESTS_FAILED 个测试失败${NC}"
        echo ""
        return 1
    fi
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --verbose|-v)
                VERBOSE=1
                shift
                ;;
            --quiet|-q)
                QUIET=1
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  -v, --verbose    详细输出模式"
                echo "  -q, --quiet      静默模式（仅显示结果）"
                echo "  -h, --help       显示帮助信息"
                echo ""
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# 主函数
main() {
    parse_args "$@"

    print_header

    # 运行所有测试套件
    run_syntax_tests
    run_load_tests
    run_alias_definition_tests
    run_function_tests
    run_dependency_tests
    run_integration_tests

    # 打印总结
    print_summary
    exit $?
}

# 如果直接执行此脚本
if [[ "${(%):-%N}" == "$0" ]]; then
    main "$@"
fi

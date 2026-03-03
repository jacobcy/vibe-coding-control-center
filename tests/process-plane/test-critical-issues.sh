#!/usr/bin/env bash
# 关键能力补充测试 - 覆盖审查中指出的缺陷

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
V3_DIR="$PROJECT_ROOT/v3/process-plane"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

pass() {
  echo -e "${GREEN}✓ PASS${NC}: $1"
  ((PASS_COUNT++))
}

fail() {
  echo -e "${RED}✗ FAIL${NC}: $1"
  if [[ -n "$2" ]]; then
    echo "  Error: $2"
  fi
  ((FAIL_COUNT++))
}

warn() {
  echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

echo "=== 关键能力补充测试 ==="
echo ""

# 测试 1: Zsh 兼容性（如果 zsh 可用）
test_zsh_compatibility() {
  echo "--- Test 1: Zsh 兼容性 ---"

  if ! command -v zsh &>/dev/null; then
    warn "zsh not available, skipping zsh compatibility test"
    return
  fi

  # 在 zsh 下加载 router.sh，检查 SCRIPT_DIR 是否正确
  local test_result
  test_result=$(zsh -c "
    source '$V3_DIR/router.sh' 2>&1
    if [[ -n \"\${SCRIPT_DIR:-}\" ]]; then
      echo \"SCRIPT_DIR=\$SCRIPT_DIR\"
    else
      echo \"ERROR: SCRIPT_DIR not set\"
    fi
  " 2>&1)

  if echo "$test_result" | grep -q "ERROR"; then
    fail "Zsh SCRIPT_DIR 解析失败" "$test_result"
  elif echo "$test_result" | grep -q "SCRIPT_DIR="; then
    local script_dir
    script_dir=$(echo "$test_result" | grep "SCRIPT_DIR=" | cut -d'=' -f2)

    # 验证 SCRIPT_DIR 是否指向正确的目录
    if [[ "$script_dir" == *"/v3/process-plane" ]]; then
      pass "Zsh SCRIPT_DIR 正确解析: $script_dir"
    else
      fail "Zsh SCRIPT_DIR 路径错误" "Expected */v3/process-plane, got $script_dir"
    fi
  else
    fail "Zsh 加载失败" "$test_result"
  fi
}

# 测试 2: Fallback 历史记录唯一性
test_fallback_history_uniqueness() {
  echo ""
  echo "--- Test 2: Fallback 历史记录唯一性 ---"

  # 清理旧历史
  FALLBACK_HISTORY_DIR="/tmp/vibe-fallback-history-test-$$"
  rm -rf "$FALLBACK_HISTORY_DIR"
  mkdir -p "$FALLBACK_HISTORY_DIR"

  # 在隔离环境中测试
  (
    export FALLBACK_HISTORY_DIR
    source "$V3_DIR/fallback.sh" 2>/dev/null

    # 快速连续记录三次降级
    pp_fallback_record "supervisor" "openspec" "test1" "task-001"
    sleep 0.01
    pp_fallback_record "openspec" "kiro" "test2" "task-001"
    sleep 0.01
    pp_fallback_record "kiro" "manual" "test3" "task-001"
  )

  # 检查是否生成了三个不同的文件
  local file_count
  file_count=$(find "$FALLBACK_HISTORY_DIR" -name "*.json" | wc -l | tr -d ' ')

  if [[ "$file_count" -eq 3 ]]; then
    pass "生成了 3 个唯一的历史文件"

    # 验证文件内容是否正确
    local all_valid=true
    for file in "$FALLBACK_HISTORY_DIR"/*.json; do
      if ! jq -e . "$file" >/dev/null 2>&1; then
        all_valid=false
        fail "无效的 JSON 文件: $file"
      fi
    done

    if $all_valid; then
      pass "所有历史文件都是有效的 JSON"
    fi
  else
    fail "历史文件数量错误" "Expected 3, got $file_count"
  fi

  # 清理
  rm -rf "$FALLBACK_HISTORY_DIR"
}

# 测试 3: Fallback Attempt 限制逻辑
test_fallback_attempt_limit() {
  echo ""
  echo "--- Test 3: Fallback Attempt 限制逻辑 ---"

  # 清理并设置隔离环境
  FALLBACK_HISTORY_DIR="/tmp/vibe-fallback-attempt-test-$$"
  rm -rf "$FALLBACK_HISTORY_DIR"
  mkdir -p "$FALLBACK_HISTORY_DIR"

  # 在 subshell 中测试
  local result
  result=$(
    export FALLBACK_HISTORY_DIR
    source "$V3_DIR/fallback.sh" 2>/dev/null

    # 记录 3 次降级，使用同一个 task_id
    pp_fallback_record "supervisor" "openspec" "test" "task-123"
    sleep 0.01
    pp_fallback_record "openspec" "kiro" "test" "task-123"
    sleep 0.01
    pp_fallback_record "kiro" "manual" "test" "task-123"

    # 检查是否达到上限
    pp_fallback_limit_attempts "task-123" 3
  )

  if [[ "$result" == "true" ]]; then
    pass "Fallback attempt limit 正确检测到上限"
  else
    fail "Fallback attempt limit 未检测到上限" "Result: $result"
  fi

  # 清理
  rm -rf "$FALLBACK_HISTORY_DIR"
}

# 测试 4: Strategy 自定义能力状态
test_strategy_custom_capability_status() {
  echo ""
  echo "--- Test 4: Strategy 自定义能力状态 ---"

  # 测试 pp_strategy_add_rule
  local add_rule_result add_rule_exit
  add_rule_result=$(source "$V3_DIR/strategy.sh" 2>/dev/null && pp_strategy_add_rule 2>&1)
  add_rule_exit=$?

  # 测试 pp_strategy_set_priority
  local set_priority_result set_priority_exit
  set_priority_result=$(source "$V3_DIR/strategy.sh" 2>/dev/null && pp_strategy_set_priority 2>&1)
  set_priority_exit=$?

  # 应该返回 2（未实现）而不是 1（错误）
  if [[ $add_rule_exit -eq 2 ]]; then
    pass "pp_strategy_add_rule 正确标记为未实现 (exit code: 2)"
  else
    fail "pp_strategy_add_rule 返回码错误" "Expected 2, got $add_rule_exit"
  fi

  if [[ $set_priority_exit -eq 2 ]]; then
    pass "pp_strategy_set_priority 正确标记为未实现 (exit code: 2)"
  else
    fail "pp_strategy_set_priority 返回码错误" "Expected 2, got $set_priority_exit"
  fi
}

# 测试 5: Adapter 校验增强
test_adapter_validation_enhanced() {
  echo ""
  echo "--- Test 5: Adapter 校验增强 ---"

  # 测试有效 adapter
  local manual_valid
  manual_valid=$(source "$V3_DIR/adapter-loader.sh" 2>/dev/null && pp_adapter_validate "manual" 2>/dev/null && echo "VALID" || echo "INVALID")

  # 测试无效 adapter（不存在的）
  local nonexistent_valid
  nonexistent_valid=$(source "$V3_DIR/adapter-loader.sh" 2>/dev/null && pp_adapter_validate "nonexistent" 2>/dev/null && echo "VALID" || echo "INVALID")

  if [[ "$manual_valid" == "VALID" ]]; then
    pass "有效 adapter (manual) 通过校验"
  else
    fail "有效 adapter (manual) 校验失败"
  fi

  if [[ "$nonexistent_valid" == "INVALID" ]]; then
    pass "无效 adapter (nonexistent) 被正确拒绝"
  else
    fail "无效 adapter (nonexistent) 未被拒绝"
  fi
}

# 运行所有测试
test_zsh_compatibility
test_fallback_history_uniqueness
test_fallback_attempt_limit
test_strategy_custom_capability_status
test_adapter_validation_enhanced

# 输出总结
echo ""
echo "=== 测试总结 ==="
echo -e "${GREEN}通过: $PASS_COUNT${NC}"
echo -e "${RED}失败: $FAIL_COUNT${NC}"

if [[ $FAIL_COUNT -eq 0 ]]; then
  echo -e "${GREEN}所有关键能力测试通过！${NC}"
  exit 0
else
  echo -e "${RED}存在失败的测试${NC}"
  exit 1
fi

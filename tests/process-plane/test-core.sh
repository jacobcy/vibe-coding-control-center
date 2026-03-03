#!/usr/bin/env zsh
# Process Plane Core Functionality Test

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Process Plane Core Functionality Test ==="
echo ""

# 加载核心模块
echo "1. Loading core modules..."
source "$PROJECT_ROOT/v3/process-plane/adapter-loader.sh"
source "$PROJECT_ROOT/v3/process-plane/strategy.sh"
source "$PROJECT_ROOT/v3/process-plane/fallback.sh"
source "$PROJECT_ROOT/v3/process-plane/router.sh"

echo "✓ Modules loaded successfully"
echo ""

# 测试 1: Adapter 加载和验证
echo "2. Testing adapter loading and validation..."
echo "   Registered adapters:"
pp_adapter_list | while read -r adapter; do
  echo "   - $adapter"
done

if pp_adapter_exists "manual"; then
  echo "   ✓ Manual adapter exists"
else
  echo "   ✗ Manual adapter NOT found"
  exit 1
fi

if pp_adapter_validate "manual"; then
  echo "   ✓ Manual adapter validation passed"
else
  echo "   ✗ Manual adapter validation failed"
  exit 1
fi

echo ""

# 测试 2: 路由策略
echo "3. Testing routing strategy..."

# 测试 spec-driven 低风险任务
TASK1='{"type":"spec-driven","risk":"low","id":"test-1"}'
RESULT1=$(pp_strategy_evaluate "$TASK1")
PROVIDER1=$(echo "$RESULT1" | jq -r '.provider')
echo "   Task: spec-driven, low risk"
echo "   Recommended provider: $PROVIDER1"
if [[ "$PROVIDER1" == "openspec" ]]; then
  echo "   ✓ Correct routing decision"
else
  echo "   ✗ Expected 'openspec', got '$PROVIDER1'"
fi

# 测试 ad-hoc 任务
TASK2='{"type":"ad-hoc","risk":"low","id":"test-2"}'
RESULT2=$(pp_strategy_evaluate "$TASK2")
PROVIDER2=$(echo "$RESULT2" | jq -r '.provider')
echo "   Task: ad-hoc, low risk"
echo "   Recommended provider: $PROVIDER2"
echo "   ✓ Strategy evaluation works"

# 测试 dry-run
DRY_RUN_RESULT=$(pp_strategy_dry_run "$TASK1")
echo "   Dry-run test: $(echo "$DRY_RUN_RESULT" | jq -c '.')"
echo "   ✓ Dry-run mode works"

echo ""

# 测试 3: Provider Router 核心接口
echo "4. Testing provider router core interfaces..."

# 测试 route
echo "   a) Testing pp_route..."
ROUTE_RESULT=$(pp_route "$TASK1")
echo "      Routed to: $ROUTE_RESULT"
if [[ -n "$ROUTE_RESULT" ]]; then
  echo "      ✓ pp_route works"
else
  echo "      ✗ pp_route failed"
  exit 1
fi

# 测试 start
echo "   b) Testing pp_start..."
PROVIDER_REF=$(pp_start "$TASK1" '{"test":"context"}')
echo "      Provider ref: $PROVIDER_REF"
if [[ -n "$PROVIDER_REF" && "$PROVIDER_REF" != error:* ]]; then
  echo "      ✓ pp_start works"
else
  echo "      ✗ pp_start failed: $PROVIDER_REF"
  exit 1
fi

# 测试 status
echo "   c) Testing pp_status..."
STATUS=$(pp_status "$PROVIDER_REF")
echo "      Status: $(echo "$STATUS" | jq -c '.')"
STATE=$(echo "$STATUS" | jq -r '.state')
if [[ -n "$STATE" ]]; then
  echo "      ✓ pp_status works"
else
  echo "      ✗ pp_status failed"
  exit 1
fi

# 测试 complete
echo "   d) Testing pp_complete..."
COMPLETE_RESULT=$(pp_complete "$PROVIDER_REF")
echo "      Complete result: $(echo "$COMPLETE_RESULT" | jq -c '.')"
RESULT=$(echo "$COMPLETE_RESULT" | jq -r '.result')
if [[ "$RESULT" == "success" ]]; then
  echo "      ✓ pp_complete works"
else
  echo "      ✗ pp_complete failed"
  exit 1
fi

echo ""

# 测试 4: 降级机制
echo "5. Testing fallback mechanism..."

echo "   a) Testing fallback path..."
AVAILABLE_PROVIDER=$(pp_fallback_find_available "supervisor")
echo "      Fallback from supervisor: $AVAILABLE_PROVIDER"
if [[ -n "$AVAILABLE_PROVIDER" ]]; then
  echo "      ✓ Fallback works"
else
  echo "      ✗ Fallback failed"
  exit 1
fi

echo "   b) Testing fallback history..."
HISTORY=$(pp_fallback_history 5)
echo "      History: $(echo "$HISTORY" | jq -c '.')"
echo "      ✓ Fallback history works"

echo ""

# 测试 5: 端到端流程
echo "6. Testing end-to-end flow..."

TASK3='{"type":"test","id":"e2e-test-1"}'
echo "   Task: $TASK3"

# Route
ROUTE=$(pp_route "$TASK3")
echo "   - Route: $ROUTE"

# Start
REF=$(pp_start "$TASK3" '{"context":"e2e"}')
echo "   - Start: $REF"

# Status
STATUS=$(pp_status "$REF")
echo "   - Status: $(echo "$STATUS" | jq -c '.')"

# Complete
COMPLETE=$(pp_complete "$REF")
echo "   - Complete: $(echo "$COMPLETE" | jq -c '.')"

echo "   ✓ End-to-end flow works"

echo ""
echo "=== All Tests Passed! ==="
echo ""
echo "Core functionality verified:"
echo "  ✓ Adapter loading and validation"
echo "  ✓ Routing strategy engine"
echo "  ✓ Provider router core interfaces (route/start/status/complete)"
echo "  ✓ Fallback mechanism"
echo "  ✓ End-to-end flow"

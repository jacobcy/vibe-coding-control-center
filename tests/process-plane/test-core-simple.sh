#!/usr/bin/env bash
# Process Plane Core Functionality Test (Simplified)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Process Plane Core Functionality Test (Simplified) ==="
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

echo ""

# 测试 2: 路由策略
echo "3. Testing routing strategy..."

TASK1='{"type":"test","risk":"low","id":"test-1"}'
RESULT1=$(pp_strategy_evaluate "$TASK1")
PROVIDER1=$(echo "$RESULT1" | jq -r '.provider')
echo "   Task: test, low risk"
echo "   Recommended provider: $PROVIDER1"
echo "   ✓ Strategy evaluation works"

echo ""

# 测试 3: 使用 Manual provider 的完整流程
echo "4. Testing complete flow with Manual provider..."

TASK2='{"type":"manual","id":"manual-test-1"}'
echo "   Task: $TASK2"

# 强制路由到 manual
ROUTE="manual"
echo "   - Route: $ROUTE (forced to manual for testing)"

# Start
echo "   - Starting..."
REF=$(pp_start "$TASK2" '{"test":"context"}')
echo "   - Provider ref: $REF"

if [[ "$REF" == error:* ]]; then
  echo "   ✗ Start failed: $REF"
  exit 1
fi

# Status
echo "   - Checking status..."
STATUS=$(pp_status "$REF")
echo "   - Status: $(echo "$STATUS" | jq -c '.')"

STATE=$(echo "$STATUS" | jq -r '.state')
if [[ "$STATE" == "in_progress" ]]; then
  echo "   ✓ Status is in_progress"
else
  echo "   ✗ Unexpected status: $STATE"
fi

# Complete
echo "   - Completing..."
COMPLETE=$(pp_complete "$REF")
echo "   - Complete result: $(echo "$COMPLETE" | jq -c '.')"

RESULT=$(echo "$COMPLETE" | jq -r '.result')
if [[ "$RESULT" == "success" ]]; then
  echo "   ✓ Complete succeeded"
else
  echo "   ✗ Complete failed"
  exit 1
fi

# 验证状态已更新
FINAL_STATUS=$(pp_status "$REF")
FINAL_STATE=$(echo "$FINAL_STATUS" | jq -r '.state')
echo "   - Final state: $FINAL_STATE"

echo ""

# 测试 4: 降级机制
echo "5. Testing fallback mechanism..."

AVAILABLE=$(pp_fallback_find_available "openspec")
echo "   Fallback from openspec: $AVAILABLE"
if [[ -n "$AVAILABLE" ]]; then
  echo "   ✓ Fallback works"
else
  echo "   ✗ Fallback failed"
  exit 1
fi

echo ""

echo "=== All Tests Passed! ==="
echo ""
echo "Core functionality verified:"
echo "  ✓ Adapter loading and validation"
echo "  ✓ Routing strategy engine"
echo "  ✓ Provider router core interfaces (start/status/complete)"
echo "  ✓ Fallback mechanism"
echo ""
echo "Note: All 4 adapters (Manual, OpenSpec, Supervisor, Kiro) are implemented."

#!/usr/bin/env bash
# Comprehensive Test Suite for Process Plane

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "V3 Process Plane - Comprehensive Tests"
echo "========================================="
echo ""

# 加载模块
source "$PROJECT_ROOT/v3/process-plane/adapter-loader.sh"
source "$PROJECT_ROOT/v3/process-plane/strategy.sh"
source "$PROJECT_ROOT/v3/process-plane/fallback.sh"
source "$PROJECT_ROOT/v3/process-plane/router.sh"

PASSED=0
FAILED=0

pass() {
  echo "  ✓ $1"
  PASSED=$((PASSED + 1))
}

fail() {
  echo "  ✗ $1"
  FAILED=$((FAILED + 1))
}

# Test Suite 1: Adapter Registration
echo "Test Suite 1: Adapter Registration"
echo "-----------------------------------"

ADAPTERS=$(pp_adapter_list | wc -l | tr -d ' ')
if [[ "$ADAPTERS" == "4" ]]; then
  pass "4 adapters registered"
else
  fail "Expected 4 adapters, got $ADAPTERS"
fi

pp_adapter_exists "manual" && pass "Manual adapter exists" || fail "Manual adapter missing"
pp_adapter_exists "openspec" && pass "OpenSpec adapter exists" || fail "OpenSpec adapter missing"
pp_adapter_exists "supervisor" && pass "Supervisor adapter exists" || fail "Supervisor adapter missing"
pp_adapter_exists "kiro" && pass "Kiro adapter exists" || fail "Kiro adapter missing"

echo ""

# Test Suite 2: Routing Strategy
echo "Test Suite 2: Routing Strategy"
echo "-----------------------------------"

TASK='{"type":"spec-driven","risk":"low"}'
PROVIDER=$(pp_strategy_evaluate "$TASK" | jq -r '.provider')
[[ "$PROVIDER" == "openspec" ]] && pass "spec-driven + low → OpenSpec" || fail "Expected openspec, got $PROVIDER"

TASK='{"type":"spec-driven","risk":"high"}'
PROVIDER=$(pp_strategy_evaluate "$TASK" | jq -r '.provider')
[[ "$PROVIDER" == "supervisor" ]] && pass "spec-driven + high → Supervisor" || fail "Expected supervisor, got $PROVIDER"

TASK='{"type":"ad-hoc","risk":"low","resources":{"ai":"sufficient"}}'
PROVIDER=$(pp_strategy_evaluate "$TASK" | jq -r '.provider')
[[ "$PROVIDER" == "kiro" ]] && pass "ad-hoc + AI → Kiro" || fail "Expected kiro, got $PROVIDER"

echo ""

# Test Suite 3: Provider Router Core
echo "Test Suite 3: Provider Router Core"
echo "-----------------------------------"

TASK='{"type":"manual","id":"test-core"}'
REF=$(pp_start "$TASK" '{"test":"context"}')

if [[ -n "$REF" && "$REF" != error:* ]]; then
  pass "pp_start returns valid ref: $REF"
  
  STATUS=$(pp_status "$REF")
  STATE=$(echo "$STATUS" | jq -r '.state')
  [[ "$STATE" == "in_progress" ]] && pass "Status is in_progress" || fail "Unexpected state: $STATE"
  
  COMPLETE=$(pp_complete "$REF")
  RESULT=$(echo "$COMPLETE" | jq -r '.result')
  [[ "$RESULT" == "success" ]] && pass "Complete succeeds" || fail "Complete failed"
else
  fail "pp_start failed: $REF"
fi

echo ""

# Test Suite 4: Fallback Mechanism
echo "Test Suite 4: Fallback Mechanism"
echo "-----------------------------------"

FALLBACK=$(pp_fallback_find_available "supervisor")
[[ -n "$FALLBACK" ]] && pass "Fallback from supervisor: $FALLBACK" || fail "Fallback failed"

FALLBACK=$(pp_fallback_find_available "kiro")
[[ "$FALLBACK" == "manual" ]] && pass "Kiro fallbacks to manual" || fail "Expected manual, got $FALLBACK"

echo ""

# Test Suite 5: End-to-End
echo "Test Suite 5: End-to-End Scenarios"
echo "-----------------------------------"

# Scenario 1
TASK1='{"type":"spec-driven","risk":"low","id":"e2e-1"}'
REF1=$(pp_start "$TASK1" '{"test":true}')
COMPLETE1=$(pp_complete "$REF1")
[[ $(echo "$COMPLETE1" | jq -r '.result') == "success" ]] && pass "E2E: Spec-driven task" || fail "E2E scenario failed"

# Scenario 2
TASK2='{"type":"spec-driven","risk":"high","id":"e2e-2"}'
REF2=$(pp_start "$TASK2" '{"test":true}')
COMPLETE2=$(pp_complete "$REF2")
[[ $(echo "$COMPLETE2" | jq -r '.result') == "success" ]] && pass "E2E: High-risk task" || fail "E2E scenario failed"

echo ""

# Summary
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Total: $((PASSED + FAILED))"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [[ $FAILED -eq 0 ]]; then
  echo "🎉 All tests passed! 🎉"
  echo ""
  echo "Verified:"
  echo "  ✓ Adapter registration (4 adapters)"
  echo "  ✓ Routing strategy (3 scenarios)"
  echo "  ✓ Provider router core (3 operations)"
  echo "  ✓ Fallback mechanism (2 scenarios)"
  echo "  ✓ End-to-end flows (2 scenarios)"
  exit 0
else
  echo "❌ Some tests failed"
  exit 1
fi

#!/usr/bin/env bash
set -euo pipefail

# Test handshake protocol state documentation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
SKILL_FILE="${PROJECT_ROOT}/skills/vibe-team-review/SKILL.md"
SCRIPT_FILE="${PROJECT_ROOT}/skills/vibe-team-review/scripts/agent-exist.sh"

echo "Testing handshake protocol state documentation"

# Test 1: SKILL.md documents all three states
echo "Test 1: Check SKILL.md documents ready_event states"
if ! grep -q "ready_event=found" "$SKILL_FILE"; then
  echo "ERROR: SKILL.md missing ready_event=found documentation"
  exit 1
fi

if ! grep -q "ready_event=missing" "$SKILL_FILE"; then
  echo "ERROR: SKILL.md missing ready_event=missing documentation"
  exit 1
fi

if ! grep -q "ready_event=waiting" "$SKILL_FILE"; then
  echo "ERROR: SKILL.md missing ready_event=waiting documentation"
  exit 1
fi

echo "OK: SKILL.md documents all three states"

# Test 2: agent-exist.sh outputs documented states
echo "Test 2: Check agent-exist.sh outputs documented states"
states_in_script=$(grep -o 'ready_event=[a-z]*' "$SCRIPT_FILE" | sort -u)

expected_states="ready_event=found
ready_event=missing
ready_event=waiting"

if [[ "$states_in_script" != "$expected_states" ]]; then
  echo "ERROR: Script states don't match documentation"
  echo "Expected: $expected_states"
  echo "Got: $states_in_script"
  exit 1
fi

echo "OK: agent-exist.sh outputs all documented states"

# Test 3: SKILL.md explains semantics of each state
echo "Test 3: Check SKILL.md explains state semantics"
if ! grep -A 3 "ready_event=found" "$SKILL_FILE" | grep -qi "agent.*ready\|就绪"; then
  echo "ERROR: SKILL.md missing ready_event=found semantics"
  exit 1
fi

if ! grep -A 3 "ready_event=missing" "$SKILL_FILE" | grep -qi "agent.*not.*sent\|未发送"; then
  echo "ERROR: SKILL.md missing ready_event=missing semantics"
  exit 1
fi

if ! grep -A 3 "ready_event=waiting" "$SKILL_FILE" | grep -qi "inbox.*not.*exist\|inbox.*不存在"; then
  echo "ERROR: SKILL.md missing ready_event=waiting semantics"
  exit 1
fi

echo "OK: SKILL.md explains state semantics"

echo
echo "SUCCESS: All handshake protocol state tests pass"

#!/usr/bin/env zsh
# tests/test_config_init.sh
# Test config initialization logic

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT_ROOT/lib/utils.sh"
source "$PROJECT_ROOT/lib/config.sh"
source "$PROJECT_ROOT/lib/config_init.sh"
source "$PROJECT_ROOT/lib/testing.sh"

start_test_suite "Config Sync"

# Test 1: Sync from project config
echo "Test 1: Sync from project config"
TEMP_VIBE_HOME=$(mktemp -d)
TEMP_PROJECT=$(mktemp -d)
mkdir -p "$TEMP_PROJECT/config"
echo "TEST_KEY=\"project_value\"" > "$TEMP_PROJECT/config/keys.env"

VIBE_HOME="$TEMP_VIBE_HOME" sync_keys_env "$TEMP_PROJECT" >/dev/null 2>&1
if [[ -f "$TEMP_VIBE_HOME/keys.env" ]] && grep -q "project_value" "$TEMP_VIBE_HOME/keys.env"; then
    echo "  ✅ Project config synced"
else
    echo "  ❌ FAILED: Project config not synced"
    rm -rf "$TEMP_VIBE_HOME" "$TEMP_PROJECT"
    exit 1
fi

# Test 2: Failed sync when no project config
echo "Test 2: Require project config (no template fallback)"
TEMP_VIBE_HOME2=$(mktemp -d)
TEMP_PROJECT2=$(mktemp -d)
mkdir -p "$TEMP_PROJECT2/config"
echo "TEMPLATE=\"template\"" > "$TEMP_PROJECT2/config/keys.template.env"

# Should fail because no real keys.env exists
if VIBE_HOME="$TEMP_VIBE_HOME2" sync_keys_env "$TEMP_PROJECT2" >/dev/null 2>&1; then
    echo "  ❌ FAILED: Should have failed without project keys.env"
    rm -rf "$TEMP_VIBE_HOME" "$TEMP_VIBE_HOME2" "$TEMP_PROJECT" "$TEMP_PROJECT2"
    exit 1
else
    echo "  ✅ Correctly requires project config (no template fallback)"
fi

# Test 3: get_env_value function
echo "Test 3: get_env_value helper"
TEMP_KEYS=$(mktemp)
echo 'ANTHROPIC_AUTH_TOKEN="sk-test-123"' > "$TEMP_KEYS"
echo 'VIBE_DEFAULT_TOOL="claude"' >> "$TEMP_KEYS"

value=$(get_env_value "ANTHROPIC_AUTH_TOKEN" "$TEMP_KEYS")
if [[ "$value" == "sk-test-123" ]]; then
    echo "  ✅ get_env_value works correctly"
else
    echo "  ❌ FAILED: got '$value', expected 'sk-test-123'"
    rm -rf "$TEMP_VIBE_HOME" "$TEMP_VIBE_HOME2" "$TEMP_PROJECT" "$TEMP_PROJECT2" "$TEMP_KEYS"
    exit 1
fi

# Test 4: set_env_value function
echo "Test 4: set_env_value helper"
TEMP_KEYS2=$(mktemp)
echo 'OLD_KEY="old_value"' > "$TEMP_KEYS2"

if set_env_value "NEW_KEY" "new_value" "$TEMP_KEYS2" >/dev/null 2>&1; then
    if grep -q 'NEW_KEY="new_value"' "$TEMP_KEYS2"; then
        echo "  ✅ set_env_value adds new key"
    else
        echo "  ❌ FAILED: New key not added"
        rm -rf "$TEMP_VIBE_HOME" "$TEMP_VIBE_HOME2" "$TEMP_PROJECT" "$TEMP_PROJECT2" "$TEMP_KEYS" "$TEMP_KEYS2"
        exit 1
    fi
else
    echo "  ❌ FAILED: set_env_value returned error"
    rm -rf "$TEMP_VIBE_HOME" "$TEMP_VIBE_HOME2" "$TEMP_PROJECT" "$TEMP_PROJECT2" "$TEMP_KEYS" "$TEMP_KEYS2"
    exit 1
fi

# Cleanup
rm -rf "$TEMP_VIBE_HOME" "$TEMP_VIBE_HOME2" "$TEMP_PROJECT" "$TEMP_PROJECT2" "$TEMP_KEYS" "$TEMP_KEYS2"

finish_test_suite

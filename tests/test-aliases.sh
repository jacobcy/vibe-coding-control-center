#!/usr/bin/env zsh
# Test script for alias files
# Usage: ./test-aliases.sh [--quiet]

# Don't use set -e to avoid exiting on glob failures

# Get script directory (resolve symlinks)
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"

QUIET_MODE=false
[[ "$1" == "--quiet" ]] && QUIET_MODE=true

log() {
  $QUIET_MODE || echo "$@"
}

# Initialize counters
typeset -i errors=0
typeset -i tested=0

log "=== Alias Files Syntax Check ==="
log ""

# Test main aliases file
if [[ -f "$PROJECT_ROOT/config/aliases.sh" ]]; then
  log "Testing: config/aliases.sh"
  if zsh -n "$PROJECT_ROOT/config/aliases.sh" 2>&1; then
    log "  ✓ Syntax OK"
    ((tested++))
  else
    log "  ✗ Syntax error"
    ((errors++))
  fi
fi

# Test all .sh files in config/aliases/ (including subdirectories)
# Use nullglob equivalent to handle no matches
setopt nullglob
alias_files=("$PROJECT_ROOT/config/aliases"/**/*.sh)
unsetopt nullglob

for alias_file in "${alias_files[@]}"; do
  [[ -f "$alias_file" ]] || continue

  rel_path="${alias_file#$PROJECT_ROOT/}"
  log "Testing: $rel_path"

  if zsh -n "$alias_file" 2>&1; then
    log "  ✓ Syntax OK"
    ((tested++))
  else
    log "  ✗ Syntax error"
    ((errors++))
  fi
done

log ""
log "=== Test Summary ==="
log "Tested: $tested files"
log "Errors: $errors"

if [[ $errors -gt 0 ]]; then
  log ""
  log "❌ FAILED: $errors files have syntax errors"
  exit 1
else
  log ""
  log "✅ PASSED: All alias files have valid syntax"
  exit 0
fi

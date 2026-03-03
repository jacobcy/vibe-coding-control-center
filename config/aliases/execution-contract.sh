#!/usr/bin/env zsh
# Execution Contract - Standardized execution result management
# Part of V3 Execution Plane
#
# This module has been refactored into submodules:
# - contract/validation.sh: JSON schema validation
# - contract/queries.sh: Query functions (by task_id, worktree, session)
# - contract/maintenance.sh: Cleanup and maintenance utilities

# Source all contract submodules
# Use VIBE_ROOT if available (for testing), otherwise resolve from script location
if [[ -n "$VIBE_ROOT" ]]; then
  CONTRACT_MODULE_DIR="$VIBE_ROOT/config/aliases/contract"
else
  CONTRACT_MODULE_DIR="${0:a:h}/contract"
fi

source "$CONTRACT_MODULE_DIR/validation.sh" 2>/dev/null || true
source "$CONTRACT_MODULE_DIR/queries.sh" 2>/dev/null || true
source "$CONTRACT_MODULE_DIR/maintenance.sh" 2>/dev/null || true

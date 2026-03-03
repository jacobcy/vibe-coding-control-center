#!/usr/bin/env zsh
# Worktree management commands
# Part of V3 Execution Plane
#
# This module has been refactored into submodules:
# - worktree/naming.sh: Naming validation and conflict handling
# - worktree/validation.sh: Worktree integrity validation
# - worktree/cleanup.sh: Worktree removal operations
# - worktree/navigation.sh: Worktree navigation utilities
# - worktree/core.sh: Core worktree creation logic

# Source all worktree submodules
# Use VIBE_ROOT if available (for testing), otherwise resolve from script location
if [[ -n "$VIBE_ROOT" ]]; then
  WORKTREE_MODULE_DIR="$VIBE_ROOT/config/aliases/worktree"
else
  # Fallback: Use BASH_SOURCE or ZSH script context
  WORKTREE_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")" 2>/dev/null && pwd)/config/aliases/worktree"
fi

source "$WORKTREE_MODULE_DIR/naming.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/validation.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/cleanup.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/navigation.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/list.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/core.sh" 2>/dev/null || true

# Backward compatibility alias
alias wtls='wtlist'

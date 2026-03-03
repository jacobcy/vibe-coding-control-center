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
WORKTREE_MODULE_DIR="${0:a:h}/worktree"

source "$WORKTREE_MODULE_DIR/naming.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/validation.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/cleanup.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/navigation.sh" 2>/dev/null || true
source "$WORKTREE_MODULE_DIR/core.sh" 2>/dev/null || true

# Backward compatibility alias
alias wtls='wtlist'

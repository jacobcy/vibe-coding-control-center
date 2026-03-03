#!/usr/bin/env zsh
# Main worktree aliases module
# Part of V3 Execution Plane

# Source all worktree submodules
source "${0:a:h}/naming.sh" 2>/dev/null || true
source "${0:a:h}/validation.sh" 2>/dev/null || true
source "${0:a:h}/cleanup.sh" 2>/dev/null || true
source "${0:a:h}/navigation.sh" 2>/dev/null || true
source "${0:a:h}/core.sh" 2>/dev/null || true

# Maintain backward compatibility
alias wtls='wtlist'

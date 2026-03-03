#!/usr/bin/env zsh
# Main execution contract module
# Part of V3 Execution Plane

# Source all contract submodules
CONTRACT_MODULE_DIR="${0:a:h}/contract"

source "$CONTRACT_MODULE_DIR/validation.sh" 2>/dev/null || true
source "$CONTRACT_MODULE_DIR/queries.sh" 2>/dev/null || true
source "$CONTRACT_MODULE_DIR/maintenance.sh" 2>/dev/null || true

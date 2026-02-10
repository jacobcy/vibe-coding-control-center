#!/usr/bin/env zsh
# scripts/cleanup.sh
# utility to clean up temporary artifacts from the workspace

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/.."
source "$ROOT_DIR/lib/utils.sh"

log_step "Cleaning up temporary Vibe artifacts..."

# Clean up tmpvibe-* folders in root
find "$ROOT_DIR" -maxdepth 1 -type d -name "tmpvibe-*" -print0 | xargs -0 rm -rf

# Clean up vibe-init-test* folders in root (if any)
find "$ROOT_DIR" -maxdepth 1 -type d -name "vibe-init-test*" -print0 | xargs -0 rm -rf

# Clean up varfolder* folders (macOS specific artifacts seen in root)
find "$ROOT_DIR" -maxdepth 1 -type d -name "varfolder*" -print0 | xargs -0 rm -rf

log_success "Cleanup complete."

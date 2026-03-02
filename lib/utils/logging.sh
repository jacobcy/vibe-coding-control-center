#!/usr/bin/env zsh
# lib/utils/logging.sh - Logging utilities
# Target: ~20 lines | Pure functions, no side effects

# ── Logging ─────────────────────────────────────────────
log_info()    { echo "${GREEN}ℹ $1${NC}"; }
log_warn()    { echo "${YELLOW}! $1${NC}" >&2; }
log_error()   { echo "${RED}✗ $1${NC}" >&2; }
log_debug()   { [[ "${VIBE_DEBUG:-}" == "1" ]] && echo "${BLUE}◈ $1${NC}" >&2 || true; }
log_step()    { echo "${BLUE}>> $1...${NC}"; }
log_success() { echo "${GREEN}★ $1${NC}"; }

# ── Legacy Compatibility ────────────────────────────────
# Map old names to new functions
log_warning() { log_warn "$@"; }
log_info()    { log_info "$@"; }

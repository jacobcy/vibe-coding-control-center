#!/usr/bin/env zsh
# lib/clean.sh – Project maintenance and cleanup

[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }

vibe_clean() {
  log_step "Cleaning project temporary files..."
  
  local count=0
  
  if [[ -d "${VIBE_ROOT}/temp" ]]; then
    rm -rf "${VIBE_ROOT}/temp"/* 2>/dev/null || true
    log_info "Cleaned temp/"
    ((count++))
  fi
  
  local tmpdirs
  tmpdirs=(${VIBE_ROOT}/tmpvibe-*(N/))
  if [[ ${#tmpdirs[@]} -gt 0 ]]; then
    rm -rf "${tmpdirs[@]}"
    log_info "Cleaned tmpvibe-*/"
    ((count++))
  fi

  local testdirs
  testdirs=(${VIBE_ROOT}/vibe-init-test*(N/))
  if [[ ${#testdirs[@]} -gt 0 ]]; then
    rm -rf "${testdirs[@]}"
    log_info "Cleaned test directories/"
    ((count++))
  fi
  
  if [[ $count -gt 0 ]]; then
    log_success "Cleanup complete."
  else
    log_info "Nothing to clean."
  fi
}

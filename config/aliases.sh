#!/usr/bin/env zsh
# config/aliases.sh - Compatibility shim for Vibe 2.0
# DEPRECATED: Use source $(vibe alias --load) which points to alias/loader.sh

_v_shim_self="$(dirname "${(%):-%x:A}")"
_v_new_loader="$_v_shim_self/../alias/loader.sh"

if [[ -f "$_v_new_loader" ]]; then
  source "$_v_new_loader"
else
  echo "vibe: error: alias/loader.sh not found" >&2
fi

unset _v_shim_self _v_new_loader

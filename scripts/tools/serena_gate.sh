#!/usr/bin/env bash
set -euo pipefail

if ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
elif [[ -n "${VIBE_ROOT:-}" ]]; then
  ROOT="$VIBE_ROOT"
else
  ROOT="$(pwd)"
fi

REPORT_DIR="$ROOT/.agent/reports"
REPORT_FILE="$REPORT_DIR/serena-impact.json"
PROJECT_FILE="$ROOT/.serena/project.yml"
SERENA_SOURCE="git+https://github.com/oraios/serena@v0.1.4"
SERENA_GLOBAL_ROOT="$HOME/.serena"
SERENA_CACHE_ROOT="${XDG_CACHE_HOME:-$HOME/.cache}/uv/archive-v0"
BASE_REF="${SERENA_BASE_REF:-}"

usage() {
  cat <<'EOF'
Usage: scripts/serena_gate.sh [--base <git-range>] [--file <relative-path>]...

Runs Serena AST gate against changed shell files and writes:
  .agent/reports/serena-impact.json

Options:
  --base <git-range>   Diff range for candidate files (default: origin/main...HEAD, fallback main...HEAD)
  --file <path>        Explicit file(s) to analyze, can pass multiple times
  -h, --help           Show this help
EOF
}

require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERROR: missing command: $cmd" >&2
    exit 2
  }
}

cleanup_runtime() {
  if [[ -n "${SERENA_RUNTIME_HOME:-}" && -d "${SERENA_RUNTIME_HOME:-}" ]]; then
    rm -rf "$SERENA_RUNTIME_HOME"
  fi
}

setup_serena_runtime_home() {
  SERENA_RUNTIME_HOME="$(mktemp -d)"

  cat >"$SERENA_RUNTIME_HOME/serena_config.yml" <<'EOF'
language_backend: LSP
gui_log_window: false
web_dashboard: false
web_dashboard_open_on_launch: false
web_dashboard_listen_address: 127.0.0.1
jetbrains_plugin_server_address: 127.0.0.1
log_level: 20
trace_lsp_communication: false
ls_specific_settings: {}
ignored_paths: []
tool_timeout: 240
excluded_tools: []
included_optional_tools: []
fixed_tools: []
base_modes:
default_modes:
- interactive
- editing
default_max_tool_answer_chars: 150000
token_count_estimator: CHAR_COUNT
projects: []
symbol_info_budget: 10.0
project_serena_folder_location: $projectDir/.serena
read_only_memory_patterns: []
EOF

  if [[ -d "$SERENA_GLOBAL_ROOT/language_servers" ]]; then
    ln -s "$SERENA_GLOBAL_ROOT/language_servers" "$SERENA_RUNTIME_HOME/language_servers"
  fi
}

resolve_serena_site_packages() {
  local serena_bin archive_root config_path
  for serena_bin in "$SERENA_CACHE_ROOT"/*/bin/serena; do
    [[ -e "$serena_bin" ]] || continue
    archive_root="$(dirname "$(dirname "$serena_bin")")"
    config_path="$(find "$archive_root/lib" -path '*/site-packages/serena/config/serena_config.py' -print -quit 2>/dev/null || true)"
    if [[ -n "$config_path" ]] && grep -q 'SERENA_HOME' "$config_path"; then
      SERENA_SITE_PACKAGES="${config_path%/serena/config/serena_config.py}"
      SERENA_ARCHIVE_ROOT="$archive_root"
      return 0
    fi
  done

  if uvx --from "$SERENA_SOURCE" serena --help >/dev/null 2>&1; then
    for serena_bin in "$SERENA_CACHE_ROOT"/*/bin/serena; do
      [[ -e "$serena_bin" ]] || continue
      archive_root="$(dirname "$(dirname "$serena_bin")")"
      config_path="$(find "$archive_root/lib" -path '*/site-packages/serena/config/serena_config.py' -print -quit 2>/dev/null || true)"
      if [[ -n "$config_path" ]] && grep -q 'SERENA_HOME' "$config_path"; then
        SERENA_SITE_PACKAGES="${config_path%/serena/config/serena_config.py}"
        SERENA_ARCHIVE_ROOT="$archive_root"
        return 0
      fi
    done
  fi

  echo "ERROR: failed to locate Serena site-packages with SERENA_HOME support" >&2
  exit 3
}

run_serena_python() {
  local runner="$ROOT/scripts/tools/serena_gate.py"
  if [[ ! -f "$runner" && -f "$ROOT/scripts/serena_gate.py" ]]; then
    runner="$ROOT/scripts/serena_gate.py"
  fi

  SERENA_HOME="$SERENA_RUNTIME_HOME" \
  SERENA_PROJECT_ROOT="$ROOT" \
  "$SERENA_ARCHIVE_ROOT/bin/python3" "$runner"
}

parse_project_name() {
  local name
  name="$(awk -F': ' '/^project_name:/{gsub(/"/,"",$2); print $2; exit}' "$PROJECT_FILE" 2>/dev/null || true)"
  [[ -n "$name" ]] || name="$(basename "$ROOT")"
  printf '%s' "$name"
}

collect_changed_files() {
  local -a files
  local line
  if [[ ${#EXPLICIT_FILES[@]} -gt 0 ]]; then
    files=("${EXPLICIT_FILES[@]}")
  else
    while IFS= read -r line; do
      [[ -n "$line" ]] && files+=("$line")
    done < <(git -C "$ROOT" diff --name-only "$BASE_REF" -- '*.sh' 'bin/vibe' 2>/dev/null || true)
  fi

  for f in "${files[@]}"; do
    [[ -f "$ROOT/$f" ]] && printf '%s\n' "$f"
  done | awk '!seen[$0]++'
}

resolve_base_ref() {
  if [[ -n "$BASE_REF" ]]; then
    return 0
  fi

  if git -C "$ROOT" rev-parse --verify origin/main >/dev/null 2>&1; then
    BASE_REF="origin/main...HEAD"
    return 0
  fi

  if git -C "$ROOT" rev-parse --verify main >/dev/null 2>&1; then
    BASE_REF="main...HEAD"
    return 0
  fi

  BASE_REF="HEAD"
}

write_empty_report() {
  local project_name="$1"
  jq -nc \
    --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --arg project "$project_name" \
    --arg base_ref "$BASE_REF" \
    '{
      generated_at:$generated_at,
      project:$project,
      base_ref:$base_ref,
      health_check:{status:"ok", log:""},
      files:[],
      summary:{files:0, file_errors:0, symbol_errors:0},
      notes:["No changed shell files detected"]
    }' >"$REPORT_FILE"
}

EXPLICIT_FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE_REF="${2:-}"
      shift 2
      ;;
    --file)
      EXPLICIT_FILES+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd python3
require_cmd uvx
require_cmd jq
[[ -f "$PROJECT_FILE" ]] || { echo "ERROR: missing .serena/project.yml" >&2; exit 2; }

mkdir -p "$REPORT_DIR"
PROJECT_NAME="$(parse_project_name)"
resolve_base_ref

TARGET_FILES=()
while IFS= read -r line; do
  [[ -n "$line" ]] && TARGET_FILES+=("$line")
done < <(collect_changed_files)
if [[ ${#TARGET_FILES[@]} -eq 0 ]]; then
  write_empty_report "$PROJECT_NAME"
  echo "Serena gate: no target files, wrote $REPORT_FILE"
  cat "$REPORT_FILE"
  exit 0
fi

setup_serena_runtime_home
resolve_serena_site_packages
trap cleanup_runtime EXIT

TARGET_FILES_JSON="$(printf '%s\n' "${TARGET_FILES[@]}" | jq -R . | jq -s .)"

echo "Serena gate: analyzing ${#TARGET_FILES[@]} file(s) with isolated SERENA_HOME ..."
SERENA_TARGET_FILES_JSON="$TARGET_FILES_JSON" \
SERENA_PROJECT_NAME="$PROJECT_NAME" \
SERENA_BASE_REF="$BASE_REF" \
SERENA_REPORT_FILE="$REPORT_FILE" \
run_serena_python

echo "Serena gate: wrote $REPORT_FILE"
cat "$REPORT_FILE"

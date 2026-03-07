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
SERENA_CMD=(uvx --from "$SERENA_SOURCE" serena)
BASE_REF="${SERENA_BASE_REF:-main...HEAD}"
PORT="${SERENA_PROJECT_SERVER_PORT:-18231}"

usage() {
  cat <<'EOF'
Usage: scripts/serena_gate.sh [--base <git-range>] [--file <relative-path>]...

Runs Serena AST gate against changed shell files and writes:
  .agent/reports/serena-impact.json

Options:
  --base <git-range>   Diff range for candidate files (default: main...HEAD)
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

cleanup_server() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}

parse_project_name() {
  local name
  name="$(awk -F': ' '/^project_name:/{gsub(/"/,"",$2); print $2; exit}' "$PROJECT_FILE" 2>/dev/null || true)"
  [[ -n "$name" ]] || name="$(basename "$ROOT")"
  printf '%s' "$name"
}

wait_heartbeat() {
  local attempts=0
  local max_attempts=20
  while (( attempts < max_attempts )); do
    if curl -sS "http://127.0.0.1:${PORT}/heartbeat" >/dev/null 2>&1; then
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 0.5
  done
  return 1
}

query_project_tool() {
  local project_name="$1"
  local tool_name="$2"
  local tool_params_json="$3"
  local payload
  payload="$(jq -nc \
    --arg project_name "$project_name" \
    --arg tool_name "$tool_name" \
    --arg tool_params_json "$tool_params_json" \
    '{project_name:$project_name, tool_name:$tool_name, tool_params_json:$tool_params_json}')"
  curl -sS -X POST "http://127.0.0.1:${PORT}/query_project" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

collect_changed_files() {
  local -a files
  if [[ ${#EXPLICIT_FILES[@]} -gt 0 ]]; then
    files=("${EXPLICIT_FILES[@]}")
  else
    mapfile -t files < <(git -C "$ROOT" diff --name-only "$BASE_REF" -- '*.sh' 'bin/vibe' 2>/dev/null || true)
  fi
  for f in "${files[@]}"; do
    [[ -f "$ROOT/$f" ]] && printf '%s\n' "$f"
  done | awk '!seen[$0]++'
}

analyze_file() {
  local project_name="$1"
  local relative_file="$2"
  local params overview functions_tmp symbols_tmp fn ref_params refs ref_count status

  params="$(jq -nc --arg rp "$relative_file" '{relative_path:$rp, depth:0}')"
  overview="$(query_project_tool "$project_name" "get_symbols_overview" "$params" || true)"

  if ! echo "$overview" | jq -e . >/dev/null 2>&1; then
    jq -nc --arg f "$relative_file" --arg err "get_symbols_overview_failed" \
      '{file:$f, status:"error", error:$err, symbols:[]}'
    return 0
  fi

  functions_tmp="$(mktemp)"
  symbols_tmp="$(mktemp)"
  echo "$overview" | jq -r '
    (
      if type == "object" and (.Function? | type == "array") then .Function else [] end
    ) + (
      [.. | objects | select(.kind? == "Function" and (.name? | type == "string")) | .name]
    )
    | unique[]?
  ' >"$functions_tmp"
  echo '[]' >"$symbols_tmp"

  while IFS= read -r fn; do
    [[ -n "$fn" ]] || continue
    ref_params="$(jq -nc --arg n "$fn" --arg rp "$relative_file" '{name_path:$n, relative_path:$rp}')"
    refs="$(query_project_tool "$project_name" "find_referencing_symbols" "$ref_params" || true)"
    if echo "$refs" | jq -e . >/dev/null 2>&1; then
      ref_count="$(echo "$refs" | jq 'if type=="array" then length elif type=="object" then ([.. | objects | .name_path? // empty] | map(select(length>0)) | length) else 0 end')"
      status="ok"
    else
      ref_count=0
      status="error"
    fi
    jq --arg name "$fn" --arg status "$status" --argjson count "$ref_count" \
      '. += [{name:$name, status:$status, references:$count}]' \
      "$symbols_tmp" >"${symbols_tmp}.tmp" && mv "${symbols_tmp}.tmp" "$symbols_tmp"
  done <"$functions_tmp"

  jq -nc --arg f "$relative_file" --slurpfile s "$symbols_tmp" \
    '{file:$f, status:"ok", symbols:($s[0] // [])}'
  rm -f "$functions_tmp" "$symbols_tmp"
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

require_cmd uvx
require_cmd jq
require_cmd curl
[[ -f "$PROJECT_FILE" ]] || { echo "ERROR: missing .serena/project.yml" >&2; exit 2; }

mkdir -p "$REPORT_DIR"
PROJECT_NAME="$(parse_project_name)"

echo "Serena gate: indexing project ..."
(cd "$ROOT" && "${SERENA_CMD[@]}" project index . >/dev/null)

HEALTH_CHECK_STATUS="ok"
HEALTH_CHECK_LOG=""
HEALTH_CHECK_OUTPUT="$(mktemp)"
echo "Serena gate: running project health-check ..."
if (cd "$ROOT" && "${SERENA_CMD[@]}" project health-check . >"$HEALTH_CHECK_OUTPUT" 2>&1); then
  HEALTH_CHECK_LOG="$(awk -F'Log saved to: ' '/Log saved to:/{print $2; exit}' "$HEALTH_CHECK_OUTPUT" | xargs)"
  rm -f "$HEALTH_CHECK_OUTPUT"
else
  HEALTH_CHECK_STATUS="error"
  HEALTH_CHECK_LOG="$HEALTH_CHECK_OUTPUT"
fi

echo "Serena gate: starting project server on port ${PORT} ..."
SERVER_LOG="$(mktemp)"
(
  cd "$ROOT"
  "${SERENA_CMD[@]}" start-project-server --port "$PORT" >"$SERVER_LOG" 2>&1
) &
SERVER_PID=$!
trap cleanup_server EXIT

wait_heartbeat || {
  echo "ERROR: Serena project server failed to start" >&2
  exit 3
}

mapfile -t TARGET_FILES < <(collect_changed_files)
if [[ ${#TARGET_FILES[@]} -eq 0 ]]; then
  jq -nc \
    --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --arg project "$PROJECT_NAME" \
    --arg base_ref "$BASE_REF" \
    --arg health_check_status "$HEALTH_CHECK_STATUS" \
    --arg health_check_log "$HEALTH_CHECK_LOG" \
    '{
      generated_at:$generated_at,
      project:$project,
      base_ref:$base_ref,
      health_check:{status:$health_check_status, log:$health_check_log},
      files:[],
      notes:["No changed shell files detected"]
    }' >"$REPORT_FILE"
  echo "Serena gate: no target files, wrote $REPORT_FILE"
  if [[ "$HEALTH_CHECK_STATUS" != "ok" ]]; then
    echo "ERROR: Serena health-check failed. See $HEALTH_CHECK_LOG" >&2
    exit 5
  fi
  exit 0
fi

files_json_tmp="$(mktemp)"
echo '[]' >"$files_json_tmp"
for rel in "${TARGET_FILES[@]}"; do
  file_result="$(analyze_file "$PROJECT_NAME" "$rel")"
  jq --argjson fr "$file_result" '. += [$fr]' "$files_json_tmp" >"${files_json_tmp}.tmp" && mv "${files_json_tmp}.tmp" "$files_json_tmp"
done

jq -nc \
  --arg generated_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --arg project "$PROJECT_NAME" \
  --arg base_ref "$BASE_REF" \
  --arg health_check_status "$HEALTH_CHECK_STATUS" \
  --arg health_check_log "$HEALTH_CHECK_LOG" \
  --slurpfile files "$files_json_tmp" \
  '{
    generated_at:$generated_at,
    project:$project,
    base_ref:$base_ref,
    health_check:{status:$health_check_status, log:$health_check_log},
    files:($files[0] // []),
    summary:{
      files: (($files[0] // []) | length),
      file_errors: (($files[0] // []) | map(select(.status != "ok")) | length),
      symbol_errors: (($files[0] // []) | map(.symbols // []) | add | map(select(.status != "ok")) | length)
    }
  }' >"$REPORT_FILE"

rm -f "$files_json_tmp"
echo "Serena gate: wrote $REPORT_FILE"
cat "$REPORT_FILE"

if [[ "$HEALTH_CHECK_STATUS" != "ok" ]]; then
  echo "ERROR: Serena health-check failed. See $HEALTH_CHECK_LOG" >&2
  exit 5
fi

if jq -e '.summary.file_errors > 0 or .summary.symbol_errors > 0' "$REPORT_FILE" >/dev/null 2>&1; then
  echo "ERROR: Serena gate found analysis errors. See $REPORT_FILE and server log: $SERVER_LOG" >&2
  exit 4
fi

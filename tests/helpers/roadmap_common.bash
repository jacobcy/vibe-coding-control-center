setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

_run_roadmap_cmd() {
  local command="$1"
  local stdin_mode="${2:-inherit}"
  local fixture="${3:-}"
  local script

  script="
    source \"$VIBE_ROOT/lib/config.sh\"
    source \"$VIBE_ROOT/lib/utils.sh\"
    source \"$VIBE_ROOT/lib/roadmap.sh\"
  "

  if [[ -n "$fixture" ]]; then
    script+="
    git() {
      case \"\$*\" in
        \"rev-parse --is-inside-work-tree\") return 0 ;;
        \"rev-parse --git-common-dir\") echo \"$fixture\"; return 0 ;;
        *) command git \"\$@\" ;;
      esac
    }
    "
  fi

  script+="
    $command
  "

  if [[ "$stdin_mode" == "null" ]]; then
    run zsh -c "$script" </dev/null
  else
    run zsh -c "$script"
  fi
}

run_roadmap_fixture_cmd() {
  local fixture="$1"
  local command="$2"

  _run_roadmap_cmd "$command" inherit "$fixture"
}

run_roadmap_fixture_cmd_no_tty() {
  local fixture="$1"
  local command="$2"

  _run_roadmap_cmd "$command" null "$fixture"
}

run_roadmap_cmd() {
  local command="$1"

  _run_roadmap_cmd "$command"
}

make_roadmap_fixture() {
  local fixture="$1"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v2","tasks":[]}
JSON
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version":"v2",
  "project_id":"PVT_kwDOBHxkss4A1a2B",
  "version_goal":"Complete shared-state standardization",
  "items":[
    {"roadmap_item_id":"rm-1","title":"Alpha","status":"current","source_type":"local","source_refs":[],"issue_refs":[],"linked_task_ids":[],"github_project_item_id":"PVTI_alpha","content_type":"draft_issue","spec_standard":"none","execution_record_id":null,"spec_ref":null,"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"},
    {"roadmap_item_id":"rm-2","title":"Beta","status":"p0","source_type":"local","source_refs":[],"issue_refs":[],"linked_task_ids":[],"github_project_item_id":"PVTI_beta","content_type":"draft_issue","spec_standard":"none","execution_record_id":null,"spec_ref":null,"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"},
    {"roadmap_item_id":"rm-3","title":"Gamma","status":"deferred","source_type":"local","source_refs":[],"issue_refs":[],"linked_task_ids":[],"github_project_item_id":"PVTI_gamma","content_type":"draft_issue","spec_standard":"none","execution_record_id":null,"spec_ref":null,"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"}
  ]
}
JSON
}

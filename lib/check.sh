#!/usr/bin/env zsh
# lib/check.sh - Shared-state audits and schema checks

[[ -f "$VIBE_LIB/check_pr_status.sh" ]] && source "$VIBE_LIB/check_pr_status.sh"
[[ -f "$VIBE_LIB/check_groups.sh" ]] && source "$VIBE_LIB/check_groups.sh"

_vibe_check_help() {
  echo "${BOLD}Vibe Check${NC}"
  echo ""
  echo "Usage: ${CYAN}vibe check${NC} [check] [target] [options]"
  echo ""
  echo "Targets:"
  echo "  ${GREEN}(none)${NC}            运行全量审计（roadmap/task/flow/link/docs）"
  echo "  ${GREEN}check${NC}             同上（兼容 command-standard）"
  echo "  ${GREEN}roadmap${NC}           只检查 roadmap 域"
  echo "  ${GREEN}task${NC}              只检查 task 域"
  echo "  ${GREEN}flow${NC}              只检查 flow 域"
  echo "  ${GREEN}link${NC}              只检查跨层链接一致性"
  echo "  ${GREEN}json <file>${NC}       JSON + schema 检查"
  echo "  ${GREEN}docs${NC}              文档 frontmatter 审计"
  echo ""
  echo "Options:"
  echo "  ${GREEN}--json${NC}            输出机器可读结果"
  echo ""
  echo "Examples:"
  echo "  vibe check"
  echo "  vibe check check --json"
  echo "  vibe check roadmap"
  echo "  vibe check json .git/vibe/registry.json"
}

_vibe_check_render_text() {
  local payload="$1" group group_json display_status summary
  local -a groups
  groups=("$(echo "$payload" | jq -r 'keys[]')")

  echo "${BOLD}Vibe Check Report${NC}"
  echo ""

  while IFS= read -r group; do
    [[ -z "$group" ]] && continue
    group_json="$(echo "$payload" | jq -c --arg g "$group" '.[$g]')"
    display_status="$(echo "$group_json" | jq -r '.status')"
    summary="$(echo "$group_json" | jq -r '.summary')"

    if [[ "$display_status" == "pass" ]]; then
      echo "${GREEN}[$group] PASS${NC} - $summary"
    else
      echo "${RED}[$group] FAIL${NC} - $summary"
    fi

    echo "$group_json" | jq -r '.errors[]?' | sed 's/^/  error: /'
    echo "$group_json" | jq -r '.warnings[]?' | sed 's/^/  warn:  /'
    echo ""
  done < <(echo "$payload" | jq -r 'keys[]')
}

_vibe_check_has_failures() {
  local payload="$1"
  echo "$payload" | jq -e 'to_entries | any(.value.status == "fail")' >/dev/null 2>&1
}

vibe_check() {
  local mode="all" json_out=0 file_arg=""
  local extra_args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        _vibe_check_help
        return 0
        ;;
      check)
        shift
        ;;
      --json)
        json_out=1
        shift
        ;;
      roadmap|task|flow|link|docs)
        [[ "$mode" == "all" ]] || { log_error "Only one check target can be specified"; return 1; }
        mode="$1"
        shift
        ;;
      json)
        mode="json"
        shift
        [[ $# -gt 0 ]] || { log_error "Usage: vibe check json <file>"; return 1; }
        file_arg="$1"
        shift
        ;;
      *)
        extra_args+=("$1")
        shift
        ;;
    esac
  done

  if [[ ${#extra_args[@]} -gt 0 ]]; then
    if [[ "$mode" == "all" && ${#extra_args[@]} -eq 1 ]]; then
      mode="json"
      file_arg="${extra_args[1]}"
    else
      log_error "Unknown check target: ${extra_args[1]}"
      return 1
    fi
  fi

  local payload
  case "$mode" in
    all)
      local g_roadmap g_task g_flow g_link g_docs
      g_roadmap="$(_vibe_check_group_roadmap)"
      g_task="$(_vibe_check_group_task)"
      g_flow="$(_vibe_check_group_flow)"
      g_link="$(_vibe_check_group_link)"
      g_docs="$(_vibe_check_group_docs)"
      payload="$(jq -nc \
        --argjson roadmap "$g_roadmap" \
        --argjson task "$g_task" \
        --argjson flow "$g_flow" \
        --argjson link "$g_link" \
        --argjson docs "$g_docs" \
        '{roadmap:$roadmap, task:$task, flow:$flow, link:$link, docs:$docs}')"
      ;;
    roadmap)
      payload="$(jq -nc --argjson roadmap "$(_vibe_check_group_roadmap)" '{roadmap:$roadmap}')"
      ;;
    task)
      payload="$(jq -nc --argjson task "$(_vibe_check_group_task)" '{task:$task}')"
      ;;
    flow)
      payload="$(jq -nc --argjson flow "$(_vibe_check_group_flow)" '{flow:$flow}')"
      ;;
    link)
      payload="$(jq -nc --argjson link "$(_vibe_check_group_link)" '{link:$link}')"
      ;;
    docs)
      payload="$(jq -nc --argjson docs "$(_vibe_check_group_docs)" '{docs:$docs}')"
      ;;
    json)
      [[ -n "$file_arg" ]] || { log_error "Usage: vibe check json <file>"; return 1; }
      payload="$(jq -nc --argjson json "$(_vibe_check_group_json_file "$file_arg")" '{json:$json}')"
      ;;
    *)
      log_error "Unknown check mode: $mode"
      return 1
      ;;
  esac

  if [[ "$json_out" -eq 1 ]]; then
    echo "$payload"
  else
    _vibe_check_render_text "$payload"
  fi

  _vibe_check_has_failures "$payload" && return 1 || return 0
}

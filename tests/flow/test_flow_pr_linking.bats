#!/usr/bin/env bats
# tests/flow/test_flow_pr_linking.bats - vibe flow pr auto-linking verification

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "flow: pr body includes Fixes #125 when gh-125 is linked" {
  local artifact_dir; artifact_dir="$(mktemp -d)"
  
  # We will test the logic by sourcing just the relevant part or mocking the environment heavily
  run zsh -c '
    VIBE_LIB="'"$VIBE_LIB"'"
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    
    # Mocking log functions
    log_info() { echo "INFO: $*"; }
    log_step() { echo "STEP: $*"; }
    log_error() { echo "ERROR: $*" >&2; }
    log_success() { echo "SUCCESS: $*"; }
    vibe_die() { echo "DIE: $*" >&2; exit 1; }
    vibe_require() { return 0; }
    vibe_has() { [[ "$1" == "gh" ]]; }

    # Mock flow functions
    _flow_resolve_pr_base() { echo "main"; }
    _flow_pr_base_git_ref() { echo "main"; }
    _flow_require_base_ref() { return 0; }
    _flow_require_latest_pr_base() { return 0; }
    
    _flow_show() {
      echo "{\"issue_refs\": [\"gh-125\"]}"
    }

    # Intercept gh pr create
    gh() {
      if [[ "$1" == "pr" && "$2" == "create" ]]; then
        # Capture arguments to a file
        while [[ $# -gt 0 ]]; do
          case "$1" in
            --body) echo "$2" > "'"$artifact_dir"'/pr_body" ;;
          esac
          shift
        done
        return 0
      fi
      [[ "$1" == "pr" && "$2" == "list" ]] && echo "[]"
      [[ "$1" == "pr" && "$2" == "view" ]] && return 1
      return 0
    }

    # Mock git commands used in _flow_pr
    git() {
      case "$1" in
        branch) echo "feature/branch" ;;
        log) echo "abcdef1 feat: commit message" ;;
        push) return 0 ;;
        show-ref|rev-parse|merge-base|rev-list|add|commit|fetch) return 0 ;;
        *) command git "$@" ;;
      esac
    }

    source "$VIBE_LIB/flow_pr.sh"
    _flow_pr --base main
  '
  
  [ "$status" -eq 0 ]
  [ -f "$artifact_dir/pr_body" ]
  grep -q "Fixes #125" "$artifact_dir/pr_body"
}

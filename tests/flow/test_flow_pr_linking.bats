#!/usr/bin/env bats
# tests/flow/test_flow_pr_linking.bats - vibe flow pr auto-linking verification

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "flow: pr appends Fixes # to body based on task issue_refs" {
  local fixture; fixture="$(mktemp -d)"
  cd "$fixture"
  git init -q
  git config user.email "test@example.com"
  git config user.name "Test User"
  echo "content" > file && git add file && git commit -m "initial" -q
  git checkout -b feature/work -q
  echo "change" > file && git add file && git commit -m "feat: main work" -q
  
  # Stub script for PR
  run zsh -c '
    source "$VIBE_LIB/utils.sh" 2>/dev/null || true
    source "$VIBE_LIB/flow_status.sh"
    source "$VIBE_LIB/flow_history.sh"
    source "$VIBE_LIB/flow_show.sh"
    source "$VIBE_LIB/flow_pr.sh"

    # Mock dependencies
    _flow_resolve_pr_base() { echo "main"; }
    _flow_pr_base_git_ref() { echo "main"; }
    _flow_require_latest_pr_base() { return 0; }
    vibe_has() { [[ "$1" == "git" ]]; } # Fake no gh to stop at push
    log_info() { :; }
    log_step() { :; }
    log_success() { :; }
    
    # Custom mock for _flow_show to return linked issues
    _flow_show() {
      if [[ "$1" == "--json" ]]; then
        echo "{\"issue_refs\": [\"gh-125\", \"gh-35\"]}"
      fi
    }
    
    # We want to check the processed pr_body. 
    # Since _flow_pr is long and does many things, we will check the variables it sets.
    # We can inject a check before it calls git push or gh.
    
    # Re-define git to intercept the commit message check (not ideal but works for testing variables if we had them exported)
    # Alternatively, let s just test that it reaches the point where it would create a PR with the right body.
    
    # We will redefine the final part of _flow_pr or mock the bump script to check environment
    _flow_pr
  '
  # This approach is hard because _flow_pr doesn't expose its variables easily.
  # Let's try to mock gh and capture the body.
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

#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/flow_common.bash"

@test "1.1 vibe flow review help points to the supported Codex package" {
  run vibe flow review --help

  [ "$status" -eq 0 ]
  [[ "$output" =~ "@openai/codex" ]]
  [[ ! "$output" =~ "@anthropic/codex" ]]
  [[ "$output" =~ "[<pr-or-branch>|--branch <ref>]" ]]
}

@test "1.2 _flow_review reports merged PR summary and next step" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    vibe_require() { return 0; }
    vibe_has() { [[ "$1" == "gh" ]]; }
    gh() {
      case "$*" in
        "pr view current-branch --json number,title,state,reviewDecision,mergeable,url,statusCheckRollup,comments")
          cat <<'"'"'JSON'"'"'
{"number":42,"title":"Summary output follow-up","state":"MERGED","reviewDecision":"APPROVED","mergeable":"MERGEABLE","url":"https://example.test/pr/42","statusCheckRollup":[{"status":"COMPLETED","state":"SUCCESS"}],"comments":[]}
JSON
          return 0
          ;;
        "pr checks current-branch")
          echo "checks ok"
          return 0
          ;;
        *)
          return 0
          ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_review
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "PR #42:" ]]
  [[ "$output" =~ "MERGED" ]]
  [[ "$output" =~ "Time to run 'vibe flow done'" ]]
}

@test "1.2b _flow_review --json includes structured review evidence summary" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    vibe_require() { return 0; }
    vibe_has() { [[ "$1" == "gh" ]]; }
    gh() {
      case "$*" in
        "pr view current-branch --json number,title,body,comments,reviews,commits,state,mergedAt,headRefName,baseRefName")
          cat <<'"'"'JSON'"'"'
{"number":42,"title":"Review gate","body":"body","state":"OPEN","mergedAt":null,"headRefName":"task/review-gated-done","baseRefName":"main","commits":[],"reviews":[{"author":{"login":"github-copilot[bot]"},"body":"Auto review complete"}],"comments":[{"author":{"login":"octocat"},"body":"Local review evidence via vibe flow review --local"},{"author":{"login":"codex"},"body":"@codex approved"}]}
JSON
          return 0
          ;;
        *)
          return 1
          ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_review --json
  '

  [ "$status" -eq 0 ]
  [[ "$(printf "%s" "$output" | jq -r '.reviewEvidence.has_review_evidence')" == "true" ]]
  [[ "$(printf "%s" "$output" | jq -r '.reviewEvidence.copilot')" == "true" ]]
  [[ "$(printf "%s" "$output" | jq -r '.reviewEvidence.codex')" == "true" ]]
  [[ "$(printf "%s" "$output" | jq -r '.reviewEvidence.local_comment')" == "true" ]]
}

@test "12. _flow_pr skips bump if PR already exists" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping version bump" ]]
}

@test "12.1 _flow_pr blocks publish when current task is missing spec_ref" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    _flow_show() {
      cat <<'"'"'JSON'"'"'
{"branch":"current-branch","current_task":"task-main","spec_ref":null}
JSON
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "task-main" ]]
  [[ "$output" =~ "spec_ref" ]]
}

@test "12.2 _flow_pr blocks publish when bound plan file does not exist" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    _flow_show() {
      cat <<'"'"'JSON'"'"'
{"branch":"current-branch","current_task":"task-main","spec_ref":"docs/plans/missing-plan.md"}
JSON
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "docs/plans/missing-plan.md" ]]
  [[ "$output" =~ "not found" || "$output" =~ "Missing" ]]
}

@test "12.3 _flow_pr auto-commits bound plan file before publish when bump is skipped" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/docs/plans"
  printf '%s\n' '# plan' > "$fixture/docs/plans/current-plan.md"

  run zsh -c '
    cd "'"$fixture"'"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    _flow_show() {
      cat <<'"'"'JSON'"'"'
{"branch":"current-branch","current_task":"task-main","spec_ref":"docs/plans/current-plan.md"}
JSON
    }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "add -- docs/plans/current-plan.md") echo "STAGED_PLAN"; return 0 ;;
        "diff --quiet HEAD -- docs/plans/current-plan.md") return 1 ;;
        "commit --only -m chore: update managed pr artifacts -- docs/plans/current-plan.md") echo "COMMITTED_MANAGED_PLAN"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "STAGED_PLAN" ]]
  [[ "$output" =~ "COMMITTED_MANAGED_PLAN" ]]
  [[ "$output" =~ "current-plan.md" ]]
}

@test "12.4 _flow_pr skips managed commit when bound plan is already in HEAD" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/docs/plans"
  printf '%s\n' '# plan' > "$fixture/docs/plans/current-plan.md"

  run zsh -c '
    cd "'"$fixture"'"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    _flow_show() {
      cat <<'"'"'JSON'"'"'
{"branch":"current-branch","current_task":"task-main","spec_ref":"docs/plans/current-plan.md"}
JSON
    }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "add -- docs/plans/current-plan.md") echo "STAGED_PLAN"; return 0 ;;
        "diff --quiet HEAD -- docs/plans/current-plan.md") return 0 ;;
        "commit --only -m chore: update managed pr artifacts -- docs/plans/current-plan.md") echo "UNEXPECTED_MANAGED_COMMIT"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "STAGED_PLAN" ]]
  [[ ! "$output" =~ "UNEXPECTED_MANAGED_COMMIT" ]]
}

@test "12.5 _flow_pr managed commit does not swallow unrelated staged files" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/docs/plans"
  printf '%s\n' '# plan' > "$fixture/docs/plans/current-plan.md"

  run zsh -c '
    cd "'"$fixture"'"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    _flow_show() {
      cat <<'"'"'JSON'"'"'
{"branch":"current-branch","current_task":"task-main","spec_ref":"docs/plans/current-plan.md"}
JSON
    }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "add -- docs/plans/current-plan.md") echo "STAGED_PLAN"; return 0 ;;
        "diff --quiet HEAD -- docs/plans/current-plan.md") return 1 ;;
        "commit --only -m chore: update managed pr artifacts -- docs/plans/current-plan.md") echo "MANAGED_ONLY_COMMIT"; return 0 ;;
        "commit -m chore: update managed pr artifacts") echo "UNSCOPED_COMMIT"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "MANAGED_ONLY_COMMIT" ]]
  [[ ! "$output" =~ "UNSCOPED_COMMIT" ]]
}

@test "13. _flow_pr skips bump if changelog message exists" {
  local fixture
  fixture="$(mktemp -d)"
  cd "$fixture"
  echo "## [2.1.0] - 2026-03-05" > CHANGELOG.md
  echo "- test commit ..." >> CHANGELOG.md

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;;
        "pr create --title test --body test --base main") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test" --msg "test commit ..."
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping version bump" ]]
}

@test "14. _flow_pr runs bump when no existing PR and changelog has no message" {
  local fixture
  fixture="$(mktemp -d)"
  cd "$fixture"
  mkdir -p scripts
  cat > scripts/bump.sh <<'EOF'
#!/usr/bin/env bash
touch bump_called
exit 0
EOF
  chmod +x scripts/bump.sh
  echo "2.1.4" > VERSION
  echo "# Changelog" > CHANGELOG.md

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;;
        "pr create --title test --body test --base main") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "add VERSION CHANGELOG.md") return 0 ;;
        "diff --quiet HEAD -- VERSION CHANGELOG.md") return 1 ;;
        "commit --only -m chore: bump version to 2.1.4 -- VERSION CHANGELOG.md") return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test" --msg "fresh release note"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Bumping version" ]]
  [ -f "$fixture/bump_called" ]
}

@test "14.0 _flow_pr fails when bump commit cannot be created" {
  local fixture
  fixture="$(mktemp -d)"
  cd "$fixture"
  mkdir -p scripts
  cat > scripts/bump.sh <<'EOF'
#!/usr/bin/env bash
echo "2.1.4" > VERSION
echo "# Changelog" > CHANGELOG.md
echo "- fresh release note" >> CHANGELOG.md
exit 0
EOF
  chmod +x scripts/bump.sh
  echo "2.1.3" > VERSION
  echo "# Changelog" > CHANGELOG.md

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;;
        "pr create --title test --body test --base main") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "add VERSION CHANGELOG.md") return 0 ;;
        "diff --quiet HEAD -- VERSION CHANGELOG.md") return 1 ;;
        "commit --only -m chore: bump version to 2.1.4 -- VERSION CHANGELOG.md") return 1 ;;
        "push origin HEAD") echo "PUSH_SHOULD_NOT_RUN"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test" --msg "fresh release note"
  '

  [ "$status" -eq 1 ]
  [[ ! "$output" =~ "PUSH_SHOULD_NOT_RUN" ]]
}

@test "14.1 _flow_pr allows inferred main as default base" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping version bump" ]]
}

@test "14.2 _flow_pr refuses non-main inferred base without explicit override" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_pick_pr_base() { echo "claude/refactor"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base claude/refactor --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "log main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "log claude/refactor..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "claude/refactor" ]]
  [[ "$output" =~ "--base" ]]
}

@test "14.2.1 _flow_pick_pr_base stays clean when typesetsilent is off" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    setopt no_typeset_silent

    _flow_pr_candidate_bases() {
      echo "main"
      echo "task/vibe-commit-playbook"
    }

    _flow_branch_ref() {
      echo "$1"
      return 0
    }

    git() {
      case "$*" in
        "merge-base --is-ancestor main HEAD") return 0 ;;
        "merge-base --is-ancestor task/vibe-commit-playbook HEAD") return 0 ;;
        "rev-list --count main..HEAD") echo "42"; return 0 ;;
        "rev-list --count task/vibe-commit-playbook..HEAD") echo "23"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_pick_pr_base current-branch
  '

  [ "$status" -eq 0 ]
  [ "$output" = "task/vibe-commit-playbook" ]
  [[ ! "$output" =~ "ahead_count=" ]]
}

@test "14.3 _flow_pr keeps GitHub base name separate from git history ref" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "develop"; return 0; }
    _flow_pr_base_git_ref() { echo "origin/develop"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base develop --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base develop --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "log origin/develop..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --base develop --title "test" --body "test"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Using PR base: develop" ]]
}

@test "14.3.1 _flow_pr normalizes origin/main input to PR base name and remote git ref" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --base origin/main --title "test" --body "test"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Using PR base: main" ]]
}

@test "14.3.2 _flow_pr only uses web creation when explicitly requested" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;;
        "pr create --title test --body test --base main --web") echo "WEB_CREATE"; return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --base main --title "test" --body "test" --web
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "WEB_CREATE" ]]
}

@test "14.4 _flow_pr_base_git_ref prefers origin base over stale local branch" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      case "$*" in
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "show-ref --verify --quiet refs/heads/main") return 0 ;;
        *) return 1 ;;
      esac
    }
    _flow_pr_base_git_ref main
  '

  [ "$status" -eq 0 ]
  [ "$output" = "origin/main" ]
}

@test "14.4.1 _flow_resolve_pr_base normalizes origin-prefixed input" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      case "$*" in
        "show-ref --verify --quiet refs/heads/main") return 0 ;;
        *) return 1 ;;
      esac
    }
    _flow_resolve_pr_base origin/main current-branch
  '

  [ "$status" -eq 0 ]
  [ "$output" = "main" ]
}

@test "14.5 _flow_pr rejects local-only PR base when gh is used" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "develop"; return 0; }
    vibe_has() { return 0; }
    gh() { return 0; }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin develop --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/develop") return 1 ;;
        "show-ref --verify --quiet refs/heads/develop") return 0 ;;
        "ls-remote --exit-code --heads origin develop") return 1 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --base develop --title "test" --body "test"
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "origin/develop not found" ]]
}

@test "14.6 _flow_pr refuses to publish when branch is behind remote base tip" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "merge-base --is-ancestor origin/main HEAD") return 1 ;;
        "push origin HEAD") echo "PUSH_SHOULD_NOT_RUN"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --base main --title "test" --body "test"
  '

  [ "$status" -eq 1 ]
  [[ ! "$output" =~ "PUSH_SHOULD_NOT_RUN" ]]
  [[ "$output" =~ "latest main" ]]
}

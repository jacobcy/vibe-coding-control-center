#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
}

@test "install migrates pending task title as YAML-safe single-line frontmatter" {
  local fixture bin_dir home_dir task_id readme current_dir
  fixture="$(mktemp -d)"
  bin_dir="$fixture/bin"
  home_dir="$fixture/home"
  task_id="2026-03-02-yaml-escape"
  current_dir="$(basename "$fixture")"
  readme="$fixture/docs/tasks/$task_id/README.md"

  mkdir -p "$bin_dir" "$home_dir" "$fixture/.git/vibe/pending-tasks" "$fixture/.git/vibe" "$fixture/docs" "$fixture/skills"

  cat > "$fixture/.git/vibe/worktrees.json" <<JSON
{"schema_version":"v1","worktrees":[{"worktree_name":"$current_dir","worktree_path":"$fixture","current_task":"$task_id"}]}
JSON

  cat > "$fixture/.git/vibe/pending-tasks/$task_id.json" <<'JSON'
{"task_id":"2026-03-02-yaml-escape","title":"Line 1\nO'Brien","status":"todo","assigned_feature":"yaml-escape","source":"pending-task","framework":"vibe"}
JSON

  cat > "$bin_dir/git" <<EOF
#!/usr/bin/env bash
if [[ "\$1 \$2" == "rev-parse --git-common-dir" ]]; then
  echo "$fixture/.git"
  exit 0
fi
exit 1
EOF
  cat > "$bin_dir/npx" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  cat > "$bin_dir/openspec" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$bin_dir/git" "$bin_dir/npx" "$bin_dir/openspec"

  run env HOME="$home_dir" PATH="$bin_dir:$PATH" bash -c 'cd "'"$fixture"'" && bash "'"$VIBE_ROOT"'/install.sh"'

  [ "$status" -eq 0 ]
  [ -f "$readme" ]
  title_line="$(grep '^title:' "$readme")"
  [[ "$title_line" == *"Line 1"* ]]
  [[ "$title_line" == *"O''Brien"* ]]
  [[ "$title_line" != *"O'Brien"* ]]
  [ ! -f "$fixture/.git/vibe/pending-tasks/$task_id.json" ]
}

#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export TMP_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$TMP_HOME/.claude/plugins" "$TMP_HOME/.agents/skills"
  printf '%s\n' '{"plugins":["superpowers@claude-plugins-official"]}' > "$TMP_HOME/.claude/plugins/installed_plugins.json"
  mkdir -p "$TMP_HOME/.agents/skills/brainstorming"

  export TMP_BIN="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$TMP_BIN"
  cat > "$TMP_BIN/npx" <<'SHELL'
#!/usr/bin/env bash
exit 0
SHELL
  chmod +x "$TMP_BIN/npx"
}

@test "vibe skills check is repo-rooted even when run from a subdirectory" {
  run env HOME="$TMP_HOME" PATH="$TMP_BIN:/usr/bin:/bin" bash -lc \
    'cd "'"$REPO_ROOT"'/docs" && HOME="'"$TMP_HOME"'" PATH="'"$TMP_BIN"':/usr/bin:/bin" ../bin/vibe skills check'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "项目级 Skills 同步" ]]
  [[ "$output" =~ ".codex/skills" ]]
  [[ "$output" =~ "Codex:" ]]
}

@test "global agent symlinks skip legacy HOME/.agents/skills mirror" {
  run env HOME="$TMP_HOME" VIBE_ROOT="$REPO_ROOT" zsh -c '
    source "'"$REPO_ROOT"'/lib/config.sh"
    source "'"$REPO_ROOT"'/lib/skills.sh"
    _vibe_skills_sync_agents_symlinks opencode agy
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "跳过 ~/.agents/skills 镜像" ]]
  [ ! -e "$TMP_HOME/.agents/skills/opencode/brainstorming" ]
  [ ! -e "$TMP_HOME/.agents/skills/agy/brainstorming" ]
}

@test "global superpowers sync does not call npx skills" {
  cat > "$TMP_BIN/npx" <<'SHELL'
#!/usr/bin/env bash
echo "network failure" >&2
exit 7
SHELL
  chmod +x "$TMP_BIN/npx"

  run env HOME="$TMP_HOME" PATH="$TMP_BIN:/usr/bin:/bin" VIBE_ROOT="$REPO_ROOT" bash -lc '
    HOME="'"$TMP_HOME"'" PATH="'"$TMP_BIN"':/usr/bin:/bin" VIBE_ROOT="'"$REPO_ROOT"'" \
      zsh -c '"'"'
        source "'"$REPO_ROOT"'/lib/config.sh"
        source "'"$REPO_ROOT"'/lib/skills.sh"
        _vibe_skills_sync_global_superpowers
      '"'"' 2>&1
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "跳过 npx Superpowers sync" ]]
}

# NOTE: Doc-text regression tests have been migrated to tests/doc-text/
# See docs/standards/doc-text-test-governance.md for separation rationale
# Only behavior tests (testing shell commands and their effects) remain here

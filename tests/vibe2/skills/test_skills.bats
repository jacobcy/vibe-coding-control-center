#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/../.."
  export TMP_HOME="$BATS_TEST_TMPDIR/home"
  mkdir -p "$TMP_HOME/.claude/plugins" "$TMP_HOME/.agents/skills" "$TMP_HOME/.trae/skills" "$TMP_HOME/.kiro/skills"
  mkdir -p "$TMP_HOME/.gemini/antigravity/skills"
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
  [[ "$output" =~ "项目级:" ]]
  [[ "$output" =~ "已链接:" ]]
  [[ "$output" =~ "本地 vibe-* skills" ]]
}

@test "global agent symlinks target HOME/.agents/skills for trae and kiro" {
  run env HOME="$TMP_HOME" VIBE_ROOT="$REPO_ROOT" zsh -c '
    source "'"$REPO_ROOT"'/lib/config.sh"
    source "'"$REPO_ROOT"'/lib/skills.sh"
    _vibe_skills_sync_agents_symlinks antigravity trae kiro
    print -r -- "$(readlink "$HOME/.trae/skills/brainstorming")"
    print -r -- "$(readlink "$HOME/.kiro/skills/brainstorming")"
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "$TMP_HOME/.agents/skills/brainstorming" ]]
}

@test "global superpowers sync returns failure when npx skills add fails" {
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

  [ "$status" -eq 1 ]
}

# NOTE: Doc-text regression tests have been migrated to tests/doc-text/
# See docs/standards/doc-text-test-governance.md for separation rationale
# Only behavior tests (testing shell commands and their effects) remain here

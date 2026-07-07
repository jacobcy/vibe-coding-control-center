#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export TMP_BIN="$BATS_TEST_TMPDIR/bin"
  mkdir -p "$TMP_BIN"
}

_write_graphify_stub() {
  local version="$1"

  cat > "$TMP_BIN/graphify" <<EOF
#!/usr/bin/env sh
printf '%s\n' '$version'
EOF
  chmod +x "$TMP_BIN/graphify"
}

_run_graphify_check() {
  env PATH="$TMP_BIN:/usr/bin:/bin" zsh -c '
    source "'$REPO_ROOT'/lib/config.sh"
    source "'$REPO_ROOT'/lib/doctor.sh"
    _doctor_check_tool \
      "graphify" \
      "graphify --version" \
      "uv tool install --force graphifyy==0.9.8" \
      "代码知识图谱" \
      "graphify 0.9.8"
  '
}

_run_doctor_with_graphify_only() {
  env PATH="$TMP_BIN:/usr/bin:/bin" zsh -c '
    source "'$REPO_ROOT'/lib/config.sh"
    source "'$REPO_ROOT'/lib/doctor.sh"
    _doctor_read_config() {
      print -r -- "# REQUIRED_TOOLS
# OPTIONAL_TOOLS
graphify|graphify --version|uv tool install --force graphifyy==0.9.8|代码知识图谱|graphify 0.9.8
# REQUIRED_PLUGINS"
    }
    _doctor_check_plugins() { return 0; }
    vibe_doctor
  '
}

@test "doctor accepts the pinned graphify version" {
  _write_graphify_stub "graphify 0.9.8"

  run _run_graphify_check

  [ "$status" -eq 0 ]
  [[ "$output" == *"graphify 0.9.8"* ]]
}

@test "doctor reports a graphify version mismatch" {
  _write_graphify_stub "graphify 0.9.7"

  run _run_graphify_check

  [ "$status" -eq 1 ]
  [[ "$output" == *"版本不匹配"* ]]
  [[ "$output" == *"graphify 0.9.7"* ]]
  [[ "$output" == *"uv tool install --force graphifyy==0.9.8"* ]]
}

@test "doctor reports missing graphify separately" {
  run _run_graphify_check

  [ "$status" -eq 1 ]
  [[ "$output" == *"未安装"* ]]
  [[ "$output" == *"uv tool install --force graphifyy==0.9.8"* ]]
}

@test "full doctor keeps a graphify mismatch non-blocking" {
  _write_graphify_stub "graphify 0.9.7"

  run _run_doctor_with_graphify_only

  [ "$status" -eq 0 ]
  [[ "$output" == *"版本不匹配"* ]]
  [[ "$output" == *"可选工具缺失 1 个（不影响核心功能）"* ]]
}

@test "full doctor keeps missing graphify non-blocking" {
  run _run_doctor_with_graphify_only

  [ "$status" -eq 0 ]
  [[ "$output" == *"graphify"*"未安装"* ]]
  [[ "$output" == *"可选工具缺失 1 个（不影响核心功能）"* ]]
}

#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/../../.."
}

_write_common_noninteractive_stubs() {
  local bin_dir="$1"

  cat > "$bin_dir/curl" <<'EOF'
#!/usr/bin/env bash
cat <<'INSTALLER'
#!/usr/bin/env sh
set -e
mkdir -p "${UV_INSTALL_DIR:?}"
cat > "${UV_INSTALL_DIR}/uv" <<'UVEOF'
#!/usr/bin/env sh
if [ "$1" = "venv" ]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/pyvenv.cfg"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  [ -n "${TEST_UV_LOG:-}" ] && echo "$*" >> "${TEST_UV_LOG}"
  exit 0
fi
if [ "$1" = "sync" ] || [ "$1" = "tool" ]; then
  [ -n "${TEST_UV_LOG:-}" ] && echo "$*" >> "${TEST_UV_LOG}"
  exit 0
fi
[ -n "${TEST_UV_LOG:-}" ] && echo "$*" >> "${TEST_UV_LOG}"
exit 0
UVEOF
chmod +x "${UV_INSTALL_DIR}/uv"
INSTALLER
EOF

  cat > "$bin_dir/npx" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/pre-commit" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/openspec" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/jq" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF

  chmod +x "$bin_dir/curl" "$bin_dir/npx" "$bin_dir/pre-commit" "$bin_dir/openspec" "$bin_dir/jq"
}

@test "install configures gh non-interactive defaults when gh is available" {
  local fixture home_dir bin_dir gh_log

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  gh_log="$fixture/gh.log"

  mkdir -p "$home_dir" "$bin_dir"

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$TEST_GH_LOG"
exit 0
EOF

  cat > "$bin_dir/direnv" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  hook|allow) exit 0 ;;
  *) exit 0 ;;
esac
EOF

  cat > "$bin_dir/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "venv" ]]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"
  _write_common_noninteractive_stubs "$bin_dir"

  run env HOME="$home_dir" SHELL="/bin/zsh" TEST_GH_LOG="$gh_log" PATH="$bin_dir:$PATH" zsh "$VIBE_ROOT/scripts/install.sh"

  [ "$status" -eq 0 ]
  [ -f "$gh_log" ]
  grep -q '^config set prompt disabled$' "$gh_log"
  grep -q '^config set pager cat$' "$gh_log"
}

@test "install writes stable envrc path and installs alias loader assets" {
  local fixture home_dir bin_dir source_root install_script envrc_path rc_file

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  envrc_path="$source_root/.envrc"
  rc_file="$home_dir/.zshrc"

  mkdir -p "$home_dir" "$bin_dir" "$source_root"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"
  cp -R "$VIBE_ROOT/src" "$source_root/src"
  cp -R "$VIBE_ROOT/supervisor" "$source_root/supervisor"
  cp -R "$VIBE_ROOT/skills" "$source_root/skills"

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/direnv" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  hook|allow) exit 0 ;;
  *) exit 0 ;;
esac
EOF

  cat > "$bin_dir/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "venv" ]]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"
  _write_common_noninteractive_stubs "$bin_dir"

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  [ -f "$envrc_path" ]
  [ -f "$home_dir/.vibe/lib/alias/loader.sh" ]
  grep -Fx 'export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/vibe-center"' "$envrc_path"
  [[ "$(cat "$envrc_path")" != *"$fixture"* ]]
  ! grep -q '^export UV_PROJECT_ENVIRONMENT=' "$rc_file"
  grep -q 'Vibe Center - codeagent-wrapper PATH' "$rc_file"
  grep -q 'export PATH="\$HOME/.claude/bin:\$PATH"' "$rc_file"
  grep -q '# Load Vibe keys' "$rc_file"
  grep -q '\[ -f "'"$home_dir"'/.vibe/loader.sh" \] && source "'"$home_dir"'/.vibe/loader.sh"' "$rc_file"
  grep -q 'command -v direnv >/dev/null 2>&1 && eval "\$(direnv hook zsh)"' "$rc_file"
}

@test "install bootstraps uv into ~/.local/bin and remains idempotent" {
  local fixture home_dir bin_dir source_root install_script rc_file uv_log

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  rc_file="$home_dir/.zshrc"
  uv_log="$fixture/uv.log"

  mkdir -p "$home_dir" "$bin_dir" "$source_root"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"
  cp -R "$VIBE_ROOT/src" "$source_root/src"
  cp -R "$VIBE_ROOT/supervisor" "$source_root/supervisor"
  cp -R "$VIBE_ROOT/skills" "$source_root/skills"
  cat > "$rc_file" <<'EOF'
export VIBE_ROOT_CUSTOM="/tmp/keep-me"
# mention UV_PROJECT_ENVIRONMENT but keep this comment
export UV_PROJECT_ENVIRONMENT_CUSTOM="/tmp/keep-me"
EOF

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  chmod +x "$bin_dir/gh"
  _write_common_noninteractive_stubs "$bin_dir"

  run env HOME="$home_dir" SHELL="/bin/zsh" TEST_UV_LOG="$uv_log" PATH="$bin_dir:$PATH" zsh "$install_script"
  [ "$status" -eq 0 ]
  [ -x "$home_dir/.local/bin/uv" ]
  [ -d "$home_dir/.venvs/vibe-center" ]
  grep -q 'Vibe Local Bin' "$rc_file"
  ! grep -q '^export UV_PROJECT_ENVIRONMENT=' "$rc_file"
  grep -q '^tool install --editable \.$' "$uv_log"
  [ "$(grep -c 'Vibe Center - codeagent-wrapper PATH' "$rc_file")" -eq 1 ]
  [ "$(grep -c '# Load Vibe keys' "$rc_file")" -eq 1 ]
  [ "$(grep -c 'Vibe Coding Control Center - Loader' "$rc_file")" -eq 1 ]
  [ "$(grep -c 'Vibe Direnv Hook' "$rc_file")" -eq 1 ]
  grep -q '^export VIBE_ROOT_CUSTOM="/tmp/keep-me"$' "$rc_file"
  grep -q '^export UV_PROJECT_ENVIRONMENT_CUSTOM="/tmp/keep-me"$' "$rc_file"

  run env HOME="$home_dir" SHELL="/bin/zsh" TEST_UV_LOG="$uv_log" PATH="$bin_dir:$PATH" zsh "$install_script"
  [ "$status" -eq 0 ]
  [ "$(grep -c 'Vibe Local Bin' "$rc_file")" -eq 1 ]
  [ "$(grep -c 'Vibe Center - codeagent-wrapper PATH' "$rc_file")" -eq 1 ]
  [ "$(grep -c '# Load Vibe keys' "$rc_file")" -eq 1 ]
  [ "$(grep -c 'Vibe Coding Control Center - Loader' "$rc_file")" -eq 1 ]
  [ "$(grep -c 'Vibe Direnv Hook' "$rc_file")" -eq 1 ]
  [ "$(grep -c '^tool install --editable \.$' "$uv_log")" -eq 2 ]
  grep -q '^export VIBE_ROOT_CUSTOM="/tmp/keep-me"$' "$rc_file"
  grep -q '^export UV_PROJECT_ENVIRONMENT_CUSTOM="/tmp/keep-me"$' "$rc_file"
}

@test "install writes bash direnv hook when current shell is bash" {
  local fixture home_dir bin_dir source_root install_script rc_file

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  rc_file="$home_dir/.bashrc"

  mkdir -p "$home_dir" "$bin_dir" "$source_root"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"
  cp -R "$VIBE_ROOT/src" "$source_root/src"
  cp -R "$VIBE_ROOT/supervisor" "$source_root/supervisor"
  cp -R "$VIBE_ROOT/skills" "$source_root/skills"

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/direnv" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  hook|allow) exit 0 ;;
  *) exit 0 ;;
esac
EOF

  cat > "$bin_dir/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "venv" ]]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"
  _write_common_noninteractive_stubs "$bin_dir"

  run env HOME="$home_dir" SHELL="/bin/bash" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  grep -q 'command -v direnv >/dev/null 2>&1 && eval "\$(direnv hook bash)"' "$rc_file"
  ! grep -q 'direnv hook zsh' "$rc_file"
}

@test "install recovers from invalid venv by removing and recreating" {
  local fixture home_dir bin_dir source_root install_script venv_dir

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  venv_dir="$home_dir/.venvs/vibe-center"

  mkdir -p "$home_dir" "$bin_dir" "$source_root"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"
  cp -R "$VIBE_ROOT/src" "$source_root/src"
  cp -R "$VIBE_ROOT/supervisor" "$source_root/supervisor"
  cp -R "$VIBE_ROOT/skills" "$source_root/skills"

  # Pre-create an invalid venv (empty directory, no pyvenv.cfg or bin/python)
  mkdir -p "$venv_dir"

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/direnv" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  hook|allow) exit 0 ;;
  *) exit 0 ;;
esac
EOF

  cat > "$bin_dir/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "venv" ]]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  touch "$2/pyvenv.cfg"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"
  _write_common_noninteractive_stubs "$bin_dir"

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  # Check stderr contains the warning message
  [[ "$output" == *"Global venv at $venv_dir is invalid; removing and recreating..."* ]]
  # Check venv was properly recreated
  [ -f "$venv_dir/bin/activate" ]
  [ -f "$venv_dir/pyvenv.cfg" ]
  [ -f "$venv_dir/bin/python" ]
  [ -x "$venv_dir/bin/python" ]
}

@test "install adds ~/.vibe to direnv whitelist prefix" {
  local fixture home_dir bin_dir source_root install_script direnv_conf_dir direnv_conf

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  direnv_conf_dir="$home_dir/.config/direnv"
  direnv_conf="$direnv_conf_dir/direnv.toml"

  mkdir -p "$home_dir" "$bin_dir" "$source_root"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"
  cp -R "$VIBE_ROOT/src" "$source_root/src"
  cp -R "$VIBE_ROOT/supervisor" "$source_root/supervisor"
  cp -R "$VIBE_ROOT/skills" "$source_root/skills"

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/direnv" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  hook|allow) exit 0 ;;
  *) exit 0 ;;
esac
EOF

  cat > "$bin_dir/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "venv" ]]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"
  _write_common_noninteractive_stubs "$bin_dir"

  # Ensure direnv config directory does not exist before test
  [ ! -d "$direnv_conf_dir" ]

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  [ -f "$direnv_conf" ]
  grep -q "prefix = " "$direnv_conf"
  grep -Fq "$home_dir/.vibe" "$direnv_conf"
}

@test "install appends to existing whitelist.prefix" {
  local fixture home_dir bin_dir source_root install_script direnv_conf_dir direnv_conf

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  direnv_conf_dir="$home_dir/.config/direnv"
  direnv_conf="$direnv_conf_dir/direnv.toml"

  mkdir -p "$home_dir" "$bin_dir" "$source_root" "$direnv_conf_dir"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"
  cp -R "$VIBE_ROOT/src" "$source_root/src"
  cp -R "$VIBE_ROOT/supervisor" "$source_root/supervisor"
  cp -R "$VIBE_ROOT/skills" "$source_root/skills"

  # Pre-create direnv.toml with existing prefix
  cat > "$direnv_conf" <<'EOF'
[whitelist]
prefix = ["/tmp/old"]
EOF

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/direnv" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  hook|allow) exit 0 ;;
  *) exit 0 ;;
esac
EOF

  cat > "$bin_dir/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "venv" ]]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"
  _write_common_noninteractive_stubs "$bin_dir"

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  [ -f "$direnv_conf" ]
  grep -Fq "/tmp/old" "$direnv_conf"
  grep -Fq "$home_dir/.vibe" "$direnv_conf"
}

@test "install whitelist prefix entry is idempotent" {
  local fixture home_dir bin_dir source_root install_script direnv_conf_dir direnv_conf before_content

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  direnv_conf_dir="$home_dir/.config/direnv"
  direnv_conf="$direnv_conf_dir/direnv.toml"

  mkdir -p "$home_dir" "$bin_dir" "$source_root" "$direnv_conf_dir"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"
  cp -R "$VIBE_ROOT/src" "$source_root/src"
  cp -R "$VIBE_ROOT/supervisor" "$source_root/supervisor"
  cp -R "$VIBE_ROOT/skills" "$source_root/skills"

  # Pre-create direnv.toml with vibe entry already present
  cat > "$direnv_conf" <<'EOF'
[whitelist]
prefix = ["${HOME}/.vibe"]
EOF
  # Replace ${HOME} with actual home path
  sed -i.bak "s|\${HOME}|$home_dir|g" "$direnv_conf" && rm -f "$direnv_conf.bak"

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

  cat > "$bin_dir/direnv" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  hook|allow) exit 0 ;;
  *) exit 0 ;;
esac
EOF

  cat > "$bin_dir/uv" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "venv" ]]; then
  mkdir -p "$2/bin"
  touch "$2/bin/activate"
  touch "$2/bin/python"
  chmod +x "$2/bin/python"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"
  _write_common_noninteractive_stubs "$bin_dir"

  before_content="$(cat "$direnv_conf")"

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  [ -f "$direnv_conf" ]
  [ "$(cat "$direnv_conf")" == "$before_content" ]
}

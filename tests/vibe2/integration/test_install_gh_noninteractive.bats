#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/../../.."
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
  mkdir -p "$2"
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"

  run env HOME="$home_dir" SHELL="/bin/zsh" TEST_GH_LOG="$gh_log" PATH="$bin_dir:$PATH" zsh "$VIBE_ROOT/scripts/install.sh"

  [ "$status" -eq 0 ]
  [ -f "$gh_log" ]
  grep -q '^config set prompt disabled$' "$gh_log"
  grep -q '^config set pager cat$' "$gh_log"
}

@test "install writes stable envrc path and installs alias loader assets" {
  local fixture home_dir bin_dir source_root install_script envrc_path

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  envrc_path="$source_root/.envrc"

  mkdir -p "$home_dir" "$bin_dir" "$source_root"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"

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
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  [ -f "$envrc_path" ]
  [ -f "$home_dir/.vibe/lib/alias/loader.sh" ]
  grep -Fx 'source "$HOME/.venvs/vibe-center/bin/activate"' "$envrc_path"
  [[ "$(cat "$envrc_path")" != *"$fixture"* ]]
}

@test "install bootstraps uv into ~/.local/bin and remains idempotent" {
  local fixture home_dir bin_dir source_root install_script rc_file

  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  bin_dir="$fixture/bin"
  source_root="$fixture/source"
  install_script="$source_root/scripts/install.sh"
  rc_file="$home_dir/.zshrc"

  mkdir -p "$home_dir" "$bin_dir" "$source_root"
  cp -R "$VIBE_ROOT/bin" "$source_root/bin"
  cp -R "$VIBE_ROOT/lib" "$source_root/lib"
  cp -R "$VIBE_ROOT/config" "$source_root/config"
  cp -R "$VIBE_ROOT/scripts" "$source_root/scripts"

  cat > "$bin_dir/gh" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

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
  exit 0
fi
exit 0
UVEOF
chmod +x "${UV_INSTALL_DIR}/uv"
INSTALLER
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/curl"

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"
  [ "$status" -eq 0 ]
  [ -x "$home_dir/.local/bin/uv" ]
  [ -d "$home_dir/.venvs/vibe-center" ]
  grep -q 'Vibe Local Bin' "$rc_file"
  grep -q '^export UV_PROJECT_ENVIRONMENT=' "$rc_file"

  run env HOME="$home_dir" SHELL="/bin/zsh" PATH="$bin_dir:$PATH" zsh "$install_script"
  [ "$status" -eq 0 ]
  [ "$(grep -c 'Vibe Local Bin' "$rc_file")" -eq 1 ]
  [ "$(grep -c '^export UV_PROJECT_ENVIRONMENT=' "$rc_file")" -eq 1 ]
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
  exit 0
fi
exit 0
EOF

  chmod +x "$bin_dir/gh" "$bin_dir/direnv" "$bin_dir/uv"

  run env HOME="$home_dir" SHELL="/bin/bash" PATH="$bin_dir:$PATH" zsh "$install_script"

  [ "$status" -eq 0 ]
  grep -q 'direnv hook bash' "$rc_file"
  ! grep -q 'direnv hook zsh' "$rc_file"
}

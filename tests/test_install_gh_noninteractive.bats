#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
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

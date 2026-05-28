#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
}

@test "global vibe3 wrapper preserves caller cwd and pins code via --project" {
  local workspace external_repo fake_home fake_bin uv_log
  workspace="$(mktemp -d)"
  external_repo="$workspace/agent-mesh"
  fake_home="$workspace/home"
  fake_bin="$workspace/bin"
  uv_log="$workspace/uv.log"

  mkdir -p "$external_repo/.git" "$fake_home/.vibe" "$fake_bin"
  cp -R "$REPO_ROOT/bin" "$fake_home/.vibe/"
  cp -R "$REPO_ROOT/lib3" "$fake_home/.vibe/"
  cp -R "$REPO_ROOT/config" "$fake_home/.vibe/"
  cp -R "$REPO_ROOT/src" "$fake_home/.vibe/"
  : > "$fake_home/.vibe/config/keys.env"

  cat > "$fake_bin/uv" <<'EOF'
#!/usr/bin/env bash
{
  echo "pwd=$PWD"
  printf 'args='
  printf '%s ' "$@"
  echo
} >> "$UV_LOG"
exit 0
EOF
  chmod +x "$fake_bin/uv"

  run env HOME="$fake_home" PATH="$fake_bin:/usr/bin:/bin" UV_LOG="$uv_log" \
    zsh -c 'cd "'"$external_repo"'" && "$HOME/.vibe/bin/vibe3" flow status'

  [ "$status" -eq 0 ]
  [ -f "$uv_log" ]
  grep -Fx "pwd=$external_repo" "$uv_log"
  grep -F -- "--project $fake_home/.vibe" "$uv_log"
  grep -F -- "$fake_home/.vibe/src/vibe3/cli.py" "$uv_log"
}

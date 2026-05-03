#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../../.." && pwd)"
  export PATH="$REPO_ROOT/bin:$PATH"
  export VIBE_ROOT="$REPO_ROOT"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "global vibe delegates to repo bin/vibe inside a git repo" {
  local fixture home_dir global_root
  fixture="$(mktemp -d)"
  home_dir="$(mktemp -d)"
  global_root="$home_dir/.vibe"
  git -C "$fixture" init >/dev/null 2>&1
  mkdir -p "$fixture/bin" "$global_root/bin"
  cp "$BATS_TEST_DIRNAME/../../../bin/vibe" "$global_root/bin/vibe"
  chmod +x "$global_root/bin/vibe"
  cat > "$fixture/bin/vibe" <<'SH'
#!/usr/bin/env zsh
echo "LOCAL-REPO-VIBE"
SH
  chmod +x "$fixture/bin/vibe"

  run env HOME="$home_dir" zsh -c 'cd "'"$fixture"'" && "'"$global_root"'/bin/vibe" version'
  [ "$status" -eq 0 ]
  [ "$output" = "LOCAL-REPO-VIBE" ]
}

@test "config aliases shim supports installed aliases directory without alias loader" {
  local fixture home_dir config_dir aliases_dir
  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  config_dir="$home_dir/.vibe/config"
  aliases_dir="$config_dir/aliases"

  mkdir -p "$aliases_dir"
  cp "$BATS_TEST_DIRNAME/../../../config/aliases.sh" "$config_dir/aliases.sh"
  cp "$BATS_TEST_DIRNAME/../../../lib/alias/git.sh" "$aliases_dir/git.sh"
  cp "$BATS_TEST_DIRNAME/../../../lib/alias/vibe.sh" "$aliases_dir/vibe.sh"

  run env HOME="$home_dir" zsh -c 'source "'"$config_dir"'/aliases.sh"'
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "lib/alias/loader.sh not found" ]]
}

@test "config shell aliases shim resolves repo root after migration" {
  local repo_root
  repo_root="$BATS_TEST_DIRNAME/../../.."

  run zsh -c 'source "'"$repo_root"'/config/shell/aliases.sh"'
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "no compatible alias loader" ]]
}

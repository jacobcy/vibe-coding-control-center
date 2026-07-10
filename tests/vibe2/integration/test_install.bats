#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/../../.."
}

@test "init installs Codex plugin and links project skills for Claude and Codex" {
  local fixture bin_dir home_dir npx_log codex_log
  fixture="$(mktemp -d)"
  bin_dir="$fixture/bin"
  home_dir="$fixture/home"
  npx_log="$fixture/npx.log"
  codex_log="$fixture/codex.log"

  mkdir -p "$bin_dir" "$home_dir" "$fixture/config/v3" \
    "$fixture/skills/vibe-demo"
  printf '%s\n' '---' 'name: vibe-demo' 'description: test' '---' \
    > "$fixture/skills/vibe-demo/SKILL.md"
  cat > "$fixture/config/v3/skills.json" <<'JSON'
{"global":{"agents":["codex"],"packages":[{"source":"example/caveman","skills":["caveman"]}]},"project":{"agents":["codex","claude-code"],"packages":[]}}
JSON

  cat > "$bin_dir/npx" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$NPX_LOG"
exit 0
SH
  cat > "$bin_dir/codex" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CODEX_LOG"
if [[ "$1 $2" == "plugin list" ]]; then
  exit 0
fi
exit 0
SH
  for command in openspec pre-commit; do
    printf '%s\n' '#!/usr/bin/env bash' 'exit 0' > "$bin_dir/$command"
  done
  chmod +x "$bin_dir/npx" "$bin_dir/codex" "$bin_dir/openspec" "$bin_dir/pre-commit"

  run env HOME="$home_dir" NPX_LOG="$npx_log" CODEX_LOG="$codex_log" PATH="$bin_dir:$PATH" \
    bash -c 'cd "'"$fixture"'" && bash "'"$VIBE_ROOT"'/scripts/init.sh"'

  [ "$status" -eq 0 ]
  grep -F 'plugin marketplace add https://github.com/obra/superpowers.git' "$codex_log"
  grep -F 'plugin add superpowers@superpowers-dev' "$codex_log"
  [ ! -s "$npx_log" ]
  [ -L "$fixture/.claude/skills/vibe-demo" ]
  [ -L "$fixture/.codex/skills/vibe-demo" ]
  [ -L "$fixture/.agent/skills/vibe-demo" ]
  [ "$(readlink "$fixture/.claude/skills/vibe-demo")" = "../../skills/vibe-demo" ]
  [ "$(readlink "$fixture/.codex/skills/vibe-demo")" = "../../skills/vibe-demo" ]
  [ "$(readlink "$fixture/.agent/skills/vibe-demo")" = "../../skills/vibe-demo" ]
}

@test "init installs tracked project extension through local dev source" {
  local fixture bin_dir home_dir specify_log
  fixture="$(mktemp -d)"
  bin_dir="$fixture/bin"
  home_dir="$fixture/home"
  specify_log="$fixture/specify.log"

  mkdir -p "$bin_dir" "$home_dir" \
    "$fixture/.specify/extensions/vibe-spec-bridge" \
    "$fixture/.specify/extensions/superspec" "$fixture/skills"
  cp "$VIBE_ROOT/.specify/extensions/vibe-spec-bridge/extension.yml" \
    "$fixture/.specify/extensions/vibe-spec-bridge/extension.yml"
  touch "$fixture/.specify/extensions/vibe-spec-bridge/.project-owned"
  mkdir -p "$fixture/.specify/extensions/vibe-spec-bridge/.specify-dev"
  touch "$fixture/.specify/extensions/vibe-spec-bridge/.specify-dev/cache"
  cat > "$fixture/.specify/extensions/superspec/extension.yml" <<'YAML'
schema_version: "1.0"
extension:
  id: superspec
  name: External Fixture
  version: "1.0.0"
provides:
  commands: []
hooks: {}
YAML
  cat > "$fixture/.specify/extensions.yml" <<'YAML'
installed:
- superspec
- vibe-spec-bridge
settings:
  auto_execute_hooks: true
hooks: {}
YAML

  for command in npx openspec pre-commit; do
    cat > "$bin_dir/$command" <<'SH'
#!/usr/bin/env bash
exit 0
SH
  done
  cat > "$bin_dir/specify" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$SPECIFY_LOG"
if [[ "$1 $2" == "extension add" && -d "$3/.specify-dev" ]]; then
  exit 2
fi
if [[ "$1 $2 $3" == "extension update vibe-spec-bridge" ]]; then
  exit 1
fi
exit 0
SH
  chmod +x "$bin_dir/npx" "$bin_dir/openspec" "$bin_dir/pre-commit" \
    "$bin_dir/specify"

  run env HOME="$home_dir" SPECIFY_LOG="$specify_log" \
    PATH="$bin_dir:$PATH" bash -c \
    'cd "'"$fixture"'" && bash "'"$VIBE_ROOT"'/scripts/init.sh"'

  if [ "$status" -ne 0 ]; then
    echo "$output" >&2
  fi
  [ "$status" -eq 0 ]
  [[ "$output" == *"spec-kit extension: vibe-spec-bridge"* ]]
  run grep -E '^extension add .+/vibe-spec-bridge --dev --force$' "$specify_log"
  [ "$status" -eq 0 ]
  run grep -F 'extension update superspec' "$specify_log"
  [ "$status" -eq 0 ]
  run grep -E 'extension add .+/superspec --dev --force' "$specify_log"
  [ "$status" -ne 0 ]
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
  cat > "$bin_dir/pre-commit" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$bin_dir/git" "$bin_dir/npx" "$bin_dir/openspec" "$bin_dir/pre-commit"

  run env HOME="$home_dir" PATH="$bin_dir:$PATH" bash -c 'cd "'"$fixture"'" && bash "'"$VIBE_ROOT"'/scripts/init.sh"'

  [ "$status" -eq 0 ]
  [ -f "$readme" ]
  title_line="$(grep '^title:' "$readme")"
  [[ "$title_line" == *"Line 1"* ]]
  [[ "$title_line" == *"O''Brien"* ]]
  [[ "$title_line" != *"O'Brien"* ]]
  [ ! -f "$fixture/.git/vibe/pending-tasks/$task_id.json" ]
}

@test "install rejects unsafe pending task_id path traversal" {
  local fixture bin_dir home_dir unsafe_id current_dir
  fixture="$(mktemp -d)"
  bin_dir="$fixture/bin"
  home_dir="$fixture/home"
  unsafe_id="../../tmp/pwn"
  current_dir="$(basename "$fixture")"

  mkdir -p "$bin_dir" "$home_dir" "$fixture/.git/vibe/pending-tasks" "$fixture/.git/vibe" "$fixture/docs" "$fixture/skills"

  cat > "$fixture/.git/vibe/worktrees.json" <<JSON
{"schema_version":"v1","worktrees":[{"worktree_name":"$current_dir","worktree_path":"$fixture","current_task":"$unsafe_id"}]}
JSON

  cat > "$fixture/.git/vibe/pending-tasks/unsafe.json" <<'JSON'
{"task_id":"../../tmp/pwn","title":"Unsafe Task","status":"todo","assigned_feature":"unsafe","source":"pending-task","framework":"vibe"}
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
  cat > "$bin_dir/pre-commit" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "$bin_dir/git" "$bin_dir/npx" "$bin_dir/openspec" "$bin_dir/pre-commit"

  run env HOME="$home_dir" PATH="$bin_dir:$PATH" bash -c 'cd "'"$fixture"'" && bash "'"$VIBE_ROOT"'/scripts/init.sh"'

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skip pending task with unsafe task_id" ]]
  [ ! -f "$fixture/docs/tasks/../../tmp/pwn/README.md" ]
  [ -f "$fixture/.git/vibe/pending-tasks/unsafe.json" ]
}

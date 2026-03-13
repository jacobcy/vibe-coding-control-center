#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/.."
}

@test "serena project config uses languages list schema" {
  run grep -F "languages:" "$REPO_ROOT/.serena/project.yml"
  [ "$status" -eq 0 ]

  run grep -F -- "- bash" "$REPO_ROOT/.serena/project.yml"
  [ "$status" -eq 0 ]

  run grep -F "language: bash" "$REPO_ROOT/.serena/project.yml"
  [ "$status" -ne 0 ]
}

@test "serena gate bootstraps cold cache via uvx" {
  local fixture home_dir cache_dir bin_dir uvx_log
  fixture="$(mktemp -d)"
  home_dir="$(mktemp -d)"
  cache_dir="$home_dir/cache"
  bin_dir="$fixture/bin"
  uvx_log="$fixture/uvx.log"

  mkdir -p "$fixture/.serena" "$fixture/scripts" "$fixture/.agent/reports" "$bin_dir" "$cache_dir"

  cat > "$fixture/.serena/project.yml" <<'EOF'
project_name: "fixture"
languages:
- bash
EOF

  cat > "$fixture/foo.sh" <<'EOF'
#!/usr/bin/env bash
echo test
EOF

  cat > "$fixture/scripts/serena_gate.py" <<'EOF'
print("stub")
EOF

  cat > "$bin_dir/git" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then
  pwd
  exit 0
fi
exit 1
EOF
  chmod +x "$bin_dir/git"

  cat > "$bin_dir/uvx" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
log_file="${TEST_UVX_LOG:?}"
cache_root="${XDG_CACHE_HOME:?}/uv/archive-v0/bootstrap"
mkdir -p "$cache_root/bin" "$cache_root/lib/python3.11/site-packages/serena/config"
printf '%s\n' "$*" >> "$log_file"
cat > "$cache_root/bin/serena" <<'INNER'
#!/usr/bin/env bash
exit 0
INNER
cat > "$cache_root/bin/python3" <<'INNER'
#!/usr/bin/env bash
python3 - <<'PY'
import json
import os
report_file = os.environ["SERENA_REPORT_FILE"]
target_files = json.loads(os.environ["SERENA_TARGET_FILES_JSON"])
report = {
    "generated_at": "2026-03-13T00:00:00Z",
    "project": os.environ["SERENA_PROJECT_NAME"],
    "base_ref": os.environ["SERENA_BASE_REF"],
    "health_check": {"status": "ok", "log": ""},
    "files": [{"file": path, "status": "ok", "symbols": []} for path in target_files],
    "summary": {"files": len(target_files), "file_errors": 0, "symbol_errors": 0},
}
with open(report_file, "w", encoding="utf-8") as handle:
    json.dump(report, handle)
    handle.write("\n")
print(json.dumps(report))
PY
INNER
cat > "$cache_root/lib/python3.11/site-packages/serena/config/serena_config.py" <<'INNER'
SERENA_HOME = "supported"
INNER
chmod +x "$cache_root/bin/serena" "$cache_root/bin/python3"
exit 0
EOF
  chmod +x "$bin_dir/uvx"

  run env \
    HOME="$home_dir" \
    XDG_CACHE_HOME="$cache_dir" \
    PATH="$bin_dir:/usr/bin:/bin" \
    TEST_UVX_LOG="$uvx_log" \
    bash -c 'cd "'"$fixture"'" && bash "'"$REPO_ROOT"'/scripts/serena_gate.sh" --file foo.sh'

  [ "$status" -eq 0 ]
  [ -f "$uvx_log" ]
  [[ "$output" =~ "Serena gate: wrote" ]]
  [ "$(jq -r '.summary.files' "$fixture/.agent/reports/serena-impact.json")" = "1" ]
}

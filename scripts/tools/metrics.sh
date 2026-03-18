#!/usr/bin/env bash
# scripts/tools/metrics.sh — MSC health metrics dashboard
# Outputs YAML with v2 (Shell) and v3 (Python) metrics separated
#
# Usage:
#   bash scripts/tools/metrics.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Prefer the current git repository root to avoid stale global VIBE_ROOT pollution.
if GIT_ROOT="$(git -C "$SCRIPT_ROOT" rev-parse --show-toplevel 2>/dev/null)"; then
  VIBE_ROOT="$GIT_ROOT"
else
  VIBE_ROOT="${VIBE_ROOT:-$SCRIPT_ROOT}"
fi

echo "# MSC 健康度仪表盘"
echo "# Generated: $(date '+%Y-%m-%d %H:%M %Z')"
echo ""

# ============ v2 (Shell) Metrics ============
echo "v2_shell:"
echo "  total_loc:"
echo "    limit: 7000"
shell_loc=$(find "$VIBE_ROOT/lib" "$VIBE_ROOT/bin" "$VIBE_ROOT/lib3" -name '*.sh' -o -name 'vibe' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
shell_loc_status="pass"
[ "${shell_loc:-0}" -gt 7000 ] && shell_loc_status="fail"
echo "    current: ${shell_loc:-0}"
echo "    usage: $(( (${shell_loc:-0} * 100) / 7000 ))%"
echo "    status: ${shell_loc_status}"

echo "  max_file_loc:"
echo "    limit: 300"
max_shell_loc=0
max_shell_name=""
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$max_shell_loc" ]; then
    max_shell_loc=$lines
    max_shell_name=$(basename "$f")
  fi
done
shell_file_status="pass"
[ "$max_shell_loc" -gt 300 ] && shell_file_status="fail"
echo "    current: ${max_shell_loc}"
echo "    file: ${max_shell_name}"
echo "    status: ${shell_file_status}"

echo "  tests:"
echo "    min_required: 20"
shell_test_count=0
if command -v bats > /dev/null 2>&1; then
  shell_test_count=$(bats --count "$VIBE_ROOT/tests/" 2>/dev/null || echo 0)
fi
shell_test_status="fail"
[ "${shell_test_count:-0}" -ge 20 ] && shell_test_status="pass"
echo "    count: ${shell_test_count}"
echo "    status: ${shell_test_status}"

echo "  shellcheck_errors:"
sc_errors=0
if command -v shellcheck > /dev/null 2>&1; then
  sc_errors=$(shellcheck -s bash -S error "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh "$VIBE_ROOT"/bin/vibe 2>&1 | grep -c "^" || true)
fi
sc_status="pass"
[ "${sc_errors:-0}" -gt 0 ] && sc_status="fail"
echo "    expected: 0"
echo "    count: ${sc_errors}"
echo "    status: ${sc_status}"

echo "  zsh_syntax:"
zsh_status="pass"
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  zsh -n "$f" 2>/dev/null || { zsh_status="fail"; break; }
done
echo "    status: ${zsh_status}"

echo "  dead_code_functions:"
dead_count=0
fn_list=""
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  fn_list="$fn_list $(grep -oE '^[a-zA-Z_][a-zA-Z0-9_]*\(\)' "$f" 2>/dev/null | sed 's/()//')"
done
for fn in $fn_list; do
  [ -z "$fn" ] && continue
  callers=$( { grep -r "$fn" "$VIBE_ROOT/lib" "$VIBE_ROOT/lib3" "$VIBE_ROOT/bin" 2>/dev/null \
    | grep -v "${fn}()" | grep -c "$fn"; } 2>/dev/null || echo 0 )
  callers="${callers//[^0-9]/}"
  callers="${callers:-0}"
  [ "${callers:-0}" -eq 0 ] && dead_count=$((dead_count + 1))
done
dead_status="pass"
[ "$dead_count" -gt 0 ] && dead_status="warning"
echo "    expected: 0"
echo "    count: ${dead_count}"
echo "    status: ${dead_status}"

echo ""

# ============ v3 (Python) Metrics ============
echo "v3_python:"
echo "  total_loc:"
echo "    limit: 9000"
python_loc=$(find "$VIBE_ROOT/src" -name '*.py' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
python_loc_status="pass"
[ "${python_loc:-0}" -gt 7000 ] && python_loc_status="fail"
echo "    current: ${python_loc:-0}"
echo "    usage: $(( (${python_loc:-0} * 100) / 7000 ))%"
echo "    status: ${python_loc_status}"

echo "  max_file_loc:"
echo "    limit: 300"
max_python_loc=0
max_python_name=""
for f in $(find "$VIBE_ROOT/src/vibe3" -name '*.py' 2>/dev/null); do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$max_python_loc" ]; then
    max_python_loc=$lines
    max_python_name=$(basename "$f")
  fi
done
python_file_status="pass"
[ "$max_python_loc" -gt 300 ] && python_file_status="fail"
echo "    current: ${max_python_loc}"
echo "    file: ${max_python_name}"
echo "    status: ${python_file_status}"

echo "  tests:"
echo "    min_required: 5"
python_test_count=0
if command -v pytest > /dev/null 2>&1; then
  python_test_count=$(pytest --collect-only "$VIBE_ROOT/tests/vibe3" 2>/dev/null | grep -c "<Function" || echo 0)
fi
python_test_status="fail"
[ "${python_test_count:-0}" -ge 5 ] && python_test_status="pass"
echo "    count: ${python_test_count}"
echo "    status: ${python_test_status}"

echo "  ruff_lint_errors:"
ruff_errors=0
if command -v ruff > /dev/null 2>&1; then
  ruff_errors=$(ruff check "$VIBE_ROOT/src" 2>&1 | grep -v "^warning" | grep -v "^All checks" | grep -c "^[A-Z]" || true)
fi
ruff_status="pass"
[ "${ruff_errors:-0}" -gt 0 ] && ruff_status="fail"
echo "    expected: 0"
echo "    count: ${ruff_errors}"
echo "    status: ${ruff_status}"

echo ""

# ============ Overall Metrics ============
echo "overall:"
echo "  test_loc:"
test_loc=$(find "$VIBE_ROOT/tests" -name '*.bats' -o -name '*.py' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "    total: ${test_loc:-0}"

echo "  serena_config:"
serena_status="fail"
if [ -f "$VIBE_ROOT/.serena/project.yml" ]; then
  if grep -q "vibe-center" "$VIBE_ROOT/.serena/project.yml" 2>/dev/null; then
    serena_status="pass"
  fi
fi
echo "    status: ${serena_status}"

echo "  cli_spec:"
spec_status="fail"
[ -f "$VIBE_ROOT/openspec/specs/cli-commands.yaml" ] && spec_status="pass"
echo "    status: ${spec_status}"

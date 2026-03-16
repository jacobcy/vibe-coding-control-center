#!/usr/bin/env bash
# scripts/metrics.sh — MSC health metrics dashboard
# Outputs a Markdown table with all MSC compliance indicators

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Prefer the current git repository root to avoid stale global VIBE_ROOT pollution.
if GIT_ROOT="$(git -C "$SCRIPT_ROOT" rev-parse --show-toplevel 2>/dev/null)"; then
  VIBE_ROOT="$GIT_ROOT"
else
  VIBE_ROOT="${VIBE_ROOT:-$SCRIPT_ROOT}"
fi

echo "## 📊 MSC 健康度仪表盘"
echo ""
echo "| 指标 | 上限 | 当前值 | 状态 |"
echo "|------|------|--------|------|"

# --- Total LOC (Shell/v2) ---
shell_loc=$(find "$VIBE_ROOT/lib" "$VIBE_ROOT/bin" "$VIBE_ROOT/lib3" -name '*.sh' -o -name 'vibe' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
shell_loc_status="✅"
[ "${shell_loc:-0}" -gt 7000 ] && shell_loc_status="❌"
echo "| Shell 总 LOC (v2) | 7000 | ${shell_loc:-0} | ${shell_loc_status} $(( (${shell_loc:-0} * 100) / 7000 ))% |"

# --- Total LOC (Python/v3) ---
python_loc=$(find "$VIBE_ROOT/scripts/python" -name '*.py' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
python_loc_status="✅"
[ "${python_loc:-0}" -gt 3000 ] && python_loc_status="❌"
echo "| Python 总 LOC (v3) | 3000 | ${python_loc:-0} | ${python_loc_status} $(( (${python_loc:-0} * 100) / 3000 ))% |"

# --- Total LOC (Tests) ---
test_loc=$(find "$VIBE_ROOT/tests" -name '*.bats' -o -name '*.py' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
echo "| 测试代码 LOC | - | ${test_loc:-0} | 📊 |"

# --- Max file LOC (Shell/v2) ---
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
shell_file_status="✅"
[ "$max_shell_loc" -gt 300 ] && shell_file_status="❌"
echo "| Shell 最大文件行数 (v2) | 300 | ${max_shell_loc} (${max_shell_name}) | ${shell_file_status} |"

# --- Max file LOC (Python/v3) ---
max_python_loc=0
max_python_name=""
for f in $(find "$VIBE_ROOT/scripts/python/vibe3" -name '*.py' 2>/dev/null); do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$max_python_loc" ]; then
    max_python_loc=$lines
    max_python_name=$(basename "$f")
  fi
done
python_file_status="✅"
[ "$max_python_loc" -gt 300 ] && python_file_status="❌"
echo "| Python 最大文件行数 (v3) | 300 | ${max_python_loc} (${max_python_name}) | ${python_file_status} |"

# --- Test count (Shell) ---
shell_test_count=0
if command -v bats > /dev/null 2>&1; then
  shell_test_count=$(bats --count "$VIBE_ROOT/tests/" 2>/dev/null || echo 0)
fi
shell_test_status="❌"
[ "${shell_test_count:-0}" -ge 20 ] && shell_test_status="✅"
echo "| Shell 测试用例数 | ≥20 | ${shell_test_count} | ${shell_test_status} |"

# --- Test count (Python) ---
python_test_count=0
if command -v pytest > /dev/null 2>&1; then
  python_test_count=$(find "$VIBE_ROOT/tests/vibe3" -name 'test_*.py' -exec grep -l "def test_" {} \; 2>/dev/null | wc -l | awk '{print $1}')
fi
python_test_status="❌"
[ "${python_test_count:-0}" -ge 5 ] && python_test_status="✅"
echo "| Python 测试文件数 | ≥5 | ${python_test_count} | ${python_test_status} |"

# --- ShellCheck errors ---
sc_errors=0
if command -v shellcheck > /dev/null 2>&1; then
  sc_errors=$(shellcheck -s bash -S error "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh "$VIBE_ROOT"/bin/vibe 2>&1 | grep -c "^" || true)
fi
sc_status="✅"
[ "${sc_errors:-0}" -gt 0 ] && sc_status="❌"
echo "| ShellCheck errors | 0 | ${sc_errors} | ${sc_status} |"

# --- Zsh syntax check ---
zsh_status="✅"
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  zsh -n "$f" 2>/dev/null || { zsh_status="❌"; break; }
done
echo "| Zsh 语法检查 | PASS | ${zsh_status} | ${zsh_status} |"

# --- Python lint (ruff) ---
ruff_errors=0
if command -v ruff > /dev/null 2>&1; then
  ruff_errors=$(ruff check "$VIBE_ROOT/scripts/python/vibe3" 2>&1 | grep -c "^[A-Z]" || true)
fi
ruff_status="✅"
[ "${ruff_errors:-0}" -gt 0 ] && ruff_status="❌"
echo "| Ruff lint errors | 0 | ${ruff_errors} | ${ruff_status} |"

# --- Dead code (functions defined but never called) ---
dead_count=0
# Collect all function names
fn_list=""
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  fn_list="$fn_list $(grep -oE '^[a-zA-Z_][a-zA-Z0-9_]*\(\)' "$f" 2>/dev/null | sed 's/()//')"
done
for fn in $fn_list; do
  [ -z "$fn" ] && continue
  # Count occurrences excluding the definition line itself
  callers=$( { grep -r "$fn" "$VIBE_ROOT/lib" "$VIBE_ROOT/lib3" "$VIBE_ROOT/bin" 2>/dev/null \
    | grep -v "${fn}()" | grep -c "$fn"; } 2>/dev/null || echo 0 )
  callers="${callers//[^0-9]/}"
  callers="${callers:-0}"
  [ "${callers:-0}" -eq 0 ] && dead_count=$((dead_count + 1))
done
dead_status="✅"
[ "$dead_count" -gt 0 ] && dead_status="⚠️"
echo "| 死代码函数 | 0 | ${dead_count} | ${dead_status} |"

# --- Serena config ---
serena_status="❌"
if [ -f "$VIBE_ROOT/.serena/project.yml" ]; then
  if grep -q "vibe-center" "$VIBE_ROOT/.serena/project.yml" 2>/dev/null; then
    serena_status="✅"
  fi
fi
echo "| Serena 配置 | ✅ | ${serena_status} | ${serena_status} |"

# --- CLI Spec ---
spec_status="❌"
[ -f "$VIBE_ROOT/openspec/specs/cli-commands.yaml" ] && spec_status="✅"
echo "| CLI Spec 覆盖 | ✅ | ${spec_status} | ${spec_status} |"

echo ""
echo "_Generated: $(date '+%Y-%m-%d %H:%M %Z')_"

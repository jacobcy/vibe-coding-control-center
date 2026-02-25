#!/usr/bin/env bash
# scripts/metrics.sh — MSC health metrics dashboard
# Outputs a Markdown table with all MSC compliance indicators

set -e

VIBE_ROOT="${VIBE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

echo "## 📊 MSC 健康度仪表盘"
echo ""
echo "| 指标 | 上限 | 当前值 | 状态 |"
echo "|------|------|--------|------|"

# --- Total LOC ---
total_loc=$(find "$VIBE_ROOT/lib" "$VIBE_ROOT/bin" -name '*.sh' -o -name 'vibe' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
loc_status="✅"
[ "${total_loc:-0}" -gt 1200 ] && loc_status="❌"
echo "| 总 LOC | 1200 | ${total_loc:-0} | ${loc_status} $(( (${total_loc:-0} * 100) / 1200 ))% |"

# --- Max file LOC ---
max_file_loc=0
max_file_name=""
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  lines=$(wc -l < "$f")
  if [ "$lines" -gt "$max_file_loc" ]; then
    max_file_loc=$lines
    max_file_name=$(basename "$f")
  fi
done
file_status="✅"
[ "$max_file_loc" -gt 200 ] && file_status="❌"
echo "| 最大文件行数 | 200 | ${max_file_loc} (${max_file_name}) | ${file_status} |"

# --- Test count ---
test_count=0
if command -v bats > /dev/null 2>&1; then
  test_count=$(bats --count "$VIBE_ROOT/tests/" 2>/dev/null || echo 0)
fi
test_status="❌"
[ "${test_count:-0}" -ge 20 ] && test_status="✅"
echo "| 测试用例数 | ≥20 | ${test_count} | ${test_status} |"

# --- ShellCheck errors ---
sc_errors=0
if command -v shellcheck > /dev/null 2>&1; then
  sc_errors=$(shellcheck -s bash -S error "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/bin/vibe 2>&1 | grep -c "^" || true)
fi
sc_status="✅"
[ "${sc_errors:-0}" -gt 0 ] && sc_status="❌"
echo "| ShellCheck errors | 0 | ${sc_errors} | ${sc_status} |"

# --- Zsh syntax check ---
zsh_status="✅"
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  zsh -n "$f" 2>/dev/null || { zsh_status="❌"; break; }
done
echo "| Zsh 语法检查 | PASS | ${zsh_status} | ${zsh_status} |"

# --- Dead code (functions defined but never called) ---
dead_count=0
# Collect all function names
fn_list=""
for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/bin/vibe; do
  [ -f "$f" ] || continue
  fn_list="$fn_list $(grep -oE '^[a-zA-Z_][a-zA-Z0-9_]*\(\)' "$f" 2>/dev/null | sed 's/()//')"
done
for fn in $fn_list; do
  [ -z "$fn" ] && continue
  # Count occurrences excluding the definition line itself
  callers=$( { grep -r "$fn" "$VIBE_ROOT/lib" "$VIBE_ROOT/bin" 2>/dev/null \
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

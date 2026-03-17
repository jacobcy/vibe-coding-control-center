#!/usr/bin/env bash
# Python 结构摘要 - 使用 grep 和简单解析提取主要结构

# Get the script directory and resolve to repo root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Prefer git root, fallback to script root
if GIT_ROOT="$(git -C "$SCRIPT_ROOT" rev-parse --show-toplevel 2>/dev/null)"; then
  VIBE_ROOT="$GIT_ROOT"
else
  VIBE_ROOT="${VIBE_ROOT:-$SCRIPT_ROOT}"
fi 

echo "# Python (v3) 结构摘要"
echo ""
echo "## 模块结构"
echo ""

for module_dir in "$VIBE_ROOT"/src/vibe3/*/; do
    [ -d "$module_dir" ] || continue
    module_name=$(basename "$module_dir")
    
    echo "### $module_name/"
    
    for file in "$module_dir"/*.py; do
        [ -f "$file" ] || continue
        filename=$(basename "$file")
        
        # 提取类定义
        classes=$(grep "^class " "$file" 2>/dev/null | sed 's/class \([A-Za-z0-9_]*\).*/  - \1 (class)/' || true)
        
        # 提取主要函数（排除私有函数和方法）
        functions=$(grep "^def [a-z]" "$file" 2>/dev/null | sed 's/def \([a-z_]*\).*/  - \1 (function)/' || true)
        
        if [ -n "$classes" ] || [ -n "$functions" ]; then
            echo "  $filename"
            [ -n "$classes" ] && echo "$classes"
            [ -n "$functions" ] && echo "$functions"
        fi
    done
    echo ""
done

echo "## 统计"
echo ""

# 统计模块
module_count=$(find "$VIBE_ROOT/src/vibe3" -type d -mindepth 1 -maxdepth 1 | wc -l | awk '{print $1}')
echo "- 模块数: $module_count"

# 统计文件
file_count=$(find "$VIBE_ROOT/src/vibe3" -name "*.py" | wc -l | awk '{print $1}')
echo "- Python 文件数: $file_count"

# 统计类
class_count=$(grep -r "^class " "$VIBE_ROOT/src/vibe3" 2>/dev/null | wc -l | awk '{print $1}')
echo "- 类定义数: $class_count"

# 统计函数
function_count=$(grep -r "^def " "$VIBE_ROOT/src/vibe3" 2>/dev/null | wc -l | awk '{print $1}')
echo "- 函数定义数: $function_count"

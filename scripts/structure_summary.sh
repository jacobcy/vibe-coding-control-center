#!/usr/bin/env bash
# 统一结构摘要 - 显示 v2 (Shell) 和 v3 (Python) 的主要结构

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if GIT_ROOT="$(git -C "$SCRIPT_ROOT" rev-parse --show-toplevel 2>/dev/null)"; then
  VIBE_ROOT="$GIT_ROOT"
else
  VIBE_ROOT="${VIBE_ROOT:-$SCRIPT_ROOT}"
fi

# Parse arguments
SHOW_HELP=0
VERBOSE=0
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) SHOW_HELP=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [ "$SHOW_HELP" -eq 1 ]; then
  cat <<HELP
Usage: $0 [OPTIONS] [TARGET]

显示 v2 (Shell) 和 v3 (Python) 的代码结构摘要

OPTIONS:
  -h, --help     显示帮助信息
  -v, --verbose  显示详细结构

TARGET:
  不指定          显示所有模块的摘要
  v2              只显示 v2 Shell 结构
  v3              只显示 v3 Python 结构
  <file>          显示指定文件的详细结构

EXAMPLES:
  $0                    # 显示所有模块摘要
  $0 v2                 # 只显示 Shell 结构
  $0 lib/flow.sh        # 显示 flow.sh 文件详细结构
  $0 --verbose          # 显示详细结构

RELATED:
  bash scripts/metrics.sh  # 查看健康度指标
HELP
  exit 0
fi

# Show file structure
show_file() {
  local file="$1"
  [ -f "$file" ] || return 1
  
  local filename=$(basename "$file")
  local lines=$(wc -l < "$file")
  
  echo "📄 $filename ($lines 行)"
  echo ""
  
  if [[ "$file" == *.sh ]]; then
    grep "^[a-z_]*()" "$file" 2>/dev/null | sed 's/\([a-z_]*\)().*/  • \1/' | head -5
    local pub=$(grep "^[a-z_]*()" "$file" 2>/dev/null | wc -l | awk '{print $1}')
    local priv=$(grep "^_[a-z_]*()" "$file" 2>/dev/null | wc -l | awk '{print $1}')
    echo ""
    echo "公共: $pub | 私有: $priv"
  elif [[ "$file" == *.py ]]; then
    grep "^class " "$file" 2>/dev/null | sed 's/class \([A-Za-z0-9_]*\).*/  • \1 (class)/' | head -3
    echo ""
    grep "^def [a-z]" "$file" 2>/dev/null | sed 's/def \([a-z_]*\).*/  • \1/' | head -5
    local cls=$(grep "^class " "$file" 2>/dev/null | wc -l | awk '{print $1}')
    local fn=$(grep "^def " "$file" 2>/dev/null | wc -l | awk '{print $1}')
    echo ""
    echo "类: $cls | 函数: $fn"
  fi
}

# Show module summary
show_module() {
  local name="$1"
  local dir="$2"
  local pattern="$3"
  
  local file_count=$(find "$dir" -name "$pattern" 2>/dev/null | wc -l | awk '{print $1}')
  [ "$file_count" -eq 0 ] && return
  
  echo "📦 $name ($file_count 文件)"
  
  if [ "$VERBOSE" -eq 1 ]; then
    find "$dir" -name "$pattern" 2>/dev/null | sort | while read file; do
      local filename=$(basename "$file")
      local lines=$(wc -l < "$file")
      
      if [[ "$file" == *.sh ]]; then
        local pub=$(grep "^[a-z_]*()" "$file" 2>/dev/null | wc -l | awk '{print $1}')
        local priv=$(grep "^_[a-z_]*()" "$file" 2>/dev/null | wc -l | awk '{print $1}')
        printf "  %-30s %4d 行, %2d 公共, %2d 私有\n" "$filename" "$lines" "$pub" "$priv"
      elif [[ "$file" == *.py ]]; then
        local cls=$(grep "^class " "$file" 2>/dev/null | wc -l | awk '{print $1}')
        local fn=$(grep "^def " "$file" 2>/dev/null | wc -l | awk '{print $1}')
        printf "  %-30s %4d 行, %2d 类, %2d 函数\n" "$filename" "$lines" "$cls" "$fn"
      fi
    done
  else
    find "$dir" -name "$pattern" 2>/dev/null | sort | head -3 | while read file; do
      local filename=$(basename "$file")
      local lines=$(wc -l < "$file")
      echo "  • $filename ($lines 行)"
    done
    [ "$file_count" -gt 3 ] && echo "  ... (+$((file_count - 3)) more)"
  fi
  echo ""
}

# Target file specified
if [ -n "$TARGET" ] && [ -f "$TARGET" ]; then
  show_file "$TARGET"
  exit 0
fi

# Show structure
echo "═══════════════════════════════════════════════════════════════"
echo "                    Vibe Center 代码结构摘要"
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ -z "$TARGET" ] || [ "$TARGET" = "v2" ]; then
  echo "┌─────────────────────────────────────────────────────────────┐"
  echo "│                  v2 - Shell (lib/, lib3/)                  │"
  echo "└─────────────────────────────────────────────────────────────┘"
  echo ""
  
  show_module "lib/" "$VIBE_ROOT/lib" "*.sh"
  
  lib_count=$(ls -1 "$VIBE_ROOT"/lib/*.sh 2>/dev/null | wc -l | awk '{print $1}')
  lib3_count=0
  [ -d "$VIBE_ROOT/lib3" ] && lib3_count=$(ls -1 "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')
  public_count=$(grep -h "^[a-z_]*()" "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')
  private_count=$(grep -h "^_[a-z_]*()" "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')
  
  echo "统计: $lib_count lib + $lib3_count lib3 | $public_count 公共 + $private_count 私有"
  echo ""
fi

if [ -z "$TARGET" ] || [ "$TARGET" = "v3" ]; then
  echo "┌─────────────────────────────────────────────────────────────┐"
  echo "│                  v3 - Python (scripts/python/)                │"
  echo "└─────────────────────────────────────────────────────────────┘"
  echo ""
  
  show_module "vibe3/" "$VIBE_ROOT/scripts/python/vibe3" "*.py"
  
  module_count=$(find "$VIBE_ROOT/scripts/python/vibe3" -type d -mindepth 1 -maxdepth 1 ! -name "__pycache__" 2>/dev/null | wc -l | awk '{print $1}')
  file_count=$(find "$VIBE_ROOT/scripts/python/vibe3" -name "*.py" 2>/dev/null | wc -l | awk '{print $1}')
  class_count=$(grep -r "^class " "$VIBE_ROOT/scripts/python/vibe3" 2>/dev/null | wc -l | awk '{print $1}')
  func_count=$(grep -r "^def " "$VIBE_ROOT/scripts/python/vibe3" 2>/dev/null | wc -l | awk '{print $1}')
  
  echo "统计: $module_count 模块, $file_count 文件 | $class_count 类, $func_count 函数"
  echo ""
fi

echo "提示: 使用 --help 查看选项 | 使用 --verbose 显示详情"
echo "相关: bash scripts/metrics.sh  # 查看健康度指标"

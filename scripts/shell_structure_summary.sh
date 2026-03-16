#!/usr/bin/env bash
# Shell (v2) 结构摘要 - 提取主要函数和结构

VIBE_ROOT="${VIBE_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo '.')}" 

echo "# Shell (v2) 结构摘要"
echo ""
echo "## lib/ 核心库"
echo ""

for file in "$VIBE_ROOT"/lib/*.sh; do
    [ -f "$file" ] || continue
    filename=$(basename "$file")
    
    # 提取公共函数（不以 _ 开头）
    public_funcs=$(grep "^[a-z_]*()" "$file" 2>/dev/null | sed 's/\([a-z_]*\)().*/  - \1 (public)/' || true)
    
    # 提取私有函数（以 _ 开头）
    private_funcs=$(grep "^_[a-z_]*()" "$file" 2>/dev/null | sed 's/\(_[a-z_]*\)().*/  - \1 (private)/' | head -5 || true)
    private_count=$(grep "^_[a-z_]*()" "$file" 2>/dev/null | wc -l | awk '{print $1}')
    
    if [ -n "$public_funcs" ]; then
        echo "### $filename"
        echo "$public_funcs"
        if [ "$private_count" -gt 0 ]; then
            echo "$private_funcs"
            [ "$private_count" -gt 5 ] && echo "  - ... (+$((private_count - 5)) more private functions)"
        fi
        echo ""
    fi
done

echo "## lib3/ 扩展库"
echo ""

if [ -d "$VIBE_ROOT/lib3" ]; then
    for file in "$VIBE_ROOT"/lib3/*.sh; do
        [ -f "$file" ] || continue
        filename=$(basename "$file")
        
        public_funcs=$(grep "^[a-z_]*()" "$file" 2>/dev/null | sed 's/\([a-z_]*\)().*/  - \1 (public)/' || true)
        
        if [ -n "$public_funcs" ]; then
            echo "### $filename"
            echo "$public_funcs"
            echo ""
        fi
    done
fi

echo "## 统计"
echo ""

# 统计文件
lib_count=$(ls -1 "$VIBE_ROOT"/lib/*.sh 2>/dev/null | wc -l | awk '{print $1}')
lib3_count=0
[ -d "$VIBE_ROOT/lib3" ] && lib3_count=$(ls -1 "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')
echo "- lib/ 文件数: $lib_count"
echo "- lib3/ 文件数: $lib3_count"

# 统计函数
public_count=$(grep -h "^[a-z_]*()" "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')
private_count=$(grep -h "^_[a-z_]*()" "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')
echo "- 公共函数数: $public_count"
echo "- 私有函数数: $private_count"

#!/usr/bin/env bash
# 统一结构摘要 - 显示 v2 (Shell) 和 v3 (Python) 的主要结构

VIBE_ROOT="${VIBE_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo '.')}" 

echo "═══════════════════════════════════════════════════════════════"
echo "                    Vibe Center 代码结构摘要"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ============ v2 (Shell) ============
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│                  v2 - Shell (lib/, lib3/)                  │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""

echo "核心模块:"
echo ""

# 主要模块（按功能分组）
declare -A modules
modules=(
  ["flow"]="flow.sh flow_help.sh flow_history.sh flow_list.sh flow_pr.sh flow_review.sh flow_runtime.sh flow_show.sh flow_status.sh"
  ["task"]="task.sh task_actions.sh task_audit.sh task_audit_branches.sh task_audit_checks.sh task_help.sh task_query.sh task_query_openspec.sh task_render.sh task_roadmap_links.sh task_write.sh"
  ["roadmap"]="roadmap.sh roadmap_audit.sh roadmap_dependency.sh roadmap_github_api.sh roadmap_help.sh roadmap_init.sh roadmap_issue_dependency.sh roadmap_issue_intake.sh roadmap_project_sync.sh roadmap_query.sh roadmap_render.sh roadmap_store.sh roadmap_write.sh"
  ["check"]="check.sh check_groups.sh check_groups_link.sh check_pr_status.sh"
  ["skills"]="skills.sh skills_sync.sh"
  ["tool"]="tool.sh"
  ["config"]="alias.sh clean.sh config.sh doctor.sh keys.sh"
)

for module in flow task roadmap check skills tool config; do
    files=${modules[$module]}
    echo "  [$module]"
    
    for file in $files; do
        filepath="$VIBE_ROOT/lib/$file"
        [ -f "$filepath" ] || continue
        
        # 提取公共函数
        public_count=$(grep "^[a-z_]*()" "$filepath" 2>/dev/null | wc -l | awk '{print $1}')
        private_count=$(grep "^_[a-z_]*()" "$filepath" 2>/dev/null | wc -l | awk '{print $1}')
        
        lines=$(wc -l < "$filepath")
        
        echo "    - $file ($lines 行, $public_count 公共, $private_count 私有)"
    done
    echo ""
done

echo ""
echo "统计:"
echo "  - lib/ 文件数: $(ls -1 "$VIBE_ROOT"/lib/*.sh 2>/dev/null | wc -l | awk '{print $1}')"
[ -d "$VIBE_ROOT/lib3" ] && echo "  - lib3/ 文件数: $(ls -1 "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')"
echo "  - 总公共函数: $(grep -h "^[a-z_]*()" "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')"
echo "  - 总私有函数: $(grep -h "^_[a-z_]*()" "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/lib3/*.sh 2>/dev/null | wc -l | awk '{print $1}')"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "                  v3 - Python (scripts/python/)                "
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "模块层次结构:"
echo ""

for module_dir in "$VIBE_ROOT"/scripts/python/vibe3/*/; do
    [ -d "$module_dir" ] || continue
    module_name=$(basename "$module_dir")
    
    # 跳过 __pycache__
    [ "$module_name" = "__pycache__" ] && continue
    
    file_count=$(find "$module_dir" -name "*.py" | wc -l | awk '{print $1}')
    class_count=$(grep -r "^class " "$module_dir" 2>/dev/null | wc -l | awk '{print $1}')
    func_count=$(grep -r "^def " "$module_dir" 2>/dev/null | wc -l | awk '{print $1}')
    
    echo "  $module_name/"
    echo "    文件: $file_count | 类: $class_count | 函数: $func_count"
    
    # 显示主要文件
    for file in "$module_dir"*.py; do
        [ -f "$file" ] || continue
        filename=$(basename "$file")
        
        classes=$(grep "^class " "$file" 2>/dev/null | sed 's/class \([A-Za-z0-9_]*\).*/\1/' | head -3)
        funcs=$(grep "^def [a-z]" "$file" 2>/dev/null | sed 's/def \([a-z_]*\).*/\1/' | head -3)
        
        lines=$(wc -l < "$file")
        
        if [ -n "$classes" ] || [ -n "$funcs" ]; then
            echo "      - $filename ($lines 行)"
            [ -n "$classes" ] && echo "        类: $(echo $classes | tr '\n' ', ' | sed 's/,$//')"
            [ -n "$funcs" ] && echo "        函数: $(echo $funcs | tr '\n' ', ' | sed 's/,$//')"
        fi
    done
    echo ""
done

echo "统计:"
echo "  - 模块数: $(find "$VIBE_ROOT/scripts/python/vibe3" -type d -mindepth 1 -maxdepth 1 ! -name "__pycache__" | wc -l | awk '{print $1}')"
echo "  - Python 文件: $(find "$VIBE_ROOT/scripts/python/vibe3" -name "*.py" | wc -l | awk '{print $1}')"
echo "  - 类定义: $(grep -r "^class " "$VIBE_ROOT/scripts/python/vibe3" 2>/dev/null | wc -l | awk '{print $1}')"
echo "  - 函数定义: $(grep -r "^def " "$VIBE_ROOT/scripts/python/vibe3" 2>/dev/null | wc -l | awk '{print $1}')"

echo ""
echo "═══════════════════════════════════════════════════════════════"

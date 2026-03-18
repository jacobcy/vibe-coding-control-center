#!/usr/bin/env bash
# Vibe Center Skills State Scanner
# 只负责扫描实际状态，生成事实报告

set -e

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT_FILE=".agent/reports/skills-state-${TIMESTAMP}.json"

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       Vibe Center Skills State Scanner${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# 确保报告目录存在
mkdir -p .agent/reports

# 开始生成 JSON 报告
cat > "$REPORT_FILE" << EOF
{
  "scan_time": "$(date -Iseconds)",
  "timestamp": "$TIMESTAMP",
  "global": {
    "claude": {
      "path": "~/.claude/skills/",
      "skills": [
EOF

# 扫描全局 Claude skills
if [ -d "$HOME/.claude/skills" ]; then
    FIRST=true
    for skill in "$HOME/.claude/skills"/*; do
        [ -e "$skill" ] || continue
        name=$(basename "$skill")
        [ "$FIRST" = true ] && FIRST=false || echo "," >> "$REPORT_FILE"
        echo -n "        \"$name\"" >> "$REPORT_FILE"
    done
fi

cat >> "$REPORT_FILE" << EOF

      ],
      "count": $(ls -1 "$HOME/.claude/skills" 2>/dev/null | wc -l | tr -d ' ')
    },
    "agents": {
      "path": "~/.agents/skills/",
      "skills": [
EOF

# 扫描全局 Agents skills
if [ -d "$HOME/.agents/skills" ]; then
    FIRST=true
    for skill in "$HOME/.agents/skills"/*; do
        [ -e "$skill" ] || continue
        name=$(basename "$skill")
        [ "$FIRST" = true ] && FIRST=false || echo "," >> "$REPORT_FILE"
        echo -n "        \"$name\"" >> "$REPORT_FILE"
    done
fi

cat >> "$REPORT_FILE" << EOF

      ],
      "count": $(ls -1 "$HOME/.agents/skills" 2>/dev/null | wc -l | tr -d ' ')
    }
  },
  "project": {
    "agents_local": {
      "path": ".agents/skills/",
      "skills": [
EOF

# 扫描项目级 .agents/skills
if [ -d ".agents/skills" ]; then
    FIRST=true
    for skill in ".agents/skills"/*; do
        [ -e "$skill" ] || continue
        name=$(basename "$skill")
        is_symlink="false"
        [ -L "$skill" ] && is_symlink="true"
        [ "$FIRST" = true ] && FIRST=false || echo "," >> "$REPORT_FILE"
        echo -n "        {\"name\": \"$name\", \"symlink\": $is_symlink}" >> "$REPORT_FILE"
    done
fi

cat >> "$REPORT_FILE" << EOF

      ],
      "count": $(ls -1 ".agents/skills" 2>/dev/null | wc -l | tr -d ' ')
    },
    "agent_skills": {
      "path": ".agent/skills/",
      "skills": [
EOF

# 扫描 .agent/skills
if [ -d ".agent/skills" ]; then
    FIRST=true
    for skill in ".agent/skills"/*; do
        [ -e "$skill" ] || continue
        name=$(basename "$skill")
        is_symlink="false"
        target=""
        [ -L "$skill" ] && { is_symlink="true"; target=$(readlink "$skill"); }
        [ "$FIRST" = true ] && FIRST=false || echo "," >> "$REPORT_FILE"
        echo -n "        {\"name\": \"$name\", \"symlink\": $is_symlink, \"target\": \"$target\"}" >> "$REPORT_FILE"
    done
fi

cat >> "$REPORT_FILE" << EOF

      ],
      "count": $(ls -1 ".agent/skills" 2>/dev/null | wc -l | tr -d ' ')
    },
    "claude_local": {
      "path": ".claude/skills/",
      "skills": [
EOF

# 扫描项目级 .claude/skills
if [ -d ".claude/skills" ]; then
    FIRST=true
    for skill in ".claude/skills"/*; do
        [ -e "$skill" ] || continue
        name=$(basename "$skill")
        is_symlink="false"
        target=""
        [ -L "$skill" ] && { is_symlink="true"; target=$(readlink "$skill"); }
        [ "$FIRST" = true ] && FIRST=false || echo "," >> "$REPORT_FILE"
        echo -n "        {\"name\": \"$name\", \"symlink\": $is_symlink, \"target\": \"$target\"}" >> "$REPORT_FILE"
    done
fi

cat >> "$REPORT_FILE" << EOF

      ],
      "count": $(ls -1 ".claude/skills" 2>/dev/null | wc -l | tr -d ' ')
    },
    "vibe_skills": {
      "path": "skills/",
      "skills": [
EOF

# 扫描 vibe-* skills
if [ -d "skills" ]; then
    FIRST=true
    for skill in skills/vibe-*; do
        [ -d "$skill" ] || continue
        name=$(basename "$skill")
        [ "$FIRST" = true ] && FIRST=false || echo "," >> "$REPORT_FILE"
        echo -n "        \"$name\"" >> "$REPORT_FILE"
    done
fi

cat >> "$REPORT_FILE" << EOF

      ],
      "count": $(ls -1d skills/vibe-* 2>/dev/null | wc -l | tr -d ' ')
    }
  }
}
EOF

echo -e "${GREEN}✓ 扫描完成${NC}"
echo -e "${BLUE}实际状态报告: $REPORT_FILE${NC}"
echo ""
echo -e "${YELLOW}下一步:${NC}"
echo -e "  使用 /vibe-skills-manager 分析差距"
#!/usr/bin/env bash
# 创建 GitHub 标签
# 使用方法: scripts/tools/create-labels.sh

set -euo pipefail

# 标签定义
# 格式: name:color:description
LABELS=(
  "type/feature:#a2eeef:新功能开发"
  "type/fix:#d73a4a:Bug 修复"
  "type/refactor:#fbca04:代码重构"
  "type/docs:#0075ca:文档更新"
  "type/test:#0e8a16:测试相关"
  "type/chore:#fef2c0:杂项改动"
  "priority/high:#b60205:高优先级"
  "priority/medium:#fbca04:中等优先级"
  "priority/low:#c5def5:低优先级"
  "scope/shell:#1d76db:Shell 层改动"
  "scope/skill:#5319e7:Skill 层改动"
  "scope/supervisor:#d93f0b:Supervisor 层改动"
  "scope/infrastructure:#0e8a16:基础设施改动"
  "scope/documentation:#0075ca:文档改动"
  "scope/python:#fbca04:Python 代码改动"
  "scope/shell-script:#c5def5:Shell 脚本改动"
  "status/blocked:#b60205:被阻塞"
  "status/in-progress:#fbca04:进行中"
  "status/ready-for-review:#0e8a16:待审核"
  "status/wip:#c5def5:工作进行中"
  "component/cli:#1d76db:CLI 入口"
  "component/flow:#5319e7:Flow 管理"
  "component/pr:#d93f0b:PR 管理"
  "component/task:#0e8a16:Task 管理"
  "component/logger:#fbca04:Logger 模块"
  "component/client:#c5def5:Client 封装"
  "component/config:#fef2c0:配置管理"
  "breaking-change:#b60205:破坏性变更"
)

# 检查 gh 是否安装
if ! command -v gh &> /dev/null; then
  echo "错误: 未找到 gh CLI"
  echo "请先安装: https://cli.github.com/"
  exit 1
fi

# 检查是否已登录
if ! gh auth status &> /dev/null; then
  echo "错误: 未登录 GitHub"
  echo "请先运行: gh auth login"
  exit 1
fi

echo "开始创建标签..."

# 创建标签
for label_info in "${LABELS[@]}"; do
  IFS=':' read -r name color description <<< "$label_info"

  echo "创建标签: $name"

  # 尝试创建标签，如果已存在则更新
  if gh label create "$name" --color "${color#\#}" --description "$description" 2>/dev/null; then
    echo "  ✓ 已创建: $name"
  else
    echo "  - 标签已存在，更新描述..."
    gh label edit "$name" --color "${color#\#}" --description "$description" 2>/dev/null || true
    echo "  ✓ 已更新: $name"
  fi
done

echo ""
echo "✅ 所有标签创建完成！"
echo ""
echo "标签列表:"
gh label list --limit 50
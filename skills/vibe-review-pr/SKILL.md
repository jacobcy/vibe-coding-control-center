---
name: vibe-review-pr
description: |
  Use when the user wants a comprehensive PR review using multi-agent team workflow.
  Loads team configuration from .claude/team-templates/ and starts phased review.
---

# Vibe PR Review Skill

## 职责

**本 Skill 只负责**：
1. 环境检查
2. 加载 Team Template
3. 启动审查团队

**所有配置和流程定义在**：`.claude/team-templates/pr-review-team.yaml`

---

## Step 1: 环境检查

**必须先检查环境是否支持 Team 功能。**

```bash
# 检查 tmux
echo "TMUX: ${TMUX:-未设置}"

# 检查团队模式
env | grep -i "CLAUDE.*TEAM" || echo "未设置"
```

### 环境要求

| 条件 | 要求 | 不满足时 |
|------|------|----------|
| TMUX | 必须设置 | 提示用户 + 回退到 vibe-review-code |
| CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS | = 1 | 提示用户 + 回退 |

**回退处理**：
```
"Team 功能需要在 tmux session 内运行。
 请运行: tmux new-session -s vibe-review
 然后重新启动 Claude Code。

 当前回退到单 agent 审查模式..."

-> 使用 vibe-review-code
```

不要启动非 tmux team 模式。Team workflow 依赖 tmux panes、SendMessage 和
team cleanup 状态；环境不满足时，直接转入 `vibe-review-code` 单 agent 审查。

---

## Step 2: 加载 Team Template

**读取配置文件**：`.claude/team-templates/pr-review-team.yaml`

```bash
# 加载团队配置
cat .claude/team-templates/pr-review-team.yaml
```

**Template 包含**：
- Agent 定义（model, tools, description）
- PR 类型判断规则
- 工作流程（Phase 1 -> Phase 2 -> Phase 3）
- 防幻觉机制
- 输出格式

---

## Step 3: 判断 PR 类型

根据 Template 中的 `pr_classification` 规则：

| 类型 | 条件 | 流程 |
|------|------|------|
| simple | <50行, 非安全相关 | 单人审查 |
| refactor | 标题含 refactor | standard 流程 |
| security | 安全标签或 fix 标签 | 全流程 + Codex |
| standard | 其他 | standard 流程 |

```bash
gh pr view <number> --json title,labels,additions
```

---

## Step 4: 按流程启动 Agent

**Phase 1（必须先完成）**：
```
PR_BRANCH=$(gh pr view <number> --json headRefName -q .headRefName)

# 仅自动 flow 分支可推断 issue：task/issue-123 或 dev/issue-123。
# 人机合作分支（如 codex/pr-123-*）不自动推断 issue，优先使用 PR body/comments。
if echo "$PR_BRANCH" | grep -qE '^(task|dev)/issue-[0-9]+'; then
  ISSUE_NUM=$(echo "$PR_BRANCH" | grep -oE 'issue-[0-9]+' | grep -oE '[0-9]+')
  gh issue view "$ISSUE_NUM" --comments
else
  echo "issue comments unavailable for non-flow branch: $PR_BRANCH"
  gh pr view <number> --comments
fi

Agent(context-researcher, model=haiku, prompt="收集 PR 背景...")
v 等待 teammate-message
```

**Phase 2（收到背景后）**：
```
SendMessage(to=architect-reviewer, message=背景报告)
Agent(architect-reviewer, model=sonnet, prompt=带背景的prompt)

SendMessage(to=code-analyst, message=背景报告)
Agent(code-analyst, model=haiku, prompt=带背景的prompt)

# 仅安全相关 PR
if security_related:
    Agent(security-reviewer, ...)
```

**Phase 3（综合判断）**：
```
收集结果 -> 差异检测 -> 仲裁 -> 最终决策
```

**Phase 4（写回与改进）**：
```
team-lead 执行：
- write_review_comment -> gh pr comment
- create_follow_up_issues -> 为范围外发现创建 issue（需要去重、标注来源和优先级）
- 不直接提交、amend、push 或修改 PR 分支；需要代码修复时，写明建议并交给后续执行流程
```

**Phase 5（清理与复用准备）**：
```
team-lead 执行：
- 如果继续审查下一个 PR：
  - 清空 inbox 文件（保留 tmux panes）
  - 重置 tasks 状态
- 如果结束本次审查会话：
  - 杀死所有 teammate panes
  - 删除 teams 和 tasks 目录
  - 释放资源
```

---

## Team-lead 控制规则

1. **不同时启动所有 agent**
2. **Phase 1 完成后才启动 Phase 2**
3. **用 SendMessage 传递背景**
4. **差异必须仲裁**

---

## 文件位置

| 文件 | 职责 |
|------|------|
| `skills/vibe-review-pr/SKILL.md` | 本文件：检查和启动 |
| `.claude/team-templates/pr-review-team.yaml` | 团队配置和流程定义 |
| `.claude/agents/pr-*.md` | Agent 详细定义 |
| `docs/references/team-guide.md` | 使用指南 |

---

## 使用方式

```
/vibe-review-pr 604
```

或

```
用 vibe-review-pr 审查 PR #604
```

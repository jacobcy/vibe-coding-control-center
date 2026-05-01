---
name: vibe-review-pr
description: |
  Use when the user wants a comprehensive PR review using multi-agent team workflow.
  Loads team configuration from .claude/team-templates/ and starts phased review.
---

# Vibe PR Review Skill

## 职责

**本 Skill 只负责**：
1. 环境检查与模式选择
2. PR 队列排序与选择
3. 加载 Team Template
4. 启动审查团队

**所有配置和流程定义在**：`.claude/team-templates/pr-review-team.yaml`

---

## Step 1: 环境检查与模式选择

**检查环境是否支持 Team 功能，并决定审查模式。**

```bash
# 检查 tmux
TMUX_STATUS="${TMUX:-未设置}"

# 检查团队模式
TEAM_MODE=$(env | grep -i "CLAUDE.*TEAM" || echo "未设置")
```

### 环境状态判断

| TMUX | TEAM_MODE | 结果 |
|------|-----------|------|
| 已设置 | =1 | tmux 模式可用 |
| 已设置 | 未设置 | 询问是否启用非 tmux 团队审查 |
| 未设置 | =1 | 询问是否启用非 tmux 团队审查 |
| 未设置 | 未设置 | 询问是否启用非 tmux 团队审查 |

**关键改进**：tmux 不可用时，**询问用户**而非直接回退：

```
"检测到 tmux session 未运行或团队模式未启用。

 可选审查模式：
 1. 非 tmux 团队审查（使用 Agent 工具串行启动多个审查 agent）
 2. 单 agent 审查（使用 vibe-review-code skill）

 请选择审查模式 [1/2]？"
```

### 非 tmux 团队审查模式

当用户选择非 tmux 模式时：
- 使用 Agent 工具串行启动审查 agent（Phase 1 → Phase 2 → Phase 3）
- 不使用 SendMessage（因为没有 tmux panes）
- 通过主对话上下文传递信息
- 保留完整的审查流程和仲裁机制

---

## Step 2: PR 队列排序与选择

**检查当前 repo 的所有未合并 PR，排序后确定审查顺序。**

```bash
# 获取所有未合并 PR
gh pr list --state open --json number,title,labels,additions,deletions,baseRefName,headRefName,updatedAt
```

### PR 排序规则

**优先级从高到低**：

1. **merge-ready 状态**：标签含 `state/merge-ready`
2. **最小改动优先**：additions + deletions 行数最小
3. **无依赖优先**：检查 PR 分支是否依赖其他未合并 PR
4. **范围重叠处理**：
   - 复杂 PR（改动更多文件）先审查
   - 简单 PR（改动较少文件）后审查
   - 同一文件的多个改动：先审查改动量大的

### PR 依赖关系检测

```bash
# 检查 PR 分支的 merge base
for each PR:
  gh pr view <number> --json baseRefName,headRefName
  # 如果 baseRefName 不是 main，检查是否依赖其他 PR
```

**依赖判断**：
- `baseRefName == main`：无依赖，优先审查
- `baseRefName == task/issue-xxx`：可能依赖另一个 PR 的分支，需先审查那个 PR

### 用户确认

```
"发现 N 个未合并 PR，按优先级排序：

 [排列表格]

 建议从 PR #xxx 开始审查。是否同意？[y/n]
 或指定要审查的 PR 编号。"
```

---

## Step 3: 加载 Team Template

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

## Step 4: 判断 PR 类型

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

## Step 5: 按流程启动 Agent

**关键改进**：从被审查 PR 的分支推断 issue，而非当前分支。

**Phase 1（必须先完成）**：
```
# 从 PR 分支获取 issue 编号
PR_BRANCH=$(gh pr view <number> --json headRefName -q .headRefName)
ISSUE_NUM=$(echo "$PR_BRANCH" | grep -oE 'issue-[0-9]+' | grep -oE '[0-9]+')

Agent(context-researcher, model=haiku, prompt="收集 PR 背景...")
v 等待 teammate-message
```

**重要**：context-researcher 需要 Bash 工具权限来执行 `gh issue view` 命令。

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
- check_fixable_issues -> 如需修复，提交代码
- create_follow_up_issues -> 为发现但未处理的事项创建 issue
```

### 创建 Follow-up Issue 规则

**当发现以下内容时，应创建 follow-up issue**：

1. **范围外问题**：审查中发现但不属于当前 PR 范围的问题
2. **改进建议**：可优化但非阻塞性的建议
3. **技术债识别**：发现的现有技术债
4. **安全增强**：非紧急但可加强的安全措施

**创建方式**：
```bash
gh issue create --title "<title>" --body "<description>" --label "type/follow-up,scope/<component>"
```

**Issue body 模板**：
```markdown
## 来源
PR #<number> 审查中发现

## 问题描述
[具体描述]

## 建议处理方式
[可选]

## 优先级
- [ ] 高
- [ ] 中
- [ ] 低
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

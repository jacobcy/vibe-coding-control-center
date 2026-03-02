# Skills Handbook

> 自动生成于 2026-03-02 by vibe-skills

## 当前安装概览

| 层级 | 数量 | 说明 |
|------|------|------|
| 项目级 | 27 | 排除流程 skills 后约 14 个 |
| 全局 | 20 | 跨项目通用 |

---

## 项目级 Skills

### OpenSpec 工作流（流程 skills）

| Skill | 用途 | When to use |
|-------|------|-------------|
| openspec-explore | 需求探索模式 | 想法不清晰时，先探索再行动 |
| openspec-new-change | 启动新变更 | 开始一个正式的功能开发 |
| openspec-ff-change | 快速创建变更 | 一次性生成所有 artifacts |
| openspec-continue-change | 继续变更 | 继续未完成的 artifact |
| openspec-apply-change | 实现变更 | 开始写代码实现 |
| openspec-verify-change | 验证实现 | 完成前验证是否匹配 spec |
| openspec-sync-specs | 同步 specs | 将 delta spec 合并到主 spec |
| openspec-archive-change | 归档变更 | 变更完成后归档 |
| openspec-bulk-archive | 批量归档 | 多个变更一起归档 |
| openspec-onboard | 引导入门 | 首次使用 OpenSpec 的教程 |

### Vibe 系（项目专属）

| Skill | 用途 | When to use |
|-------|------|-------------|
| vibe-orchestrator | 流程编排 | 所有改代码动作的主入口 |
| vibe-commit | 智能提交 | 准备 commit 时 |
| vibe-review-code | 代码审查 | PR review 时 |
| vibe-review-docs | 文档审查 | 审计文档/PRD 时 |
| vibe-test-runner | 测试验证 | 代码修改后自动验证 |
| vibe-check | 一致性检查 | 验证项目记忆一致性 |
| vibe-boundary-check | 边界检查 | 开发中检查是否越界 |
| vibe-scope-gate | 范围门禁 | 新功能 start 时检查 |
| vibe-rules-enforcer | 规则执行 | review 时全量合规检查 |
| vibe-drift | 偏离检测 | 定期检测是否偏离初衷 |
| vibe-audit | 项目审计 | 评估项目是否该继续 |
| vibe-save | 保存会话 | 结束会话时保存上下文 |
| vibe-continue | 继续会话 | 恢复之前的工作 |
| vibe-skills | Skills 管理 | 管理 skills 生命周期 |

---

## 全局 Skills（来自 obra/superpowers）

| Skill | 用途 | When to use |
|-------|------|-------------|
| brainstorming | 创意探索 | 任何创造性工作前必用 |
| systematic-debugging | 系统调试 | 遇到 bug/test failure 时 |
| verification-before-completion | 完成验证 | 声称完成前必须验证 |
| test-driven-development | TDD 工作流 | 写功能/修 bug 时 |
| using-git-worktrees | Worktree 隔离 | 多任务并行开发 |
| writing-skills | 创建 skills | 编写新 skill 时 |
| executing-plans | 执行计划 | 有现成计划要执行时 |
| writing-plans | 编写计划 | 需求转化为实现计划 |
| finishing-a-development-branch | 完成分支 | 开发完成后的决策 |
| receiving-code-review | 处理 CR | 收到 review 反馈时 |
| requesting-code-review | 发起 CR | 提交 PR 前 |
| dispatching-parallel-agents | 并行调度 | 多个独立任务并行 |
| subagent-driven-development | 子 Agent 驱动 | 复杂任务拆分执行 |

---

## 支持的 IDE

- **Antigravity** - 纯 Markdown 驱动
- **Trae** - 纯 Markdown 驱动
- **Codex** - 支持
- **Claude Code** - 通过 Plugin 生态（第三方包需用 `claude plugin add`）

---

## 快速参考

```bash
# 查看已安装 skills
npx skills ls        # 项目级
npx skills ls -g     # 全局

# 安装新 skill
npx skills add obra/superpowers --agent antigravity trae codex --skill <name> -y

# 删除 skill
npx skills remove <name> -y
```

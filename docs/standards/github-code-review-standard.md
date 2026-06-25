---
title: GitHub 智能代码审查系统
author: Claude Sonnet 4.6
created_at: 2026-03-17
category: standards
status: active
version: 1.0
related_docs:
  - .github/labeler.yml
  - .github/workflows/ai-pr-review.yml
  - docs/standards/github-labels-standard.md
---

# GitHub 智能代码审查系统

## 概述

基于 PR 标签的智能代码审查系统，自动根据标签类型选择合适的审查策略。

## 审查策略

### 🤖 自动审查

| 标签类型 | 审查方式 | 触发条件 |
|---------|---------|---------|
| `type/feature` + 高影响 scope/component | **Codex AI 审查** | 含 `scope/infrastructure`、`component/cli`、`component/flow` 等核心组件标签时自动触发 |
| `type/feat` + 高影响 scope/component | **Codex AI 审查** | 同上 |
| `type/fix` + 高影响 scope/component | **Copilot AI 审查** | 同上 |
| `type/feature` + 普通范围 | **人工审查** | 不含高影响标签时由人工决定 |
| `type/fix` + 普通范围 | **人工审查** | 同上 |
| `type/refactor` | **跳过在线审查** | 已在本地完成 lint + pytest + bats，CI 自动跳过 |

### ⏸️ 手动审查

| 标签类型 | 审查方式 | 说明 |
|---------|---------|------|
| `type/docs` | **人工审查** | 文档变更，需手动决定是否测试 |
| `type/test` | **人工审查** | 测试变更，需手动决定是否测试 |
| `type/chore` | **人工审查** | 杂项变更，需手动决定是否测试 |

---

## 使用方式

### 1. 正确命名 PR 标题

```bash
# 新功能 → 自动触发 Codex
feat: 添加智能审查系统

# Bug 修复 → 自动触发 Copilot
fix: 修复 PR 创建参数错误

# 重构 → 自动运行本地测试
refactor: 统一 Logger 调用规范

# 文档 → 需要手动决定
docs: 更新智能审查文档

# 测试 → 需要手动决定
test: 添加审查系统测试

# 杂项 → 需要手动决定
chore: 更新依赖版本
```

### 2. 自动标签

Labeler 会根据 PR 分支名前缀自动添加对应的标签：

| 分支前缀 | 标签 |
|----------|------|
| `feat/`, `feature/` | `type/feature` |
| `fix/`, `bugfix/` | `type/fix` |
| `refactor/` | `type/refactor` |
| `docs/`, `documentation/` | `type/docs` |
| `test/`, `testing/` | `type/test` |
| `chore/` | `type/chore` |
| `task/` | `type/task` |

此外，Labeler 还会根据变更文件路径自动附加 `scope/*`、`component/*` 和 `breaking-change` 标签。详见 [labeler.yml](https://github.com/jacobcy/vibe-coding-control-center/blob/main/.github/labeler.yml)。

### 3. 自动审查流程

根据标签组合，`ai-pr-review.yml` 自动裁定审查策略：

#### Codex 审查 (高影响 feature)

1. 当 PR 带 `type/feature` 或 `type/feat` + 高影响 scope/component 标签时触发
2. `determine-strategy` 步骤裁定为 `codex`
3. `codex-review` job 请求 Codex Cloud 开始审查
4. Codex 提交代码审查意见

#### Copilot 审查 (高影响 fix)

1. 当 PR 带 `type/fix` + 高影响 scope/component 标签时触发
2. `determine-strategy` 步骤裁定为 `copilot`
3. `copilot-review` job 请求 Copilot 作为审查者
4. Copilot 提交审查意见

#### 跳过在线审查 (refactor)

1. `determine-strategy` 步骤裁定为 `skip`
2. CI 假定本地已运行 lint (shellcheck/ruff/black/mypy) 和测试 (bats/pytest)

---

## 配置要求

### Codex Cloud 配置

1. 在 [Codex Cloud](https://developers.openai.com/codex/cloud) 中授权仓库
2. 在仓库设置中启用 **Code review**
3. 可选：启用 **Automatic reviews**（会在所有 PR 自动审查）

### GitHub Copilot 配置

1. 确保仓库已启用 GitHub Copilot
2. Copilot 会作为 reviewer 自动响应审查请求

---

## 工作流文件

### `.github/labeler.yml`

自动根据分支名前缀和文件路径添加标签。

### `.github/workflows/ai-pr-review.yml`

根据标签组合触发对应的审查策略（支持 `workflow_dispatch` 手动触发）。

---

## 手动触发审查

如果需要手动触发审查，可以在 PR 中评论：

```bash
# 触发 Codex 审查
@codex review

# 触发 Copilot 审查
# 在 PR 页面手动请求 Copilot 作为审查者
```

---

## 最佳实践

1. **使用标准标题前缀**：确保自动标签正确添加
2. **描述清晰**：标题要能清楚说明改动内容
3. **一个 PR 一个类型**：不要混合多种类型的改动
4. **及时处理审查意见**：AI 审查后及时响应建议

---

## 故障排查

### Codex 没有响应

1. 检查 Codex Cloud 是否已授权仓库
2. 检查是否启用了 Code review
3. 检查评论格式是否正确（`@codex review`）

### Copilot 没有响应

1. 检查仓库是否启用了 Copilot
2. 检查 Copilot 配额是否充足

### 标签没有自动添加

1. 检查 PR 标题格式是否正确
2. 检查 `.github/labeler.yml` 配置

---

## 参考资料

- [配置标准](./configuration-standard.md) - 代码质量限制、审核范围、评分规则
- [Codex GitHub 集成](https://developers.openai.com/codex/integrations/github)
- [GitHub Copilot 代码审查](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/configure-automatic-review)
- [GitHub 标签标准](./github-labels-standard.md)
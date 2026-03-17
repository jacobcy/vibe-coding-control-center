---
document_type: plan
title: Git Commit Hooks for Local CI Validation
issue: "195"
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
status: draft
framework: superpowers
related_docs:
  - .github/workflows/ci.yml
  - scripts/init.sh
---

# Git Commit Hooks Configuration Plan

## 目标

配置 git commit hooks (pre-commit) 在本地运行 CI 检查，防止提交会在远程 CI 失败的代码。

## 背景

当前开发者在 PR 创建后才发现 CI 失败，浪费时间并延迟审查流程。Issue #195 要求在本地提交前运行相同的检查。

## 范围

### 包含

1. ✅ 安装 pre-commit framework
2. ✅ 创建 `.pre-commit-config.yaml` 配置
3. ✅ 映射 `.github/workflows/ci.yml` 中的检查到本地 hooks
4. ✅ 集成到 `scripts/init.sh` 自动安装流程
5. ✅ 提供清晰的错误消息和绕过机制

### 不包含

- ❌ 创建新的检查规则（只复用现有 CI 配置）
- ❌ 修改 CI workflow 本身
- ❌ 强制所有开发者使用（保留 `--no-verify` 绕过选项）

## 执行步骤

### Phase 1: 环境准备

- [ ] **1.1 安装 pre-commit framework**
  - 验证 pre-commit 是否已安装：`pre-commit --version`
  - 若未安装，添加到项目依赖或提供安装说明
  - 更新 `scripts/init.sh` 添加 pre-commit 安装逻辑

### Phase 2: 配置文件创建

- [ ] **2.1 创建 `.pre-commit-config.yaml`**
  - 映射以下 CI 检查到 pre-commit hooks：
    - Shell lint (shellcheck + scripts/hooks/lint.sh)
    - Python lint (ruff, black, mypy)
    - Bats tests (可选，仅对修改 tests/ 时触发)
    - LOC checks (可选，防止代码膨胀)

- [ ] **2.2 配置 hook 触发条件**
  - 使用 `files` 和 `types` 过滤器减少不必要的检查
  - 示例：只在修改 `.sh` 文件时运行 shellcheck

### Phase 3: 集成与测试

- [ ] **3.1 更新 `scripts/init.sh`**
  - 添加 `pre-commit install` 命令
  - 确保在 worktree 初始化时自动安装 hooks

- [ ] **3.2 本地测试**
  - 创建测试提交验证 hooks 正常工作
  - 测试失败场景（故意引入 lint 错误）
  - 测试绕过机制（`git commit --no-verify`）

### Phase 4: 文档与交付

- [ ] **4.1 更新开发者文档**
  - 在 README 或 CONTRIBUTING 中说明 hooks 机制
  - 提供 troubleshooting 指南

- [ ] **4.2 创建 commit 并提交 PR**
  - 使用 `vibe-commit` 创建 PR
  - 确保 PR 描述清晰说明变更范围

## 检查映射表

| CI 检查 | Pre-commit Hook | 触发条件 | 备注 |
|---------|----------------|----------|------|
| shellcheck | `shellcheck` repo hook | `*.sh` files | 直接使用现成 hook |
| lint.sh | `script` hook | `*.sh` files | 需要自定义包装 |
| ruff | `ruff` repo hook | `*.py` files | 使用官方 hook |
| black | `black` repo hook | `*.py` files | 使用官方 hook |
| mypy | `local` script hook | `*.py` files | 需要自定义包装 |
| pytest | `local` script hook | `tests/**/*.py` | 可选，仅在测试修改时触发 |
| bats | `local` script hook | `tests/**/*.bats` | 可选，仅在测试修改时触发 |
| LOC checks | `local` script hook | 所有代码文件 | 可选，防止膨胀 |

## 预期产出

1. `.pre-commit-config.yaml` 文件
2. 更新后的 `scripts/init.sh`
3. 开发者文档更新
4. PR #195-ready commit

## 验收标准

- [ ] `pre-commit run --all-files` 成功通过所有检查
- [ ] 修改 Shell 文件时自动触发 shellcheck 和 lint.sh
- [ ] 修改 Python 文件时自动触发 ruff/black/mypy
- [ ] hooks 可通过 `git commit --no-verify` 绕过
- [ ] 新 worktree 初始化时自动安装 hooks
- [ ] 文档清晰说明使用方法和故障排查

## 风险与缓解

### 风险 1: Hooks 执行时间过长

**缓解**：
- 使用 `files` 过滤器减少不必要的检查
- 将完整测试套件设为可选或仅在 CI 运行
- 提供快速 lint + 完整测试两种模式

### 风险 2: 开发者环境差异

**缓解**：
- 在 `scripts/init.sh` 中检查依赖并提示安装
- 提供清晰的错误消息和修复建议
- 文档中列出所有必需工具

### 风险 3: 绕过机制滥用

**缓解**：
- 保留 `--no-verify` 作为应急选项
- 在 PR template 中提醒检查本地测试
- CI 仍然是最终质量门禁

## 下一步

完成后：
1. 使用 `vibe task update` 标记 task 为 completed
2. 使用 `vibe-commit` 创建 PR
3. 更新 handoff 记录
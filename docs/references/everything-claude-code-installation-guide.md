---
title: Everything Claude Code (ECC) 安装与使用指南
author: Claude Sonnet 4.6
created_at: 2026-03-17
category: guide
status: active
version: 1.0
related_docs:
  - docs/v3/ROADMAP.md
  - README.md
---

# Everything Claude Code (ECC) 安装与使用指南

> 本指南帮助你安装和使用 Everything Claude Code (ECC)，实现高效的并行开发

---

## 📋 目录

1. [ECC 是什么？](#ecc-是什么)
2. [安装步骤](#安装步骤)
3. [核心功能](#核心功能)
4. [并行开发工作流](#并行开发工作流)
5. [实际案例](#实际案例)
6. [故障排查](#故障排查)

---

## 🎯 ECC 是什么？

**Everything Claude Code (ECC)** 是一个**AI Agent Harness 性能优化系统**，提供：

- ✅ **57+ 生产级 Skills** - 覆盖各种开发场景
- ✅ **并行开发能力** - 通过 worktree 和多 agent 协作
- ✅ **内存优化** - Instinct 系统，自动学习和复用模式
- ✅ **安全扫描** - 自动检测配置安全问题
- ✅ **多后端支持** - Codex、Gemini、Claude API

**官方仓库**: https://github.com/affaan-m/everything-claude-code

**Star 数**: 45k+ ⭐

---

## 🚀 安装步骤

### 方式 1: 插件安装（推荐）

```bash
# 1. 安装 ECC 插件
/plugin marketplace add affaan-m/everything-claude-code

# 2. 激活配置 Skill
/configure-ecc
```

### 方式 2: 手动安装

```bash
# 1. 克隆 ECC 仓库
cd ~/.claude
git clone https://github.com/affaan-m/everything-claude-code.git

# 2. 运行安装脚本
cd everything-claude-code
./install.sh typescript

# 3. 重启 Claude Code
# 退出当前 session，重新启动
```

### 方式 3: 选择性安装

如果你只需要特定组件：

```bash
# 克隆仓库
git clone https://github.com/affaan-m/everything-claude-code.git

# 只安装 Skills
cp -r everything-claude-code/skills/* ~/.claude/skills/

# 只安装 Rules
cp -r everything-claude-code/rules/* ~/.claude/rules/

# 只安装 Agents
cp everything-claude-code/agents/*.md ~/.claude/agents/
```

### 验证安装

```bash
# 查看已安装的 Skills
/skills

# 查看 ECC 命令
/help | grep -i ecc
```

---

## 🛠️ 核心功能

### 1. **Skills（技能）**

ECC 提供 57+ Skills，涵盖：

| 分类 | Skills 示例 |
|------|------------|
| **并行开发** | `multi-workflow`, `multi-plan`, `multi-executor` |
| **代码审查** | `python-review`, `go-review`, `kotlin-review` |
| **测试** | `tdd`, `e2e-testing`, `verification-loop` |
| **架构** | `plan`, `architect`, `blueprint` |
| **安全** | `security-review`, `security-scan` |
| **学习** | `learn`, `instinct-status`, `evolve` |

### 2. **Instincts（直觉系统）**

**Instincts** 是 ECC 的核心创新：

- 🧠 **自动学习** - 从你的代码历史中提取模式
- 💾 **持久化存储** - 跨 session 记住编码风格
- 🔄 **持续进化** - 随着使用变得越来越智能
- 📤 **团队共享** - 可以导入导出 instinct 文件

```bash
# 查看学习到的 instincts
/instinct-status

# 导出 instincts 给团队
/instinct-export

# 导入队友的 instincts
/instinct-import
```

### 3. **并行开发工具**

#### 3.1 `codeagent-wrapper`

**作用**: 调用外部 AI 模型（Codex/Gemini）并行分析

**位置**: `~/.claude/bin/codeagent-wrapper`

**安装检查**:
```bash
ls -la ~/.claude/bin/codeagent-wrapper
```

**如果不存在**，需要安装：
```bash
# 安装 ECC 后，运行配置
/configure-ecc

# 或者手动安装
cd ~/.claude/everything-claude-code
./scripts/install-codeagent.sh
```

**使用示例**:
```bash
# 调用 Codex 分析后端代码
codeagent-wrapper --backend codex - "$PWD" <<'EOF'
分析 src/vibe3/services/ 的代码质量
EOF

# 调用 Gemini 分析前端代码
codeagent-wrapper --backend gemini --gemini-model gemini-3-pro-preview - "$PWD" <<'EOF'
分析 UI/UX 设计建议
EOF
```

#### 3.2 Worktree 管理工具

ECC 提供 worktree 管理命令：

```bash
# 创建新 worktree
/worktree-create feature-logger

# 列出所有 worktrees
/worktree-list

# 切换 worktree
/worktree-switch feature-logger

# 清理 worktree
/worktree-cleanup
```

---

## 🔄 并行开发工作流

### 场景 1: 多模块并行开发（适用于独立任务）

**前提条件**: 任务之间无依赖关系

**示例**: 同时开发 Logger 和 Exceptions（如果它们独立）

#### Step 1: 创建多个 Worktrees

```bash
# 主 worktree 保持不动
# 创建 Logger worktree
/worktree-create feature-logger --branch feature/logger

# 创建 Exceptions worktree
/worktree-create feature-exceptions --branch feature/exceptions
```

#### Step 2: 在不同 Worktree 中并行开发

**Terminal 1 (Logger)**:
```bash
cd ~/.claude/worktrees/feature-logger

# 开始开发 Logger
"请实现 observability/logger.py"
```

**Terminal 2 (Exceptions)**:
```bash
cd ~/.claude/worktrees/feature-exceptions

# 开始开发 Exceptions
"请实现 exceptions/ 模块"
```

#### Step 3: 合并结果

```bash
# 提交 PR
cd ~/.claude/worktrees/feature-logger
git push && gh pr create

cd ~/.claude/worktrees/feature-exceptions
git push && gh pr create
```

---

### 场景 2: 多 Agent 协作（推荐用于 Vibe 3.0）

**适用场景**: 任务有依赖关系，但需要不同角色协作

**使用 `/multi-workflow`**:

```bash
/multi-workflow
<任务描述>
```

**工作流程**:

1. **Research Phase** - 收集上下文
2. **Ideation Phase** - Codex（后端）+ Gemini（前端）并行分析
3. **Plan Phase** - Codex + Gemini 并行规划
4. **Execute Phase** - Claude 执行实施
5. **Optimize Phase** - Codex + Gemini 并行审查
6. **Review Phase** - 最终验收

**示例**（Vibe 3.0 Phase 1）:

```bash
/multi-workflow

任务：完成 Phase 1 Infrastructure
1. 实现 observability/logger.py
2. 实现 exceptions/ 模块
3. 为命令添加核心参数集
4. 提升测试覆盖率至 80%
```

**优势**:
- ✅ 保留依赖关系
- ✅ 利用外部模型的专业能力
- ✅ 获得多角度分析和审查

---

### 场景 3: 快速原型验证

**使用 `/blueprint`**:

```bash
# 快速生成实现计划
/blueprint "实现 Logger 系统，支持 verbose 参数"

# Claude 会生成详细计划
# 然后你可以决定是否执行
```

---

## 📚 实际案例

### 案例 1: Vibe 3.0 Phase 1 并行开发

**任务**: 完成 Infrastructure 层的剩余工作

**策略**: 由于任务有依赖，使用 `/multi-workflow` 而非并行 worktree

**执行**:

```bash
/multi-workflow

任务：完成 Vibe 3.0 Phase 1 Infrastructure

Context:
- Phase 1 当前完成 70%
- 需要实现 Logger、Exceptions、核心参数集、测试覆盖率
- Logger 和 Exceptions 是前置依赖
- 测试覆盖率需要等所有模块完成

Requirements:
1. 实现 observability/logger.py
   - 支持 verbose 参数 (0=ERROR, 1=INFO, 2=DEBUG)
   - Agent-centric logging

2. 实现 exceptions/ 模块
   - 统一的 VibeError 层级
   - 所有异常继承 VibeError

3. 为命令添加核心参数集
   - --trace, -v, --json, -y

4. 提升测试覆盖率至 80%
```

**预期流程**:
1. Research: Claude 分析 docs/v3 文档
2. Ideation: Codex 分析后端实现方案
3. Plan: Codex 规划详细实施步骤
4. Execute: Claude 串行实施（因为依赖）
5. Optimize: Codex + Gemini 并行审查
6. Review: 最终验收

---

### 案例 2: 多项目并行维护

**场景**: 同时维护 Vibe 2 和 Vibe 3

**使用 Worktree**:

```bash
# Vibe 2 维护
/worktree-create vibe2-hotfix --branch hotfix/v2-xxx

# Vibe 3 开发
/worktree-create vibe3-feature --branch feature/v3-yyy
```

**在不同终端中工作**:
```bash
# Terminal 1: Vibe 2 热修复
cd ~/.claude/worktrees/vibe2-hotfix
# ... 修复 bug

# Terminal 2: Vibe 3 新功能
cd ~/.claude/worktrees/vibe3-feature
# ... 开发新功能
```

---

## ⚠️ 故障排查

### 问题 1: `codeagent-wrapper: command not found`

**原因**: ECC 未正确安装

**解决**:
```bash
# 重新安装 ECC
/plugin marketplace add affaan-m/everything-claude-code

# 或手动安装
cd ~/.claude/everything-claude-code
./install.sh typescript
```

### 问题 2: Codex/Gemini 调用失败

**原因**: 未配置 API Keys

**解决**:
```bash
# 配置 OpenAI API Key（Codex）
export OPENAI_API_KEY="sk-..."

# 配置 Google API Key（Gemini）
export GOOGLE_API_KEY="..."
```

### 问题 3: Worktree 冲突

**原因**: 多个 worktree 修改同一文件

**解决**:
```bash
# 查看冲突
git status

# 手动解决冲突
git mergetool

# 或者放弃某个 worktree 的修改
git checkout --theirs <file>
```

### 问题 4: Instinct 不生效

**原因**: Instinct 文件未正确加载

**解决**:
```bash
# 检查 instinct 文件
ls -la ~/.claude/instincts/

# 重新加载
/instinct-status

# 如果为空，运行学习
/learn
```

---

## 📖 学习资源

### 官方文档

- **ECC GitHub**: https://github.com/affaan-m/everything-claude-code
- **Claude Code Docs**: https://code.claude.com/docs
- **Skill Directory**: https://www.skillsdirectory.com

### 推荐阅读

1. **Shorthand Guide** - ECC 快速入门
2. **Longform Guide** - Token 优化、内存、并行化详解
3. **Claude Code Ultimate Guide** - 从新手到专家

### 社区

- **Reddit**: r/ClaudeAI
- **Discord**: Claude Code Community
- **GitHub Issues**: ECC 仓库的 Issues

---

## 🎯 下一步

### 立即开始

1. **安装 ECC**
   ```bash
   /plugin marketplace add affaan-m/everything-claude-code
   /configure-ecc
   ```

2. **验证安装**
   ```bash
   /skills
   /instinct-status
   ```

3. **尝试并行工作流**
   ```bash
   /multi-workflow
   完成一个简单的并行任务
   ```

### 用于 Vibe 3.0 开发

根据 [docs/v3/ROADMAP.md](../v3/ROADMAP.md)，推荐：

1. **使用 `/multi-workflow`** - 因为任务有依赖
2. **利用 Codex 审查后端代码**
3. **利用 Gemini 审查文档和 UI**
4. **串行实施，并行审查**

---

## 📌 快速参考卡

### ECC 常用命令

```bash
# 安装
/plugin marketplace add affaan-m/everything-claude-code

# 配置
/configure-ecc

# 并行开发
/multi-workflow <任务>
/multi-plan <计划>
/blueprint <目标>

# Instincts
/instinct-status
/instinct-export
/instinct-import

# Worktrees
/worktree-create <name>
/worktree-list
/worktree-switch <name>

# 代码审查
/python-review
/go-review
/security-review

# 测试
/tdd
/e2e-testing
/verification-loop
```

---

**维护者**: Vibe Team
**最后更新**: 2026-03-17
**版本**: 1.0
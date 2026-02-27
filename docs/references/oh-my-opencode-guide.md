# Oh My OpenCode Agent 系统详解

## 概述

**Oh My OpenCode** 是 OpenCode 的一个插件系统，提供了一套专业化的 AI Agent 架构。这些 Agent 不是简单的 AI 模型，而是带有**特定 Prompt、工具配置和职责定义的角色**，可以根据任务需求选择不同的底层模型（Claude、GPT、Qwen、Gemini 等）。

> 说明：以下内容主要是 OpenCode 侧的 Agent 体系说明。若你采用本仓库的并行 worktree 工作流，请参考下方的「并行 Worktree 协作流程」。

---

## 并行 Worktree 协作流程（推荐）

**核心原则**：每个 agent 在独立 worktree 开发并提交 PR；Claude 固定在 `main` 负责测试、审核与合并。

### 最小可用流程
1. `wtnew <feature> <agent>` 创建 worktree 并设置 Git 身份
2. 在该 worktree 完成修改并提交 PR
3. Claude 在 `main` 拉取并执行测试 + 审核
4. 通过后合并并更新 `CHANGELOG.md`（如影响用户）

### PR 摘要格式（必填）
`变更摘要 | 测试说明 | 风险点`

---

## Agent 类型总览

| Agent | 类型 | 主要职责 | 工作模式 | 默认模型 |
|-------|------|---------|---------|---------|
| **Sisyphus** | Orchestrator (默认) | 智能规划和执行，协调子 Agent | 可选择直接实现或委派 | Claude Opus 4.5 |
| **Atlas** | Master Orchestrator | 复杂多步骤工作流管理 | 完全委派，绝不直接实现 | 可配置 |
| **Hephaestus** | Deep Worker | 深度复杂工程任务 | 专注模式 | 开发中 |
| **Oracle** | Specialist | 高难度调试、架构设计 | 只读咨询 | Claude Sonnet |
| **Librarian** | Specialist | 多仓库分析、外部文档搜索 | 外部资源搜索 | Claude Haiku |
| **Explore** | Specialist | 代码库内部探索 | 上下文感知搜索 | Claude Haiku |

---

## 核心 Agent 详解

### 1. Sisyphus Orchestrator（西西弗斯）

> 命名来源：希腊神话中永恒推石上山的西西弗斯

#### 特点
- **504 行系统 Prompt**，包含完整的任务分类和工作流定义
- **默认 Agent**，处理大多数开发请求
- **智能委派**：简单任务直接处理，复杂任务自动委派给子 Agent
- **TODO 驱动**：使用 `todowrite` 工具管理任务进度

#### 核心工作流（6 阶段）

```
Phase 0: 请求分类
  ↓ 识别任务类型 (Trivial/Explicit/Exploratory/Open-ended)
Phase 1: 代码库评估
  ↓ 判断代码库状态 (Disciplined/Transitional/Legacy/Chaotic)
Phase 2A: 并行执行 (Explore + Librarian)
  ↓ 后台并行搜索
Phase 2B: 实现
  ↓ 编码 + 验证 (lsp_diagnostics)
Phase 2C: 失败恢复
  ↓ 3次失败后咨询 Oracle
Phase 3: 完成
  ↓ 清理背景任务，交付结果
```

#### 委派策略矩阵

| Agent | 成本 | 执行模式 | 使用场景 | 不使用场景 |
|-------|------|---------|---------|-----------|
| **explore** | FREE | 后台并行 | 不熟悉模块、跨层模式发现 | 已知位置、简单任务 |
| **librarian** | CHEAP | 后台并行 | 外部文档、GitHub 示例 | 内部代码库问题 |
| **oracle** | EXPENSIVE | 阻塞同步 | 架构决策、3+次失败后调试 | 探索性工作 |
| **frontend-ui-ux** | MEDIUM | 阻塞同步 | 任何视觉/UI/UX 变更 | 纯逻辑变更 |

#### 配置示例

```json
{
  "agents": {
    "planner-sisyphus": {
      "enabled": true,
      "replace_plan": true,
      "model": "anthropic/claude-opus-4-5",
      "thinking": {
        "type": "enabled",
        "budgetTokens": 32000
      }
    }
  }
}
```

---

### 2. Atlas Orchestrator（阿特拉斯）

> 命名来源：希腊神话中擎天的阿特拉斯

#### 与 Sisyphus 的关键区别

| 特性 | Sisyphus | Atlas |
|------|---------|-------|
| 工作方式 | 可选择直接实现 | **强制委派，绝不直接写代码** |
| 状态管理 | TODO Lists (`todowrite`) | **Notepad 文件系统** (`.sisyphus/notepads/`) |
| 验证机制 | Hook 驱动 | **内置验证协议** |
| 使用场景 | 一般编码任务 | **复杂多步骤项目** |

#### 系统架构（6 部分）

1. **Identity（身份）**
   - 定义为 Master Orchestrator
   - 仅协调，不直接实现
   - 所有工作通过 `delegate_task()` 完成

2. **Mission（使命）**
   - 完成工作计划中的所有任务
   - 通过委派直到完全完成

3. **Orchestration Loop（编排循环）**
   - 任务选择 → 上下文准备 → 委派决策
   - 技能加载 → 执行 → 验证 → 状态更新

4. **Delegation Strategy（委派策略）**
   - **Category**: 领域特定工作（视觉、逻辑等）
   - **Agent**: 需要专业专家时（oracle、librarian）
   - 两者互斥，不能同时使用

5. **Notepad System（笔记本系统）**

```
.sisyphus/notepads/
├── context.md      # 当前任务需求、相关文件、关键模式
├── learnings.md    # 成功经验、发现的模式
├── decisions.md    # 架构选择、决策依据
└── issues.md       # 遇到的错误、失败尝试
```

6. **Verification Protocol（验证协议）**
   - LSP Diagnostics（类型检查、Lint）
   - Build Validation（构建命令）
   - Test Execution（测试套件）
   - Error Recovery（错误恢复）

#### 使用场景
- 多阶段复杂工作流
- 需要跨会话持久状态的项目
- 验证密集型工作（LSP、构建、测试）

---

### 3. Hephaestus（赫菲斯托斯）

> 命名来源：希腊神话中的火神与工匠之神

#### 定位
- **深度工作者 (Deep Worker)**
- 专门处理需要长时间专注的**复杂软件工程任务**
- 目前仍在开发完善中（根据 GitHub Issues）

#### 预期功能
- 深度代码分析和重构
- 复杂算法实现
- 长时间运行的任务处理
- 高精度工程任务

---

## Specialist Agents（专业 Agent）

### Oracle（神谕）

**用途**: 高难度调试、架构决策、代码审查

**特点**:
- 只读咨询，不直接修改代码
- 高 IQ 推理专家
- 昂贵的推理成本
- 在 3+ 次失败后调用

**触发条件**:
- 复杂架构设计
- 完成重要工作后自我审查
- 多次修复失败
- 不熟悉代码模式
- 安全/性能问题

**使用模式**:
```
"Consulting Oracle for [reason]"
```

---

### Librarian（图书管理员）

**用途**: 多仓库分析、外部文档检索

**特点**:
- 搜索**外部资源**（文档、GitHub、开源代码）
- 使用 GitHub CLI、Context7、Web Search
- 适用于不熟悉的库/包
- 低成本

**触发场景**:
- "How do I use [library]?"
- "Find examples of [framework]"
- "Library best practices"
- "Working with unfamiliar npm/pip packages"

**执行方式**:
- 始终后台并行运行
- 与 Explore 同时启动

---

### Explore（探索者）

**用途**: 代码库内部探索

**特点**:
- 搜索**内部代码库**（当前项目）
- 上下文感知的代码搜索
- 发现项目特定的模式和逻辑
- 免费（本地搜索）

**使用场景**:
- 寻找特定功能实现
- 理解项目结构
- 发现现有模式
- 跨层代码分析

**vs Librarian**:
| Contextual Grep (Explore) | Reference Grep (Librarian) |
|--------------------------|---------------------------|
| 搜索当前代码库 | 搜索外部资源 |
| 项目特定逻辑 | 官方 API 文档 |
| 内部模式发现 | 开源实现示例 |

---

## Agent 与模型的关系

### 关键概念

**Agent ≠ 模型**

Agent 是带有特定 Prompt 和工具配置**角色**，可以绑定不同的底层 AI 模型。

### 模型配置

```json
{
  "agents": {
    "sisyphus": {
      "model": "anthropic/claude-opus-4-5",
      "thinking": { "type": "enabled", "budgetTokens": 32000 }
    },
    "atlas": {
      "model": "openai/gpt-5.2",
      "reasoningEffort": "medium",
      "textVerbosity": "high"
    },
    "oracle": {
      "model": "anthropic/claude-sonnet-4-5"
    },
    "librarian": {
      "model": "anthropic/claude-haiku"  // 低成本模型
    }
  }
}
```

### 模型适配

| 模型系列 | 检测方式 | 推理配置 |
|---------|---------|---------|
| **Claude** | 不以 `openai/` 或 `github-copilot/gpt-` 开头 | `thinking: {type: "enabled", budgetTokens: 32000}` |
| **GPT** | 以 `openai/` 或 `github-copilot/gpt-` 开头 | `reasoningEffort: "medium"`, `textVerbosity: "high"` |

---

## 委派系统

### Category + Skills 系统

```typescript
delegate_task(
  category="visual-engineering",  // 领域类别
  load_skills=["frontend-ui-ux"], // 技能注入
  prompt="...",
  run_in_background=true
)
```

### 可用 Categories

| Category | 最佳用途 |
|---------|---------|
| `visual-engineering` | 前端、UI/UX、设计、样式、动画 |
| `ultrabrain` | 超难逻辑任务 |
| `deep` | 深度问题求解 |
| `artistry` | 创意性非传统方案 |
| `quick` | 简单修改 |
| `writing` | 文档、技术写作 |

### Delegation Prompt 结构（7 部分）

```
1. TASK: 原子化、具体的目标
2. EXPECTED OUTCOME: 可交付成果和成功标准
3. REQUIRED SKILLS: 需要调用的技能
4. REQUIRED TOOLS: 显式工具白名单
5. MUST DO: 详尽的要求
6. MUST NOT DO: 禁止的行为
7. CONTEXT: 文件路径、现有模式、约束
```

---

## 实际使用指南

### 切换 Agent

```bash
# 在 OpenCode 交互界面中
# 按 Tab 键循环切换 Primary Agents
# 使用 @agent_name 提及调用 Specialist Agents

@oracle 如何设计这个系统的架构？
@librarian 查找 FastAPI 最佳实践示例
@explore 找到项目中所有使用 useEffect 的地方
```

### 配置位置

```
.opencode/oh-my-opencode.json        # 项目级配置
~/.config/opencode/oh-my-opencode.json  # 用户级配置
```

### 特殊关键词

- `ulw`: 触发 Ultrawork 模式（全自动高强度模式）
- `plan`: 请求创建详细工作计划
- `review`: 请求代码审查

---

## 工作流程示例

### 场景 1: 简单功能实现

```
用户: 添加一个用户登录功能

Sisyphus: 
  1. 分类: Open-ended 任务
  2. 启动 explore + librarian (后台)
  3. 找到现有认证代码
  4. 直接实现或委派给 specialist
  5. 验证 (lsp_diagnostics)
  6. 完成
```

### 场景 2: 复杂重构项目

```
用户: 重构整个前端组件库

Atlas:
  1. 创建 work plan
  2. 初始化 notepad 文件
  3. Loop:
     a. 选择下一个任务
     b. delegate_task(category="visual-engineering")
     c. 等待完成
     d. 验证 (LSP + Build + Test)
     e. 更新 notepad
  4. 所有任务完成
```

### 场景 3: 架构咨询

```
用户: 这个微服务架构应该如何设计？

Sisyphus: 
  "Consulting Oracle for architecture design"
  
Oracle:
  - 提供架构建议
  - 分析 trade-offs
  - 返回详细方案
  
Sisyphus:
  - 基于 Oracle 建议实现
```

---

## 最佳实践

1. **从默认开始**: Sisyphus 适合大多数任务
2. **按需求启用**: 根据工作流需要启用其他 Agent
3. **组合使用**: 不同 Agent 可以协作提供完整方案
4. **项目级配置**: 针对不同项目使用不同的 Agent 设置
5. **合理使用后台任务**: explore/librarian 总是后台并行
6. **验证优先**: 每次修改后运行 `lsp_diagnostics`

---

## 参考资源

- [Oh My OpenCode GitHub](https://github.com/code-yeongyu/oh-my-opencode)
- [Sisyphus Orchestrator 文档](https://deepwiki.com/code-yeongyu/oh-my-opencode/4.2-sisyphus-orchestrator)
- [Atlas Hook 文档](https://deepwiki.com/code-yeongyu/oh-my-opencode/4.3-atlas-hook-and-agent)
- [OpenCode 官方文档](https://opencode.ai/docs)

---

## 总结

**Agent 是角色，模型是引擎。**

- **Sisyphus**: 日常开发，智能规划
- **Atlas**: 复杂项目，强制委派
- **Hephaestus**: 深度工程（开发中）
- **Oracle/Librarian/Explore**: 专业领域支持

通过组合这些 Agent，可以构建强大的 AI 辅助开发工作流。

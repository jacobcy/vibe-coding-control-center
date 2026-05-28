# Claude Code 技能清单（准确版）

生成时间: 2026-05-21

## 系统架构

您有**三个独立的技能系统**：

### 1. Repository-Local Skills (Vibe Center)
- **目录**: `skills/`
- **定位**: 项目特有的自动化流程、治理与协作技能
- **状态**: 核心运行时技能
- **技能数**: 22 个

### 2. Everything Claude Code (ECC) 系统
- **目录**: `~/.claude/skills/`
- **定位**: 全面的技能和规则集合
- **状态**: 活跃维护
- **技能数**: 37 个

### 3. Superpowers 系统
- **目录**: `~/.agents/skills/`
- **定位**: 基础代理工作流框架
- **状态**: 活跃（不是"旧版"或"已弃用"）
- **技能数**: 18 个

**重要**: 这三个系统是**互补的**，不是替代关系。Vibe Skills 关注本项目 V3 运行时的自动化，Superpowers 关注通用工作流程，ECC 关注通用技术实现。

---

## 目录加载优先级

```
Skills:
  1. skills/              ← Vibe 本地技能（本项目最高优先级）
  2. ~/.claude/skills/    ← ECC 技能
  3. .claude/skills/      ← 项目级覆盖
  4. ~/.agents/skills/    ← Superpowers 技能

Agents:
  1. ~/.claude/agents/    ← ECC 代理
  2. .claude/agents/      ← 项目级覆盖

Rules:
  1. ~/.claude/rules/     ← ECC 规则
  2. .claude/rules/       ← 项目级规则
```

---

## Vibe 本地技能 (skills/)

### 开发与协作 (7 个)

| Skill | 功能描述 |
|-------|---------|
| `vibe-new` | 启动新任务，绑定 issue，同步 flow 现场 |
| `vibe-continue` | 恢复现有任务，加载 handoff 上下文 |
| `vibe-commit` | 提交代码，处理 pre-commit 格式化，创建/更新 PR |
| `vibe-integrate` | 评估 PR 状态，处理合并冲突与依赖 |
| `vibe-done` | 完成任务，关闭 issue，清理现场 |
| `vibe-save` | 保存当前 session 上下文，记录 handoff |
| `vibe-closeout` | 执行 flow 终端清理（由 manager 调度） |

### 治理与巡检 (8 个)

| Skill | 功能描述 |
|-------|---------|
| `vibe-check` | 审计 task-flow 状态，同步 metadata，修复同步错误 |
| `vibe-orchestra` | Issue 池治理，心跳调度，分配任务 |
| `vibe-roadmap` | 路线图规划，版本目标管理，Issue 分组 |
| `vibe-issue` | 创建、修补或去重 GitHub Issue |
| `vibe-rules` | 治理项目规则文件，防止冗余或冲突 |
| `vibe-skill-audit` | 审查与更新项目本地技能定义 |
| `vibe-redundancy-audit` | 发现业务逻辑或代码中的冗余实现 |
| `vibe-skills-manager` | 管理跨项目与本地技能的同步与加载 |

### 评审与引导 (4 个)

| Skill | 功能描述 |
|-------|---------|
| `vibe-review-code` | 源码实现结构化评审 |
| `vibe-review-docs` | 文档质量、变更日志与语义一致性评审 |
| `vibe-team-review` | 多 agent 协作审查（支持 PR、代码、架构等） |
| `vibe-onboard` | 安装后的入门引导与系统检查 |

### 调试与监控 (3 个)

| Skill | 功能描述 |
|-------|---------|
| `vibe-instruction` | 项目元指令，提供架构与命令概览 |
| `vibe-debug-serve` | 调试 vibe3 serve (orchestra) 运行时 |
| `vibe-task` | 跨工作区任务流状态查询与切换建议 |

**Vibe 总计**: 22 个技能

---

## ECC 技能系统 (~/.claude/skills/)

### 核心开发技能 (7 个)

| Skill | 功能描述 |
|-------|---------|
| `api-design` | REST API 设计模式，资源命名、版本控制 |
| `backend-patterns` | 后端架构模式，服务端最佳实践 |
| `coding-standards` | 通用编码标准 |
| `frontend-patterns` | React/Next.js 状态管理、性能优化 |
| `frontend-slides` | 零依赖 HTML 演示文稿 |
| `tdd-workflow` | 测试驱动开发，RED-GREEN-REFACTOR |
| `verification-loop` | 验证系统，代码质量循环检查 |

### Python 专项 (2 个)

| Skill | 功能描述 |
|-------|---------|
| `python-patterns` | Pythonic 模式、PEP 8、类型提示 |
| `python-testing` | pytest、TDD、fixtures、mocking |

### 内容创作 (6 个)

| Skill | 功能描述 |
|-------|---------|
| `article-writing` | 长篇写作、博客、教程 |
| `content-engine` | 多平台社交内容 |
| `crosspost` | 多平台内容分发 |
| `investor-materials` | 融资材料、演示文稿 |
| `investor-outreach` | 投资者联系、冷邮件 |
| `market-research` | 市场调研、竞争分析 |

### 研究工具 (4 个)

| Skill | 功能描述 |
|-------|---------|
| `search-first` | 编码前研究工作流 |
| `deep-research` | 多源深度研究 |
| `exa-search` | 神经搜索 MCP |
| `documentation-lookup` | 库和框架文档查询 |

### 安全与质量 (3 个)

| Skill | 功能描述 |
|-------|---------|
| `security-review` | 安全检查清单 |
| `eval-harness` | 形式化评估框架 |
| `strategic-compact` | 手动上下文压缩 |

### 多媒体 (2 个)

| Skill | 功能描述 |
|-------|---------|
| `fal-ai-media` | AI 媒体生成 MCP |
| `video-editing` | AI 辅助视频编辑 |

### AI 集成 (2 个)

| Skill | 功能描述 |
|-------|---------|
| `claude-api` | Anthropic Claude API 模式 |
| `x-api` | X/Twitter API 集成 |

### 运行时与工具 (4 个)

| Skill | 功能描述 |
|-------|---------|
| `bun-runtime` | Bun 运行时和包管理器 |
| `nextjs-turbopack` | Next.js 16+ 和 Turbopack |
| `dmux-workflows` | dmux 多代理编排 |
| `mcp-server-patterns` | MCP 服务器模式 |

### 内置工具 (7 个)

| Skill | 功能描述 |
|-------|---------|
| `browser` | 浏览器自动化 |
| `codeagent` | 多后端 AI 代码生成 |
| `harness` | 多会话代理工具 |
| `learned` | 学习的模式存储 |
| `omo` | 多代理系统 |
| `skill-install` | 安装 Claude 技能 |
| `e2e-testing` | Playwright E2E 测试 |

**ECC 总计**: 37 个技能

---

## Superpowers 技能系统 (~/.agents/skills/)

### 核心工作流技能 (18 个)

| Skill | 功能描述 |
|-------|---------|
| `using-superpowers` | **入口技能** - 如何查找和使用技能 |
| `writing-plans` | 编写实现计划 |
| `executing-plans` | 执行已定义的计划 |
| `writing-skills` | 创建新技能 |
| `skill-creator` | 技能创建工具 |
| `find-skills` | 查找相关技能 |
| `test-driven-development` | 测试驱动开发流程 |
| `systematic-debugging` | 系统化调试方法 |
| `brainstorming` | 头脑风暴和方案探索 |
| `subagent-driven-development` | 子代理驱动开发 |
| `dispatching-parallel-agents` | 并行代理调度 |
| `agent-browser` | 浏览器自动化代理 |
| `using-git-worktrees` | Git worktree 工作流 |
| `finishing-a-development-branch` | 完成开发分支 |
| `requesting-code-review` | 请求代码审查 |
| `receiving-code-review` | 处理代码审查反馈 |
| `verification-before-completion` | 完成前验证 |
| `web-design-guidelines` | Web 设计指南 |

### Superpowers 核心原则

来自 `~/.agents/AGENTS.md`:

1. **语言规则**
   - 内部推理、代码、commit message: 英文
   - 面向用户回复: 中文

2. **Session 分离**
   - 讨论 Session: 分析、规划（禁止修改代码）
   - 执行 Session: 按计划实施（禁止重新讨论）

3. **变更控制**
   - 只改用户要求改的
   - 超过 5 个文件需确认
   - 一个 commit 对应一个逻辑变更

4. **验证纪律**
   - 禁止未验证就宣称完成

**Superpowers 总计**: 18 个技能

---

## 推荐工作流

### 场景 1: 新功能开发

```bash
# 1. 使用 Superpowers 规划
/writing-plans <功能需求>

# 2. 使用 ECC 研究技术
/search-first <技术调研>

# 3. 使用 ECC TDD 实现
/tdd-workflow

# 4. 使用 Superpowers 验证
/verification-before-completion

# 5. 使用 ECC 审查
/code-review
/security-review  # 如需要
```

### 场景 2: Bug 修复

```bash
# 1. 使用 Superpowers 调试
/systematic-debugging

# 2. 使用 ECC TDD 修复
/tdd-workflow

# 3. 使用 Superpowers 验证
/verification-before-completion
```

### 场景 3: Python 项目

```bash
# 1. 使用 ECC Python 技能
/python-patterns
/python-testing

# 2. 使用 Superpowers 工作流
/writing-plans
/executing-plans

# 3. 使用 ECC 审查
/python-review
```

---

## 两者的定位差异

### Superpowers 优势

- **流程驱动**: Plan → Execute → Verify
- **讨论分离**: 防止分析和实现混淆
- **工作流完整**: 从规划到完成的全流程
- **代理协作**: 并行代理、子代理模式

### ECC 优势

- **技术深度**: 语言/框架专项最佳实践
- **内容创作**: 写作、营销、研究工具
- **生态集成**: API、媒体、数据库
- **质量保证**: 安全审查、性能优化

---

## 常见误解澄清

- **两个系统是独立的**，设计目标不同
- **Superpowers** = 工作流程方法论
- **ECC** = 技术实现细节
- **最佳实践** = 两者结合使用

---

## 统计信息

### 按系统统计

- **Vibe 技能**: 22 个 (Repository-Local)
- **ECC 技能**: 37 个
- **Superpowers 技能**: 18 个
- **ECC 规则**: 14 个文件
- **ECC 代理**: 29 个

### 总计

- **技能总数**: 77 个（22 Vibe + 37 ECC + 18 Superpowers）
- **代理总数**: 29 个（ECC）
- **规则总数**: 14 个文件

---

## 目录清理建议

### 可以删除

```bash
~/.agent/skills/    # 空目录，无内容
```

### 必须保留

```bash
~/.claude/skills/   # ECC 技能系统
~/.claude/agents/   # ECC 代理系统
~/.claude/rules/    # ECC 规则系统
~/.agents/skills/   # Superpowers 技能系统（活跃使用）
```

---

生成时间: 2026-03-18
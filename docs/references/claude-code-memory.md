# Claude Code Memory 机制

本文档介绍 Claude Code 的长期记忆（Memory）机制，包括存储位置、结构和使用方式。

## 1. 存储位置

### 1.1 全局目录

所有 Claude Code 记忆数据存储在全局配置目录：

```
~/.claude/
```

### 1.2 项目级记忆 (Project Memory)

每个项目有独立的记忆目录，通过项目路径的哈希值来区分：

```
~/.claude/projects/<project-hash>/memory/
├── MEMORY.md              # 主记忆文件（总是加载到上下文）
├── deployment.md          # 主题记忆文件（可选）
├── patterns.md            # 主题记忆文件（可选）
└── debugging.md           # 主题记忆文件（可选）
```

**项目哈希生成规则**：
- 项目路径被转换为哈希格式的目录名
- 例如：`/Users/jacobcy/Documents/skills/openclaw-evolve-main` → `-Users-jacobcy-Documents-skills-openclaw-evolve-main`

### 1.3 记忆图谱 (Memory Graph)

```
~/.claude/memory/graph.json
```

存储跨项目的知识图谱，包含实体和关系，用于语义搜索和关联。

### 1.4 会话历史

```
~/.claude/projects/<project-hash>/<session-id>.jsonl
```

存储会话历史记录，每个会话一个文件。

## 2. 记忆文件结构

### 2.1 MEMORY.md 主记忆文件

示例结构：

```markdown
# Project Memory

## 2026-02-20 Deployment Summary

### Completed Tasks

1. **Feature Name**
   - 配置项：值
   - 部署状态：healthy

### 关键配置

**环境变量:**
```
VAR_NAME=value
```

### 待完成

- [ ] 待办事项

### Deployment Preferences

See [deployment.md](./deployment.md) for details.
```

### 2.2 graph.json 知识图谱

存储实体、关系和观察的结构化数据，支持语义搜索。

## 3. Worktree 记忆处理机制

### 3.1 问题背景

Git worktree 允许多个工作目录共享同一个 Git 仓库。例如：

```
vibe-center/                 # 主仓库
├── wt-feature-a/           # worktree A
├── wt-feature-b/           # worktree B
└── wt-fix-bug/             # worktree C（当前目录）
```

**问题**：每个 worktree 目录路径不同，Claude Code 会将其视为不同的项目，导致记忆隔离。

### 3.2 当前行为

根据实际调查：

| 目录路径 | 项目哈希 | 记忆目录 |
|---------|---------|---------|
| `/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection` | `-Users-jacobcy-src-vibe-center-wt-fix-pr-base-selection` | 独立 |
| `/Users/jacobcy/src/vibe-center-main` | `-Users-jacobcy-src-vibe-center-main` | 独立 |

**结论**：当前 Claude Code **没有**特殊的 worktree 处理机制，每个物理目录都有独立的记忆空间。

### 3.3 影响

1. **记忆碎片化**：同一项目的不同 worktree 无法共享记忆
2. **上下文丢失**：在主目录学到的知识不会自动同步到 worktree
3. **重复学习**：每个 worktree 需要重新建立上下文

## 4. 解决方案

### 4.1 方案 A：项目级共享记忆（推荐）

在项目根目录创建共享记忆文件，所有 worktree 共享：

```
vibe-center/
├── .claude-memory/        # 项目共享记忆目录
│   ├── MEMORY.md
│   └── patterns.md
├── wt-feature-a/
├── wt-feature-b/
└── wt-fix-bug/
```

**实现方式**：
1. 在 vibe-center 主仓库创建 `.claude-memory/` 目录
2. 所有 worktree 通过符号链接或读取主目录实现共享

### 4.2 方案 B：手动同步

定期将重要记忆从各个 worktree 同步到主项目目录。

### 4.3 方案 C：使用 MCP Memory 工具

通过 MCP 工具手动管理跨 worktree 的记忆同步。

### 4.4 方案 D：使用 vibe-memory-sync 工具（vibe-center 项目实现）

vibe-center 项目提供了专用的记忆同步脚本 `scripts/vibe-memory-sync.sh`：

```bash
# 设置共享记忆同步
./scripts/vibe-memory-sync.sh setup

# 查看同步状态
./scripts/vibe-memory-sync.sh status

# 推送本地记忆到共享目录
./scripts/vibe-memory-sync.sh push

# 从共享目录拉取记忆
./scripts/vibe-memory-sync.sh pull
```

**工作原理**：
1. 脚本自动检测当前 worktree 对应的 Claude 项目哈希
2. 在 `~/.claude/projects/<hash>/memory/` 目录创建符号链接指向共享记忆
3. 支持双向同步（push/pull）

## 5. 使用建议

### 5.1 对于 vibe-center 项目

vibe-center 项目已在主仓库创建共享记忆目录和同步工具：

**共享记忆位置**：
```
vibe-center/main/.claude-memory/MEMORY.md
```

**同步工具**：
```
vibe-center/main/scripts/vibe-memory-sync.sh
```

**快速开始**：
```bash
# 在主仓库执行（首次）
cd /Users/jacobcy/src/vibe-center/main
mkdir -p .claude-memory
# 编辑 .claude-memory/MEMORY.md 添加项目共享知识

# 在每个 worktree 中执行
cd /path/to/worktree
./scripts/vibe-memory-sync.sh setup
./scripts/vibe-memory-sync.sh status
```

### 5.2 记忆写入最佳实践

1. **区分层次**：
   - 项目通用知识 → `.claude-memory/`（共享）
   - worktree 特定上下文 → 本地 `memory/`（隔离）

2. **及时归档**：
   - 完成 flow 后，将有价值的记忆同步到共享目录
   - 使用 `vibe-memory-sync.sh push` 同步

3. **避免重复**：
   - 写入前先检查是否已存在于共享记忆

## 6. 相关工具

### 6.1 MCP Memory 工具

- `mcp__memory__read_graph` - 读取知识图谱
- `mcp__memory__create_entities` - 创建实体
- `mcp__memory__add_observations` - 添加观察
- `mcp__memory__search_nodes` - 搜索节点

### 6.2 命令

```bash
# 查看当前项目记忆
ls ~/.claude/projects/

# 查看共享记忆
cat ~/.claude/memory/graph.json
```

## 7. 参考资料

- [Claude Code 官方文档](https://docs.anthropic.com/claude-code/)
- [Memory MCP Server](https://github.com/anthropics/claude-code)

---

*文档创建：2026-03-11*
*相关文档：[docs/README.md](../README.md)*

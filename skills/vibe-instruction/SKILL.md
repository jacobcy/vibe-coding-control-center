---
name: vibe-instruction
description: Use when you need an overview of the Vibe Center project, its two implementations (vibe2 shell and vibe3 python), the available commands, and the standard development workflow. This is the meta-skill that orients any agent to the project.
---

# /vibe-instruction - 项目导览

这是所有 agent 的入口导览技能。用于快速了解项目结构、可用命令和开发工作流。

---

## 项目结构概览

Vibe Center 包含**两个并行实现**：

```
vibe-center/
  bin/vibe          # V2 Shell 入口
  lib/              # V2 Shell 核心逻辑
  config/aliases.zsh  # V2 alias 定义
  src/vibe3/        # V3 Python 实现
  skills/           # AI agent 技能集
  .agent/           # 规则、规范、上下文
```

---

## V2 Shell 部分（vibe2）

V2 是基础 Shell 实现，通过 `config/aliases.zsh` 提供常用 alias。

**激活方式**：
```bash
source $(vibe alias --load)
# 或直接 source config/aliases.zsh
```

**核心 alias（常用）**：

| alias | 含义 |
|-------|------|
| `wtnew <branch>` | 创建新 worktree（git worktree add） |
| `vup` | 更新主仓库 + 当前 worktree |

**V2 主命令**：

```bash
bin/vibe check          # 验证环境
bin/vibe tool           # 工具管理
bin/vibe keys <list|set|get|init>  # 密钥管理
```

> **注意**：`bin/vibe flow|task|roadmap` 等命令已重定向到 V3（vibe3）。V2 的主要价值在于 alias 和环境工具，业务逻辑由 V3 承载。

---

## V3 Python 部分（vibe3）

V3 是主要的 issue → flow → PR 管理工具。

**运行方式**（必须用 uv）：
```bash
uv run python src/vibe3/cli.py <command>
# 或通过 alias: vibe3 <command>
```

### 核心命令组

#### flow - 分支/工作流管理

```bash
# 查看当前 flow 详情（主要观察窗口）
vibe3 flow show
vibe3 flow show --trace     # 含调用链追踪

# 查看所有活跃 flow 仪表盘
vibe3 flow status

# 列出所有 flow
vibe3 flow list

# 在新分支创建 flow（同时指定任务 issue）
vibe3 flow create <name> --task <issue-number>
vibe3 flow create <name> --base main

# 在已有分支上注册 flow（不创建新分支）
vibe3 flow add

# 绑定 issue 到当前 flow
vibe3 flow bind <issue-number>                    # 默认 role=task
vibe3 flow bind <issue-number> --role related
vibe3 flow bind <issue-number> --role dependency

# 标记 flow 为 blocked（有依赖时）
vibe3 flow blocked --task <blocking-issue-number>
vibe3 flow blocked --reason "等待外部反馈"

# 结束并删除 flow（推荐方式）
vibe3 flow done

# 切换到其他 flow（无需 flow done，直接 checkout）
git checkout <other-branch>
```

#### task - 任务上下文

```bash
# 查看当前任务（含 milestone 编排视图）
vibe3 task show

# 列出所有有任务绑定的 flow
vibe3 task list
```

#### handoff - agent 交接记录

```bash
# 查看交接链
vibe3 handoff show

# 追加轻量更新
vibe3 handoff append "<message>" --actor <actor> --kind <milestone|note>

# 记录 plan / report / audit handoff
vibe3 handoff plan
vibe3 handoff report
vibe3 handoff audit
```

#### pr - Pull Request 管理

```bash
vibe3 pr create --base <ref>  # 创建 PR
```

#### inspect - 代码分析（开发工具）

```bash
vibe3 inspect symbols <file>       # 符号引用分析
vibe3 inspect structure <file>     # 文件结构 + 依赖
vibe3 inspect commit <sha>         # 改动影响范围
```

#### 其他实用命令

```bash
vibe3 check           # 验证 handoff 存储一致性
vibe3 --trace <cmd>   # 任意命令加 --trace 可追踪调用链
```

---

## 开发工作流

### 标准流程

```
/vibe-new <feature>
    → [写代码]
    → /vibe-commit
    → /vibe-integrate
    → /vibe-done
```

### 各阶段说明

| 阶段 | skill | 职责 |
|------|-------|------|
| 开始任务 | `/vibe-new` | 选 issue → 创建/注册 flow → 绑定 issue → 创建 PR draft → 停止等待开发 |
| 提交代码 | `/vibe-commit` | 整理变更 → 分组 commit → 推送 PR → 停止 |
| 整合合并 | `/vibe-integrate` | 检查 CI / review → 解除阻塞 → 合并 PR |
| 收口归档 | `/vibe-done` | 关闭 issue → 执行 `flow done` → 清理工作区 |

### 有依赖时的处理

如果当前 flow 依赖另一个 issue 未完成：

```bash
# 标记为 blocked，记录依赖
vibe3 flow blocked --task <blocking-issue-number> --reason "需要 #X 先完成"

# 当前 flow 状态变为 blocked，可安全 git checkout 到其他分支处理别的任务
git checkout main   # 或切到其他活跃 flow

# 依赖解除后，切回来继续
git checkout <this-branch>
vibe3 flow show     # 确认状态，继续开发
```

### 在已有分支上继续工作

```bash
# 从非活跃分支创建新 flow
vibe3 flow create <name> --task <issue>

# 在当前分支注册 flow（已有 branch，首次使用 vibe3）
vibe3 flow add

# 绑定任务 issue（已有 flow 但未绑定 task）
vibe3 flow bind <issue> --role task
```

---

## 常见场景速查

### 查看项目进度
```bash
vibe3 flow status        # 所有活跃 flow 一览
vibe3 task show          # 当前任务 + milestone 进度
```

### 调试问题
```bash
vibe3 flow show --trace  # 追踪 flow show 调用链
vibe3 inspect symbols src/vibe3/commands/flow.py  # 查看符号引用
```

### flow 卡住了怎么办
```bash
# 如果 flow done 失败，可先切走
git checkout main

# 如果需要放弃当前 flow
vibe3 flow aborted

# 如果 flow 状态数据异常，运行一致性检查
vibe3 check
```

---

## 常见误区

1. **flow ≠ branch**：flow 是绑定在 branch 上的元数据（issue、PR、状态），branch 只是载体
2. **flow done ≠ git branch -d**：`flow done` 会同时清理本地/远端 branch 和 flow 元数据
3. **不需要 vibe-new 也可以 commit**：vibe-new 是 agent 流程入口，人工开发随时可以 commit
4. **--trace 不影响功能**：任何命令加 `--trace` 只增加日志输出，不改变行为
5. **task show 和 flow show 的区别**：`flow show` 是开发时间线视角，`task show` 是项目编排视角（milestone）

---

## 数据存储位置

- **flow 元数据**：`.git/vibe3/`（位于主仓库 git common dir，即最顶层 `.git`）
- **handoff 文件**：`.agent/context/`（每个 worktree 的本地状态，不是真源）
- **GitHub 为真源**：issue、PR 状态以 GitHub 为准，本地只存最小索引

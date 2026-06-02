# Vibe Center 3.0 — 开发指南

> **文档定位**：本文件是开发流程和工具使用的权威指南（详见 [SOUL.md](SOUL.md) §0 文档职责分工）
> **核心原则**：详见 [SOUL.md](SOUL.md)
> **项目结构**：详见 [STRUCTURE.md](STRUCTURE.md)
> **AI 规则**：详见 [CLAUDE.md](CLAUDE.md)
> **V3 标准入口**：`docs/standards/v3/` 是 V3 命令、数据、技能与 handoff 语义的真源目录。

## 1. 项目双栈，但 V3 为主链

本项目包含两个维度的工作（详见 [CLAUDE.md](CLAUDE.md)），但当前默认开发路径是 V3 Python：

| 维度 | 内容 | 位置 | 治理标准 |
|------|------|------|----------|
| **V3 Python 运行时** | 主执行链、flow、handoff、orchestra、roles | `src/vibe3/` | 命令、数据、角色语义以 `docs/standards/v3/` 为准 |
| **V2 Shell** | 环境工具、兼容入口、轻量辅助能力 | `bin/`, `lib/`, `config/` | LOC ≤ 7000，单文件 ≤ 300 行 |
| **Vibe Coding Framework** | Agent 行为控制技能 | `skills/` | 清晰度、正确性、有效性 |

> Shell 代码严格控制体积；技能是 Markdown 提示词，评估标准不同。V3 Python 的新语义与命令边界优先写入 `docs/standards/v3/`。

---

## 2. 开发环境搭建

### 2.1 前置要求
- macOS / Linux
- zsh (默认 Shell)
- git
- [bats-core](https://github.com/bats-core/bats-core)：`brew install bats-core`
- [shellcheck](https://www.shellcheck.net/)：`brew install shellcheck`

### 2.2 Setup（自动化环境准备）

```bash
./scripts/init.sh
```

当你执行 `vibe flow start <feature>`、`wtnew <branch>`，或由 V3 runtime 自动创建 worktree 时，`scripts/init.sh` 会自动运行，完成以下工作：
1. 安装并配置 `openSpec` 和 `Superpowers`
2. 在 `.agent/skills/` 建立项目自有技能和第三方技能的符号链接
3. 为 Trae 编辑器用户准备相同的技能环境

**Hybrid Architecture Setup (Recommended):**
为了在任何目录下都能直接使用 `vibe3` 命令，建议安装全局可执行文件：
```bash
uv tool install -e .
```

如果你是手动 `git worktree add ...` 创建工作树，则需要手动运行一次 `./scripts/init.sh`。

### 2.3 验证环境
```bash
bin/vibe check       # 环境诊断（V2）
vibe3 check          # V3 一致性与共享状态审计 (或 uv run python src/vibe3/cli.py check)
bats tests/          # 运行所有测试（应看到 20 tests, 0 failures）
bash scripts/hooks/lint.sh # 双层 lint 检查（0 errors）
```

### 2.4 V3 开发入口

V3 相关工作优先用 Python 入口和 V3 标准来校准语义。支持通过 `uv tool install -e .` 安装全局 `vibe3` 命令：

```bash
vibe3 check
vibe3 status
vibe3 flow show
vibe3 handoff show
uv run pytest tests/vibe3
```

如果需要理解命令、数据模型、技能或 handoff 的正式边界，优先阅读 `docs/standards/v3/` 下的标准文档。

---

## 3. 如何防止 AI 生成垃圾代码

这是本项目最重要的一章。**AI 如果不加约束，会不断膨胀代码、引入死代码、忽略边界条件。** 我们通过三层机制防止这件事发生。

### 3.1 问题的根本

以下是 AI 在 Vibe Center 项目中被禁止做的事：

| AI 的坏习惯 | 我们的制约 |
|---|---|
| 无限膨胀代码量 | LOC 硬上限：Python 总量 ≤ 65000 行，单文件警告 300/阻塞 400 |
| 文档膨胀 | 文档单文件：警告 500 / 阻塞 800 |
| 添加"万一用到"的函数 | 零死代码：每个函数必须有调用者 |
| 不测试直接提交 | 所有修改必须通过 `bats tests/` (V2) 或 `pytest tests/vibe3` (V3) |
| 自己看不见语法错误 | 修改后必须运行 lint (Shell) 或 ruff/mypy (Python) |
| 不经审批加功能 | SOUL.md + CLAUDE.md 锁死边界 |

### 3.2 三层防护机制

#### 🔴 Layer 0：硬规则（HARD RULES）

写在 `CLAUDE.md` 和 `SOUL.md` 中的不可违反规则：

```
- V3 Python 总 LOC ≤ 65000 (config/v3/loc_limits.yaml)
- 任何单个 .py 文件：警告 300 / 阻塞 400
- 任何单个 .md 文档：警告 500 / 阻塞 800
- lib/ + bin/ 总 LOC ≤ 7000 (V2 Shell)
- 任何单个 .sh 文件 ≤ 300 行 (V2 Shell)
- 零死代码：每个函数必须有 ≥1 个调用者
- 不得在 SOUL.md 之外新增 CLI 功能
```

**违反即拒绝。** CI Pipeline 会自动检测并阻止合并。

#### 🟡 Layer 1：Serena AST 检索（修改前的影响分析）

Serena 是一个 MCP 工具，提供代码结构的 AST 级查询能力。

**强制场景：**

| 操作 | 必须调用的工具 |
|---|---|
| 修改任何函数前 | `find_referencing_symbols("<函数名>")` ← 查调用者 |
| 删除任何函数前 | `find_referencing_symbols("<函数名>")` ← 确认无人调用 |
| 新增函数后 | `get_symbols_overview("lib/<文件>.sh")` ← 检查总函数数 |

**禁止：**
- ❌ 不查引用直接修改函数签名
- ❌ 不查引用直接删除函数
- ❌ 用 `cat` 读整个文件来"理解上下文"

详见 [docs/standards/serena-usage.md](standards/serena-usage.md)。

#### 🟢 Layer 2：双层 Lint（修改后验证语法和质量）

每次修改 Shell 代码后，**必须运行**：

```bash
bash scripts/hooks/lint.sh
```

这个脚本做两件事：

**Step 1：`zsh -n`（语法检查，0 容忍）**
```bash
zsh -n lib/flow.sh   # 检查是否有语法错误
```

**Step 2：`shellcheck -s bash`（代码质量，error 级 0 容忍）**
```bash
shellcheck -s bash -S error lib/*.sh bin/vibe
```

Zsh 特有语法（如 `${(%):-%x}`）已在 `.shellcheckrc` 中豁免。

#### 🟢 Layer 3：bats 测试（功能验证）

每次修改后，**必须运行**：

```bash
bats tests/
```

预期输出：`20 tests, 0 failures`

如果测试失败，**禁止提交**。找到根因修复后再提交。

### 3.3 自动修复闭环（vibe-test-runner Skill）

`skills/vibe-test-runner/SKILL.md` 定义了 AI Agent 的自动修复流程：

```
发现问题 → 自动修复 → 重新验证 → 循环（最多 3 轮）
              ↓
         3 轮不过 → 挂起，通知人类介入
```

**为什么是 3 轮？** 3 轮修不好通常说明 Spec 有问题，而非代码问题，此时需要人类判断。

### 3.4 CI/CD 自动把关

`.github/workflows/ci.yml` 在每次 Push 和 PR 时自动运行：

1. `bash scripts/hooks/lint.sh` — 双层 lint (Shell) + ruff/mypy (Python)
2. `bats tests/` & `pytest tests/vibe3` — 所有测试
3. Python LOC 总量检查 (≤ 65000)
4. 单文件行数检查 (Code ≤ 400, Doc ≤ 800)

**CI 不过 = PR 不能合并。**

### 3.5 实时度量仪表盘

随时运行以下命令查看项目健康状态：

```bash
vibe3 snapshot show           # V3 核心仪表盘（替换旧的 check --metrics）
bash scripts/tools/metrics.sh  # V2 Legacy 仪表盘
```

输出示例 (V3)：

```
## 📊 Vibe Center 健康度仪表盘

| 指标       | 上限         | 当前值  | 状态 |
|-----------|--------------|---------|------|
| Python LOC| 65000        | 45894   | ✅   |
| Code 文件 | 400          | 320     | ✅   |
| Doc 文件  | 800          | 505     | ✅   |
| Pytest    | 0 失败       | 0       | ✅   |
| Type Check| 0 错误       | 0       | ✅   |
```

---

## 4. V2 标准开发流程（V2 Legacy，已退居二线）

> ⚠️ **重要提示**：此流程基于已不再扩展的 V2 Shell 入口（`bin/vibe`）。
> **当前项目已全面切换到 V3 Python 运行时为核心。**
> 新功能开发、架构调整和日常运维必须优先使用 §2.4 节定义的 V3 入口和命令集。
> 仅在维护旧逻辑、环境同步或简单的密钥管理时，才参考此 V2 流程。

### Step 1：创建工作区

```bash
# 在项目根目录，使用 git worktree 创建隔离工作空间
git worktree add ../wt-task-1839 task/issue-1839
cd ../wt-task-1839

# 注册并同步 flow 状态
vibe3 flow update
```

> V3 优先使用 `vibe3 flow update` 注册当前分支为活跃 flow；worktree 建议使用原生 `git worktree` 管理或由 orchestra 自动调度。开发前通过 `vibe3 flow show` 查看当前 flow 上下文。

这会：
- 创建独立的物理工作目录
- 自动检测并同步分支对应的 flow 状态
- 准备技能环境（通过 `scripts/init.sh`）
- 使当前目录成为该 flow 的权威执行区

### Step 2：写计划（Plan Gate）

使用 `/vibe-task` 或 `/vibe-new` 技能明确任务范围，然后创建执行计划：

```bash
vibe3 plan --branch @current
```

**不通过 Plan Gate，不开始写代码。**

### Step 3：执行任务（Run Gate）

利用 `/vibe-*` 系列技能执行具体动作：
- 使用 `/vibe-review-docs` 审查文档
- 使用 `/vibe-review-code` 审查代码
- 使用 `/vibe-commit` 自动提交并创建 PR

每改一次代码，运行验证命令：

```bash
# 1. 语法和质量检查 (V3)
uv run ruff check .
uv run mypy src/vibe3

# 2. 运行所有测试
uv run pytest tests/vibe3

# 3. 查看健康度
vibe3 snapshot show
```

**出现 ❌ 立刻修复，不要积累问题。**

### Step 4：Review + 创建 PR

```bash
# 使用技能执行标准化审查
/vibe-team-review

# 提交并推送到远端
/vibe-commit
```

### Step 5：清理工作区

```bash
# 完成后移除 worktree
git worktree remove .
```

---

## 5. 目录结构

```
bin/vibe               # CLI 入口（~60 行）
lib/                   # Shell 核心逻辑（受 LOC 上限约束）
config/                # 别名、密钥模板
scripts/
  lint.sh              # 双层 lint（zsh -n + shellcheck）
  metrics.sh           # MSC 健康度仪表盘
skills/                # 🟢 Vibe 自有技能（tracked，规范源）
  vibe-test-runner/    # 三层验证 Skill（Serena + Lint + bats）
  vibe-commit/         # 智能 commit 消息生成
.claude/rules/        # 架构和编码规则
.agent/                # Agent 工作区
  governance.yaml      # 治理配置
  workflows/           # 工作流定义
.serena/
  project.yml          # Serena AST 检索配置（项目级约束）
.shellcheckrc          # ShellCheck 豁免规则（Zsh 特有语法）
.github/workflows/
  ci.yml               # CI Pipeline（lint + test + LOC 检查）
openspec/specs/
  cli-commands.yaml    # CLI 命令结构化 Spec（机器可读）
docs/
  standards/           # 开发规范文档
.agent/
  plans/               # 临时实施计划（执行前可写）
  reports/             # 临时验证报告
  model-spec-context.md # MSC 范式说明与自检
tests/                 # bats-core 测试（≥20 个用例）
```

---

## 6. 外部依赖

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| [bats-core](https://github.com/bats-core/bats-core) | Shell 单元测试 | `brew install bats-core` |
| [shellcheck](https://www.shellcheck.net/) | Shell 代码 lint | `brew install shellcheck` |
| [Superpowers](https://github.com/jomifred/superpowers) | 通用 agent 技能 | 按文档安装到 `~/.agents/skills/` |
| [OpenSpec](https://github.com/OpenSpec) | 结构化变更管理 | 按文档安装 |
| Serena MCP | AST 检索（IDE/Agent 已内置） | 通常已内置于 IDE |

---

## 7. 常用命令速查

### V2 (Shell) — Legacy，不再扩展

> ⚠️ `bin/vibe` 是 V2 Shell 入口，已稳定不再扩展。V3 用户请使用下方 V3 (Python) 命令。

```bash
# 开发工作流（V2，仅供参考）
bin/vibe flow start <feature>  # 创建 worktree + 分支
bin/vibe flow review           # Pre-PR 检查
bin/vibe flow pr               # 创建 PR
# 注意：flow done 已弃用，V3 使用 git worktree remove

# 质量验证（每次改代码后必跑）
bash scripts/hooks/lint.sh           # 双层 lint
bats tests/                    # 所有测试
bash scripts/tools/metrics.sh        # 健康度仪表盘

# 环境和工具
bin/vibe check                 # 环境诊断
bin/vibe keys list             # 列出 API 密钥
bin/vibe tool                  # 安装 AI 工具
bin/vibe clean                 # 清理临时文件
```

### V3 (Python)

```bash
# 核心运行时管理
vibe3 serve status      # 查看 Orchestra 服务状态与门禁
vibe3 task status       # 总览活跃 flow 与 orchestra 状态
vibe3 check             # 共享状态审计与一致性检查
vibe3 snapshot show     # 项目健康度度量仪表盘

# Flow 与协作
vibe3 flow show         # 查看当前 flow 上下文与绑定信息
vibe3 flow update       # 注册/更新当前分支为活跃 flow
vibe3 flow bind         # 显式绑定 issue-flow 关系
vibe3 handoff show      # 查看 agent 间的 handoff 链路
vibe3 handoff append    # 向当前 flow 追加 handoff 记录

# 代码智能与执行 (Agent 模式)
vibe3 inspect symbols   # AST 级代码结构分析
vibe3 plan/run/review   # 标准 Agent 执行入口
vibe3 ask               # 向 Vibe 知识库/现场提问
```

---

## 8. Vibe Center 3.0 的核心哲学

**"用约束驯服 AI"**

AI 不是通才，是专才。给它越大的自由度，越容易出轨。Vibe Center 3.0 的核心不是"让 AI 写更多代码"，而是"让 AI 在极窄的通道里做正确的事"：

1. **Spec 先行**：CLI 命令有机器可读的 YAML Spec，PRD 先于代码存在
2. **工具约束**：不靠提示词说"请别写太多"，靠 CI 硬拦截
3. **可度量**：所有规则都对应可运行的检查脚本，通过/失败一目了然

这套机制的详细原理见 [CLAUDE.md](CLAUDE.md) §架构分层与 [docs/standards/v3/command-standard.md](docs/standards/v3/command-standard.md) 命令规范。

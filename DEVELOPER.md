# Vibe Center 2.0 — 开发指南

> **文档定位**：本文件是开发流程和工具使用的权威指南（详见 [SOUL.md](SOUL.md) §0 文档职责分工）
> **核心原则**：详见 [SOUL.md](SOUL.md)
> **项目结构**：详见 [STRUCTURE.md](STRUCTURE.md)
> **AI 规则**：详见 [CLAUDE.md](CLAUDE.md)

## 1. 项目双重身份

本项目包含两个维度的工作（详见 [CLAUDE.md](CLAUDE.md)）：

| 维度 | 内容 | 位置 | 治理标准 |
|------|------|------|----------|
| **Zsh CLI** | Shell 脚本，环境编排 | `bin/`, `lib/` | LOC ≤ 7000，单文件 ≤ 300 行 |
| **Vibe Coding Framework** | Agent 行为控制技能 | `skills/` | 清晰度、正确性、有效性 |

> Shell 代码严格控制体积；技能是 Markdown 提示词，评估标准不同。

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

当你执行 `vibe flow start <feature>` 创建新工作区时，`scripts/init.sh` 会自动运行，完成以下工作：
1. 安装并配置 `openSpec` 和 `Superpowers`
2. 在 `.agent/skills/` 建立项目自有技能和第三方技能的符号链接
3. 为 Trae 编辑器用户准备相同的技能环境

手动创建 worktree 时需要手动运行一次 `./scripts/init.sh`。

### 2.3 验证环境
```bash
bin/vibe check       # 环境诊断
bats tests/          # 运行所有测试（应看到 20 tests, 0 failures）
bash scripts/hooks/lint.sh # 双层 lint 检查（0 errors）
```

---

## 3. 如何防止 AI 生成垃圾代码

这是本项目最重要的一章。**AI 如果不加约束，会不断膨胀代码、引入死代码、忽略边界条件。** 我们通过三层机制防止这件事发生。

### 3.1 问题的根本

以下是 AI 在 Vibe Center 项目中被禁止做的事：

| AI 的坏习惯 | 我们的制约 |
|---|---|
| 无限膨胀代码量 | LOC 硬上限：总量 ≤ 7000 行，单文件 ≤ 300 行 |
| 添加"万一用到"的函数 | 零死代码：每个函数必须有调用者 |
| 不测试直接提交 | 所有修改必须通过 `bats tests/` |
| 自己看不见语法错误 | 修改后必须运行 `zsh -n` + `shellcheck` |
| 不知道改了哪些地方 | 修改前必须查引用关系（Serena AST） |
| 不经审批加功能 | SOUL.md + CLAUDE.md 锁死边界 |

### 3.2 三层防护机制

#### 🔴 Layer 0：硬规则（HARD RULES）

写在 `CLAUDE.md` 和 `SOUL.md` 中的不可违反规则：

```
- lib/ + bin/ 总 LOC ≤ 7000
- 任何单个 .sh 文件 ≤ 300 行
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

1. `bash scripts/hooks/lint.sh` — 双层 lint
2. `bats tests/` — 所有测试
3. LOC 总量检查（`find lib/ bin/ | xargs wc -l` ≤ 7000）
4. 单文件行数检查（每个文件 ≤ 300 行）

**CI 不过 = PR 不能合并。**

### 3.5 实时度量仪表盘

随时运行以下命令查看项目健康状态：

```bash
bash scripts/tools/metrics.sh
```

输出示例：

```
## 📊 MSC 健康度仪表盘

| 指标       | 上限  | 当前值 | 状态 |
|-----------|-------|--------|------|
| 总 LOC    | 7000  | 689    | ✅   |
| 最大文件  | 300   | 191    | ✅   |
| 测试用例  | ≥20   | 20     | ✅   |
| ShellCheck| 0错误 | 0      | ✅   |
| 死代码函数| 0     | 0      | ✅   |
```

---

## 4. 标准开发流程

> 小白入门：**每次开发功能，严格按这 5 步走。**

### Step 1：创建工作区

```bash
# 在项目根目录
bin/vibe flow start <feature-name>
# 例如：bin/vibe flow start add-vibe-doctor
```

这会：
- 创建 `wt-claude-<feature>` 目录（git worktree）
- 切换到新分支
- 自动运行 `scripts/init.sh` 准备环境
- 生成 `docs/prds/<feature>.md` 的 PRD 模板

### Step 2：写 PRD（先写需求，再写代码）

打开 `docs/prds/<feature>.md`，填写：
- 背景：为什么需要这个功能
- 目标：这个功能做什么
- 需求清单：具体的验收条件

**不写 PRD，不开始写代码。**

### Step 3：写代码 + 验证（边写边测）

每改一次代码，运行三个命令：

```bash
# 1. 语法和质量检查
bash scripts/hooks/lint.sh

# 2. 运行所有测试
bats tests/

# 3. 查看健康度
bash scripts/tools/metrics.sh
```

**出现 ❌ 立刻修复，不要积累问题。**

### Step 4：Review + 创建 PR

```bash
bin/vibe flow review   # 交互式 review
bin/vibe flow pr       # 生成 PR
```

### Step 5：清理工作区

```bash
bin/vibe flow done     # 合并后清理 worktree
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
.agent/                # Agent 工作区
  governance.yaml      # 治理配置
  workflows/           # 工作流定义
  rules/               # 架构和编码规则
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

```bash
# 开发工作流
bin/vibe flow start <feature>  # 创建 worktree + 分支
bin/vibe flow review           # Pre-PR 检查
bin/vibe flow pr               # 创建 PR
bin/vibe flow done             # 清理 worktree

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

---

## 8. V2 的核心哲学

**"用约束驯服 AI"**

AI 不是通才，是专才。给它越大的自由度，越容易出轨。Vibe Center 2.0 的核心不是"让 AI 写更多代码"，而是"让 AI 在极窄的通道里做正确的事"：

1. **Spec 先行**：CLI 命令有机器可读的 YAML Spec，PRD 先于代码存在
2. **工具约束**：不靠提示词说"请别写太多"，靠 CI 硬拦截
3. **可度量**：所有规则都对应可运行的检查脚本，通过/失败一目了然

这套机制的详细原理见 [docs/model-spec-context.md](model-spec-context.md)。

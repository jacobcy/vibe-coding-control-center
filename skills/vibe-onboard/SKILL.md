---
name: vibe-onboard
description: 安装完成后的入门引导与系统检查。用于安装完成后引导用户完成配置、检查系统状态、介绍核心功能，是新用户安装后的第一步入口。支持交互式询问用户需求，只安装必要的可选组件。**职责边界**：底层事实来自 `vibe doctor` / `vibe keys check`，本技能只负责解释结果与组织下一步。
---

# /vibe-onboard - 安装后入门引导

Vibe Center 安装完成后的一站式引导工具，帮助用户完成全部配置、检查系统状态、了解核心功能，确保系统就绪可用。

前提：

- 命令链路已经由 `zsh scripts/install.sh` 建好；如果 `vibe` 命令还不可用，先完成安装并重新加载 shell
- 当前项目 / worktree 已执行 `zsh scripts/init.sh`；通过 `wtnew`、`vibe flow start` 或 V3 自动创建的新 worktree 通常会自动跑一次，但如果还没做项目初始化，先执行它再进入 onboarding
- 推荐在 Claude Code 等支持 skill 的工具内使用 `/vibe-onboard`

**完成后状态**：所有基础配置已完成，系统状态健康，用户了解核心用法，可以开始使用 Vibe Center 开发。

---

## 核心职责

1. **必要依赖诊断检查**：运行 `vibe doctor` / `vibe doctor --essential` 获取系统事实结果
2. **密钥配置引导**：引导用户配置必要的 API 密钥（OpenAI/Anthropic/GitHub 等）
3. **交互式可选组件安装**：询问用户需求，按需安装可选组件（远程开发工具、额外AI后端等）
4. **项目与能力介绍**：介绍 Vibe Center 的核心定位、本项目结构与主要命令
5. **skills 体系引导**：在用户需要时引导到 `vibe skills check` / `/vibe-skills-manager`
6. **快速开始教程**：给出简单的使用示例，帮助用户快速上手

**分层原则**：
- `vibe doctor` 负责工具与 Claude plugins 的事实判断
- `vibe keys check` 负责密钥状态的事实判断
- `/vibe-onboard` 只消费这些结果，负责解释、排序、提问和给方案
- `/vibe-onboard` 不直接读取 `config/dependencies.toml`，也不重复实现底层检查逻辑

---

## 停止点

完成后输出：
- ✅ 系统状态检查完成，所有必要依赖正常
- ✅ 密钥配置已完成
- ✅ 可选组件已按用户需求安装
- **下一步**：开始使用 Vibe Center，运行 `/vibe-new` 创建新任务
- 如果在安装、初始化或使用过程中遇到问题，提示用户向项目开发者提交 issue，并附上现场信息与复现步骤

---

## 完整流程

```
/vibe-onboard
  ├─ Step 0: 收集底层事实
  │   ├─ 确认 `vibe` 命令已经可用；如果不可用，先提示运行 `zsh scripts/install.sh`
  │   ├─ 确认当前项目已执行 `zsh scripts/init.sh`；如果没有，先提示执行初始化
  │   ├─ 运行 `vibe doctor --essential`
  │   ├─ 运行 `vibe doctor`
  │   ├─ 运行 `vibe keys check`
  │   └─ 基于以上结果整理后续引导流程
  │
  ├─ Step 1: 必要依赖诊断与检查
  │   ├─ 读取 `vibe doctor --essential` 的输出
  │   ├─ 识别必要工具中缺失或异常的项目
  │   └─ 只给出明确解决方案，不在本技能中自行做底层判断
  │
  ├─ Step 2: 密钥配置引导
  │   ├─ 读取 `vibe keys check` 的输出
  │   ├─ 列出缺失的必要密钥
  │   ├─ 对可选密钥只在用户需要相关能力时再建议
  │   └─ 默认引导用户手动编辑 `~/.vibe/keys.env`（该文件由 `config/keys.template.env` 初始化）
  │
  ├─ Step 3: 交互式可选组件询问（每项都需要用户确认）
  │   ├─ 读取 `vibe doctor` 中的可选工具、必要 plugins、建议 plugins、可选 plugins
  │   ├─ 根据用户目标解释哪些值得装、哪些可以跳过
  │   ├─ 如果用户要继续，由 agent 和用户交互决定安装哪些项
  │   └─ `/vibe-onboard` 自身不维护可选项清单，只引用 doctor / keys 的结果
  │
  ├─ Step 4: 核心功能介绍
  │   ├─ 介绍 Vibe Center 的核心定位：AI 开发编排工具
  │   ├─ 介绍本项目的双栈结构：V2 shell + V3 runtime
  │   ├─ 展示常用命令：
  │   │   - `/vibe-new`：创建新开发任务
  │   │   - `/vibe-commit`：提交代码并生成规范 commit 信息
  │   │   - `/vibe-review`：代码评审
  │   │   - `vibe doctor`：系统诊断
  │   │   - `vibe keys`：密钥管理
  │   └─ 介绍项目架构和扩展能力
  │
  ├─ Step 5: skills 体系引导
  │   ├─ 如用户关心 skills 安装 / 对齐，运行 `vibe skills check`
  │   ├─ 引导用户理解三类体系：
  │   │   - Superpowers：Claude plugin / 其他 agent 用 npx skills
  │   │   - OpenSpec：项目内独立工具链，按需启用
  │   │   - Gstack：用户可选增强，建议全局安装
  │   ├─ 如需进一步审计与推荐，委托 `/vibe-skills-manager`
  │   └─ 目标是保证 codeagent-wrapper 等执行代理具备足够能力
  │
  └─ Step 6: 快速开始教程
      ├─ 给出简单的使用示例：如何创建一个新任务，如何提交代码
      ├─ 说明文档位置：`CLAUDE.md`、`docs/` 目录
      └─ 提示用户有问题可以随时查看 `CLAUDE.md` 或使用 `/help` 获取帮助
```

---

## 事实来源

`/vibe-onboard` 不直接做底层事实判断，统一以这些命令为准：

- `zsh scripts/install.sh`（保证命令可用）
- `zsh scripts/init.sh`（保证当前项目 / worktree 初始化完成）
- `vibe doctor --essential`
- `vibe doctor`
- `vibe keys check`

如果这些命令的结果和文档描述冲突，以命令输出为准。`config/dependencies.toml` 属于 `doctor` / `keys` 的底层真源，不属于 `/vibe-onboard` 直接消费的接口。

---

## 注意事项

1. **交互式询问**：每一步都需要用户明确确认，不要强制安装不需要的组件
2. **尊重用户选择**：如果用户拒绝某个组件，不要反复提示或强行安装
3. **密钥安全**：密钥输入时要保证安全，不要记录或泄露用户的密钥信息
4. **清晰指引**：对于有问题的检查项，要给出明确、可执行的解决方案
5. **友好引导**：对于不熟悉技术的用户也要容易理解，使用简单明了的语言

---

## 常见安装指引

### codeagent-wrapper 安装

**必要依赖**：V3 的 `vibe3 run` 命令依赖此工具执行 AI Agent 任务。

**安装方式**（选择其一）：

**方式 1：直接下载预编译二进制（推荐）**

```bash
# 创建安装目录
mkdir -p ~/.claude/bin

# 下载最新版本（自动检测系统架构）
ARCH=$(uname -m)
case "$ARCH" in
  arm64) BINARY="codeagent-wrapper-darwin-arm64" ;;
  x86_64) BINARY="codeagent-wrapper-darwin-amd64" ;;
  *) echo "不支持的架构: $ARCH"; exit 1 ;;
esac

curl -fL --retry 3 --connect-timeout 10 \
  "https://github.com/stellarlinkco/myclaude/releases/latest/download/$BINARY" \
  -o ~/.claude/bin/codeagent-wrapper

# 设置可执行权限
chmod +x ~/.claude/bin/codeagent-wrapper

# 验证安装
~/.claude/bin/codeagent-wrapper --version
```

**方式 2：使用 npx 安装器**

```bash
npx github:stellarlinkco/myclaude
# 选择 codeagent-wrapper 模块
```

**方式 3：从源码构建**

需要 Go 1.21+：

```bash
git clone https://github.com/stellarlinkco/myclaude.git
cd myclaude/codeagent-wrapper
make build
mkdir -p ~/.claude/bin
cp codeagent-wrapper ~/.claude/bin/
```

**安装后验证**：

```bash
# 检查版本
codeagent-wrapper --version

# 检查帮助
codeagent-wrapper --help

# 确保 PATH 包含 ~/.claude/bin
export PATH="$HOME/.claude/bin:$PATH"
# 建议添加到 shell 配置文件（~/.zshrc 或 ~/.bashrc）
```

**官方仓库**：https://github.com/stellarlinkco/myclaude

**相关文档**：
- `docs/references/codeagent-wrapper-guide.md` — 详细使用指南
- `docs/references/everything-claude-code-installation-guide.md` — ECC 集成安装

### 密钥配置与加载机制

**重要**：Vibe Center 使用两层密钥加载机制。

**Shell 层**（`vibe` 命令）：
- 自动加载 `~/.vibe/config/keys.env`
- 通过 `lib/config.sh` 实现

**Python 层**（`vibe3 serve`、`vibe3 run`）：
- `uv run` 创建干净环境，不加载用户 shell 配置
- `manager.py` 会尝试读取项目的 `config/keys.env`（fallback）

**推荐配置方式**：

**方式 1：项目级密钥配置**（适合单项目）

```bash
# 创建项目的密钥文件（不会被 git 追踪）
echo "VIBE_MANAGER_GITHUB_TOKEN=your_token_here" \
  > /path/to/project/config/keys.env

# 验证加载
vibe3 serve status
```

**方式 2：使用 direnv**（推荐，适合多项目）

```bash
# 安装 direnv
brew install direnv

# 项目根目录创建 .envrc
echo "source ~/.vibe/config/keys.env" > .envrc

# 允许加载
direnv allow

# 验证
echo $VIBE_MANAGER_GITHUB_TOKEN
```

**方式 3：Shell 环境变量**（全局生效）

```bash
# 添加到 ~/.zshrc 或 ~/.bashrc
export VIBE_MANAGER_GITHUB_TOKEN="your_token_here"

# 重新加载
source ~/.zshrc
```

**常见问题**：

**Q: 启动 `vibe3 serve` 时警告 `VIBE_MANAGER_GITHUB_TOKEN not configured`？**

A: Python 进程没有加载密钥。解决方案：
1. 创建项目的 `config/keys.env` 文件
2. 或安装配置 `direnv`
3. 或在启动前手动导出：`export VIBE_MANAGER_GITHUB_TOKEN=xxx && vibe3 serve start`

**Q: 为什么不使用 `python-dotenv`？**

A: Vibe Center 是 Shell + Python 混合项目，`direnv` 更通用，可同时服务于两层。

**相关文档**：
- `CLAUDE.md` HARD RULES 第 17 条 — Secret Management
- `docs/specs/env-override-models-json.md` — 环境变量覆盖机制

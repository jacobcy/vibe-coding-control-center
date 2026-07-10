---
name: vibe-project-check
description: Use after `vibe init` to verify target-project configuration completeness, tool availability, and environment readiness. Interactively prompts user to fill missing items. Orchestrates existing commands without adding Python code. Supports cross-project vibe3 readiness verification (Phase 5-8). Do not use for system-level installation issues (use vibe-onboard instead).
---

# /vibe-project-check - 项目配置检查与补全

## Overview

检查 vibe3 生态项目的配置是否完整、正确，发现缺失项时交互式询问用户是否补全。

## When to Use

用于目标 repo 已执行 `vibe init` 后的配置、工具、adapter 和 prompt readiness 检查。

## Required Reading

- `docs/standards/plugin-setup-standard.md`
- `docs/standards/v3/skill-trigger-standard.md`

## 职责边界

- **负责**：当前 repo / 目标项目的配置完整性、工具可用性、adapter 对应 CLI、prompt readiness、被 orchestra 管理所需的本地条件
- **不负责**：机器级安装修复、全局 CLI 安装、claude-mem worker 运维、skills inventory 审计

分流规则：

- 全局安装、doctor、keys、Claude/Codex 外部工具链上游问题 → `skills/vibe-onboard/SKILL.md`
- skills 安装、symlink、全局/项目级差距分析 → `skills/vibe-skills-manager/SKILL.md`
- 仅需项目导览 / 命令索引 → `skills/vibe-instruction/SKILL.md`

如检查项涉及 Claude / Codex adapter、hooks、MCP、claude-mem 或已知兼容性，先读取：

- `docs/standards/plugin-setup-standard.md`

该标准是当前项目关于外部 agent 工具链、安装形态、已知上游问题和本机规避策略的真源。

**前提**：
- 已经在某个项目中
- 已经执行 `vibe init`（目录结构已创建）
- 想要验证配置是否完整、正确

**适用场景**：
- 新项目初始化后，验证配置是否正确
- Orchestra 启动前，检查项目是否能被管理
- 配置修改后，验证配置是否有效
- 问题诊断时，作为第一道环境检查

**注意**：此 skill 可在任意 repo 中运行。Phase 1–4 检查 vibe-center 项目配置；Phase 5–8 检查跨项目 readiness；Phase 9 检查第三方工具链合规（消费 `plugin-setup-standard.md`）。

**完成后状态**：输出完整的检查报告，所有配置项已验证或补全，项目可以正常运行。

---

## Execution Flow

### Phase 1: vibe init 产物验证

**Step 1.1: 检查 .vibe/config.yaml**

```bash
# 检查文件是否存在
test -f .vibe/config.yaml || echo "missing"

# 检查 YAML 格式（容错处理）
if command -v uv >/dev/null 2>&1; then
  uv run python -c "import sys; yaml_available = False
try:
    import yaml
    yaml_available = True
except ImportError:
    pass
if yaml_available:
    try:
        yaml.safe_load(open('.vibe/config.yaml'))
        print('valid')
    except Exception as e:
        print(f'invalid: {e}')
else:
    print('yaml-check-skipped: PyYAML not installed, skipping format validation')
" || echo "check-failed"
fi

# 检查关键字段
grep -q "^profile:" .vibe/config.yaml && echo "profile found" || echo "profile missing"
grep -q "^adapter:" .vibe/config.yaml && echo "adapter found" || echo "adapter missing"
```

**Step 1.2: 检查项目内 agent 配置覆盖（如存在）**

```bash
test -f .claude/settings.json && echo ".claude/settings.json exists" || echo ".claude/settings.json not present (optional)"
test -f .codex/config.toml && echo ".codex/config.toml exists" || echo ".codex/config.toml not present (optional)"
```

**Step 1.3: 检查 agent 目录结构**

```bash
test -d .agent/workflows && echo "workflows exists" || echo "workflows missing"
test -d .codex/skills && echo "codex skills exists" || echo "codex skills missing"
```

---

### Phase 2: 配置补全检查

**Step 2.1: 检查 .gitignore 条目**

```bash
# 检查必要条目（正确转义点号，检查 .vibe/ 或 .vibe3/）
grep -qE '^\.(vibe|vibe3)/' .gitignore || echo "missing: .vibe/ or .vibe3/"
grep -qE '^\.worktrees/' .gitignore || echo "missing: .worktrees/"
grep -qE '^\.agent/plans/' .gitignore || echo "missing: .agent/plans/"
grep -qE '^\.agent/reports/' .gitignore || echo "missing: .agent/reports/"
grep -qE '^temp/' .gitignore || echo "missing: temp/"
```

修复操作（交互式）：
```bash
# 询问用户是否添加缺失条目
# 用户确认后追加到 .gitignore
```

**Step 2.2: 检查 GitHub labels**

```bash
# 获取现有 labels
gh label list --limit 100

# 检查必要 labels
for label in state/ready state/claimed state/in-progress state/blocked state/handoff state/review state/merge-ready state/done state/failed; do
  gh label list | grep -q "$label" || echo "missing: $label"
done
```

修复操作（交互式）：
```bash
# 询问用户是否创建缺失 labels
# 用户确认后批量创建
```

---

### Phase 3: Orchestra 管理配置

**Step 3.1: 检查 vibe-manager GitHub token**

```bash
# 检查 config/keys.env（精确匹配，避免注释干扰）
test -f config/keys.env && grep -q '^VIBE_MANAGER_GITHUB_TOKEN=' config/keys.env && echo "found in config/keys.env"

# 检查环境变量
test -n "$VIBE_MANAGER_GITHUB_TOKEN" && echo "found in env"

# 检查 ~/.vibe/config/keys.env
test -f ~/.vibe/config/keys.env && grep -q '^VIBE_MANAGER_GITHUB_TOKEN=' ~/.vibe/config/keys.env && echo "found in ~/.vibe/config/keys.env"
```

修复操作（交互式，**避免泄露密钥到 shell history**）：
```
Agent: 未找到 VIBE_MANAGER_GITHUB_TOKEN 配置。

       请选择配置方式：
       A. 创建 config/keys.env 文件（推荐，项目级配置）
       B. 使用 direnv 管理（适合多项目）

       你希望使用哪种方式？
User: A

Agent: 请手动编辑 config/keys.env 文件，添加：
       VIBE_MANAGER_GITHUB_TOKEN=your_token_here

       注意：不要在命令行中直接输入 token，避免泄露到 shell history。

       完成后按回车继续...
```

**Step 3.2: 验证 GitHub token 权限**

```bash
# 使用配置的 token 验证（而非默认 gh 认证）
if [ -n "$VIBE_MANAGER_GITHUB_TOKEN" ]; then
  GH_TOKEN="$VIBE_MANAGER_GITHUB_TOKEN" gh api user
else
  gh auth status
fi
```

**Step 3.3: 验证 repo 写权限**

```bash
# 解析 remote（支持 GitHub Enterprise 和标准 GitHub）
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

# 提取 owner/repo（host-agnostic，支持 HTTPS 和 SSH）
REPO=$(echo "$REMOTE_URL" | sed -E 's|.*[:/]([^/]+/[^/]+)\.git$|\1|')

# 检查是否为 GitHub 仓库
if echo "$REMOTE_URL" | grep -qE 'github\.com|github\.'; then
  # 使用配置的 token 检查权限
  if [ -n "$VIBE_MANAGER_GITHUB_TOKEN" ]; then
    GH_TOKEN="$VIBE_MANAGER_GITHUB_TOKEN" gh api "repos/$REPO" --jq '.permissions.push'
  else
    gh api "repos/$REPO" --jq '.permissions.push'
  fi
else
  echo "非 GitHub 仓库，跳过权限检查"
fi
```

**Step 3.4: 检查 scene_base_ref**

```bash
# 读取配置
grep "scene_base_ref" config/v3/settings.yaml || echo "not configured"

# 获取分支名
SCENE_BASE_REF=$(grep "scene_base_ref" config/v3/settings.yaml | awk '{print $2}')

# 检查分支是否存在
git branch -r | grep -q "$SCENE_BASE_REF" && echo "branch exists" || echo "branch missing"
```

修复操作（**跨平台兼容**）：
```bash
# 检测操作系统
if [ "$(uname)" = "Darwin" ]; then
  # macOS
  sed -i '' "s/scene_base_ref:.*/scene_base_ref: main/" config/v3/settings.yaml
else
  # Linux
  sed -i "s/scene_base_ref:.*/scene_base_ref: main/" config/v3/settings.yaml
fi
```

---

### Phase 4: 运行时验证

**Step 4.1: 验证 vibe3 scan**

```bash
vibe3 scan all --dry-run
```

**Step 4.2: 检查 Python 环境**

```bash
uv run python --version
test -f pyproject.toml && echo "pyproject.toml exists" || echo "pyproject.toml missing"

# 依赖安装探针：验证核心依赖真装了（不只看 pyproject.toml 存在）
# uv sync --check 不存在，用 import 探针代替
uv run python -c "import typer, rich, pydantic, pydantic_settings, loguru; print('deps: ok')" 2>&1 || echo "BROKEN: 核心依赖未装，运行 uv sync"
```

**Step 4.3: 检查工具链依赖**

```bash
# 检查 gh CLI 是否安装
which gh >/dev/null 2>&1 && echo "gh installed" || echo "gh missing"

# 检查 vibe 命令是否可用
which vibe >/dev/null 2>&1 && echo "vibe installed" || echo "vibe missing"
```

**Step 4.4: 验证 GitHub token 配置**

```bash
# 运行 vibe keys check（底层事实来源）
vibe keys check
```

---

### Phase 5: Global Runtime Asset Completeness

检查 `~/.vibe/` 运行时资产是否完整（由 `vibe update run` 分发）。

**Step 5.1: 检查 prompts 配置文件**

```bash
# 检查 prompts.yaml
test -f ~/.vibe/config/prompts/prompts.yaml && echo "ok" || echo "MISSING: ~/.vibe/config/prompts/prompts.yaml"

# 检查 prompt-recipes.yaml
test -f ~/.vibe/config/prompts/prompt-recipes.yaml && echo "ok" || echo "MISSING: ~/.vibe/config/prompts/prompt-recipes.yaml"
```

**Step 5.2: 检查 supervisor 配置**

```bash
# 检查 manager.md
test -f ~/.vibe/supervisor/manager.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/manager.md"

# 检查 supervisor handoff material
test -f ~/.vibe/supervisor/apply.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/apply.md"

# 检查 policies
test -f ~/.vibe/supervisor/policies/common.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/policies/common.md"
test -f ~/.vibe/supervisor/policies/run.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/policies/run.md"
test -f ~/.vibe/supervisor/policies/plan.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/policies/plan.md"
test -f ~/.vibe/supervisor/policies/review.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/policies/review.md"
```

**Step 5.4: 检查 governance material catalog**

```bash
# 检查 prompt-recipes.yaml 引用的 governance materials
test -f ~/.vibe/supervisor/governance/assignee-pool.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/governance/assignee-pool.md"
test -f ~/.vibe/supervisor/governance/roadmap-intake.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/governance/roadmap-intake.md"
test -f ~/.vibe/supervisor/governance/cron-supervisor.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/governance/cron-supervisor.md"
test -f ~/.vibe/supervisor/governance/code-auditor.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/governance/code-auditor.md"
test -f ~/.vibe/supervisor/governance/audit-observation.md && echo "ok" || echo "MISSING: ~/.vibe/supervisor/governance/audit-observation.md"
```

**Step 5.5: 检查全局 skills**

```bash
# 检查 vibe-commit skill
test -f ~/.vibe/skills/vibe-commit/SKILL.md && echo "ok" || echo "MISSING: ~/.vibe/skills/vibe-commit/SKILL.md"
```

**修复操作**：

如果发现缺失，提示用户：
```
Agent: 发现全局运行时资产缺失（共 14 项）。

       需要回到 vibe-center repo 运行以下命令同步：
       vibe update run

       同步后重新运行此检查确认完整性。

       是否现在停止检查，等待同步完成？(y/n)
User: y

Agent: 已停止检查。请切换到 vibe-center repo 运行：
       cd /path/to/vibe-center
       vibe update run

       完成后回到此项目重新运行 vibe-project-check。
```

**验证**: 所有 13 个路径均存在。

---

### Phase 6: Target Repo Init State

检查目标 repo（当前工作目录）是否已正确初始化。

**Step 6.1: 检查 .vibe/config.yaml**

```bash
# 检查文件是否存在
test -f .vibe/config.yaml || echo "MISSING: .vibe/config.yaml (run 'vibe init --profile <name>')"

# 检查 profile 字段
grep -q "^profile:" .vibe/config.yaml && echo "profile: ok" || echo "MISSING: profile field in .vibe/config.yaml"
```

**Step 6.2: 检查 .vibe/settings.yaml 有效性（如果存在）**

```bash
# 检查 YAML 格式（容错处理）
if test -f .vibe/settings.yaml; then
  if command -v uv >/dev/null 2>&1; then
    uv run python -c "import sys; yaml_available = False
try:
    import yaml
    yaml_available = True
except ImportError:
    pass
if yaml_available:
    try:
        yaml.safe_load(open('.vibe/settings.yaml'))
        print('settings.yaml: valid')
    except Exception as e:
        print(f'INVALID: .vibe/settings.yaml is not valid YAML: {e}')
else:
    print('settings.yaml: yaml-check-skipped: PyYAML not installed, skipping format validation')
" || echo "settings.yaml: check-failed"
  fi
else
  echo "settings.yaml: not present (optional, ok)"
fi
```

**Step 6.3: 检查 Git repo 状态**

```bash
# 检查 HEAD commit 是否存在
git rev-parse HEAD >/dev/null 2>&1 || echo "MISSING: no HEAD commit (not a git repo?)"

# 检查 remote origin 是否配置
git remote get-url origin >/dev/null 2>&1 || echo "WARNING: no remote 'origin' configured"

# 检查当前分支
git rev-parse --abbrev-ref HEAD >/dev/null 2>&1 || echo "MISSING: cannot determine current branch"
```

**修复操作**：

根据缺失项提供具体指导：
- 无 `.vibe/config.yaml` → "运行 `vibe init --profile minimal|github-flow` 初始化此 repo"
- 缺失 profile 字段 → "编辑 `.vibe/config.yaml` 添加 `profile: <name>`"
- 无效 settings → "修复 `.vibe/settings.yaml` 的 YAML 格式"
- 无 git HEAD → "先初始化 git repo: `git init`"

**验证**: 所有检查通过或明确显示 "optional, ok"。

---

### Phase 7: Agent/Toolchain Availability

检查 agent 运行所需的工具链是否就绪。

**Step 7.1: 检查基础工具链**

```bash
# 全量 doctor：覆盖 essential + 可选工具 + claude-plugins + role token 警告
# （--essential 只查 7 个核心 CLI，会漏掉 Manager Token 降级、plugin 状态等）
vibe doctor
```

> 注意 `vibe doctor` 全量会输出 role-specific token 警告（如 "Manager Token Not configured, 双层防护降级为单层"）。该警告应纳入汇总报告，不要忽略。

**Step 7.2: 检查密钥配置**

```bash
# 验证 GitHub token 等密钥
vibe keys check
```

**Step 7.3: 检查 GitHub CLI 认证**

```bash
# 验证 gh 认证状态
gh auth status
```

**Step 7.4: 检查后端 CLI（根据配置）**

```bash
# 读取 adapter 配置
ADAPTER=$(grep -E "^adapter:" .vibe/config.yaml 2>/dev/null | awk '{print $2}')

# 检查对应后端 CLI 是否存在
case "$ADAPTER" in
  claude|"")
    command -v claude >/dev/null 2>&1 || echo "MISSING: claude CLI not found"
    ;;
  codex)
    command -v codex >/dev/null 2>&1 || echo "MISSING: codex CLI not found"
    ;;
  opencode)
    command -v opencode >/dev/null 2>&1 || echo "MISSING: opencode CLI not found"
    ;;
  gemini)
    command -v gemini >/dev/null 2>&1 || echo "MISSING: gemini CLI not found"
    ;;
  *)
    # 自定义 adapter profile（如 vibe-center）：从 backend 配置推断实际 CLI
    # 读 config/keys.env 或 ~/.vibe/config/keys.env 的 VIBE_BACKEND_* 字段
    BACKEND=$(grep -hE '^VIBE_(DEFAULT_)?BACKEND=' config/keys.env ~/.vibe/config/keys.env 2>/dev/null | head -1 | cut -d= -f2)
    case "$BACKEND" in
      claude) command -v claude >/dev/null 2>&1 || echo "MISSING: claude CLI (backend=$BACKEND)" ;;
      codex) command -v codex >/dev/null 2>&1 || echo "MISSING: codex CLI (backend=$BACKEND)" ;;
      *) echo "NOTE: custom adapter='$ADAPTER' backend='$BACKEND'，手动确认对应 CLI" ;;
    esac
    ;;
esac
```

如 adapter 对应 Claude / Codex，且用户问题涉及 hooks、MCP、记忆、已知兼容性、手工补丁或安装差异，进一步检查与解释应以 `docs/standards/plugin-setup-standard.md` 为准；不要在本 skill 内重新定义外部工具链安装矩阵。

**修复操作**：

根据失败项提供具体指导：
- `vibe doctor` 失败 → "安装缺失工具（参见 `vibe doctor` 输出）"
- `vibe keys` 失败 → "运行 `vibe keys init` 或手动配置密钥"
- `gh auth` 失败 → "运行 `gh auth login`"
- 后端 CLI 缺失 → "安装所需后端 CLI 或修改 `.vibe/config.yaml` 中的 adapter 配置"

**验证**: 所有命令退出码为 0 且输出符合预期。

---

### Phase 8: Core Command Prompt Readiness

测试核心命令（`plan`, `run`, `review`）是否能正确渲染 prompt。

**Step 8.1: 检查 plan prompt readiness**

```bash
# 需要已绑定 flow 的分支；使用当前分支测试
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

if vibe3 flow show "$BRANCH" >/dev/null 2>&1; then
  vibe3 plan --dry-run --show-prompt --branch "$BRANCH" 2>&1 | grep -q "prompt" && echo "plan prompt: ok" || echo "WARNING: plan --show-prompt produced no prompt output"
else
  echo "SKIP: plan prompt check (no flow bound to current branch; this is expected in uninitialized repos)"
fi
```

**Step 8.2: 检查 run prompt readiness**

```bash
# 测试 run 命令 prompt 渲染
vibe3 run --dry-run --show-prompt "test readiness check" 2>&1 | grep -q "prompt\|Task:" && echo "run prompt: ok" || echo "WARNING: run --show-prompt produced no output"
```

**Step 8.3: 检查 review prompt readiness**

```bash
# 需要已绑定 flow 的分支
if vibe3 flow show "$BRANCH" >/dev/null 2>&1; then
  vibe3 review --dry-run --show-prompt --branch "$BRANCH" 2>&1 | grep -q "prompt\|reviewer" && echo "review prompt: ok" || echo "WARNING: review --show-prompt produced no output"
else
  echo "SKIP: review prompt check (no flow bound to current branch)"
fi
```

**Step 8.4: internal manager prompt readiness**

```bash
# internal manager 需要 issue number；优先从 task/issue-<num> 分支名解析
ISSUE=$(printf "%s" "$BRANCH" | sed -n 's/.*issue-\([0-9][0-9]*\).*/\1/p')

if test -n "$ISSUE"; then
  vibe3 internal manager "$ISSUE" --no-async --dry-run --show-prompt --branch "$BRANCH" 2>&1 | grep -q "prompt_content\|manager.supervisor_content" && echo "internal manager prompt: ok" || echo "WARNING: internal manager --show-prompt produced no prompt output"
else
  echo "SKIP: internal manager prompt check (current branch does not expose issue number)"
fi
```

**修复操作**：

根据结果提供指导：
- 未初始化 repo 中的 SKIP → 预期行为，提示用户先运行 `vibe init`
- Prompt 输出缺失 → "手动检查 `vibe3 <command> --dry-run --show-prompt`；可能是配置或 prompt 渲染问题"
- `internal manager` SKIP → "当前分支无法解析 issue number；切换到 `task/issue-<num>` / `dev/issue-<num>` 分支或手动提供 issue number 后复查"

**验证**: `plan`, `run`, `review`, `internal manager` 均产生 prompt 输出；无 issue number 的分支明确显示 SKIP。

---

### Phase 9: 第三方工具链合规（消费 plugin-setup-standard）

**先读真源**：`docs/standards/plugin-setup-standard.md`。该标准的"总览"表 + 各工具 §验证 段落是检查依据。本 phase 跑标准中文档化的验证命令矩阵，**不重新定义安装矩阵**。

按工具逐项验证，结果分三类：

- **MISSING/BROKEN**：工具未装、命令失败、doctor 报错
- **KNOWN_ISSUE_VIOLATION**：命中标准"已知上游问题"且违反规避策略（如端口漂移）
- **VERSION_DRIFT**：实际版本与标准 pin 不一致（提示对齐方向，不自动升降级）

**Step 9.1: CLI 工具版本核对**

```bash
# 标准 §总览 pin 版本：rtk 0.43.0 / graphify 0.9.8 / specify 0.12.4
for cmd in rtk graphify specify openspec; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "$cmd: $(${cmd} --version 2>&1 | head -1)"
  else
    echo "MISSING: $cmd CLI not found"
  fi
done
```

**Step 9.2: claude-mem 运行时（含已知端口漂移检查）**

```bash
# 版本 + 状态
npx claude-mem@latest status 2>&1 | grep -iE "version|port|pid" || echo "BROKEN: claude-mem status failed"

# 已知问题：端口漂移（标准 §claude-mem doctor 端口漂移说明）
# doctor 在某些路径用公式端口 37700 + (uid % 100)，而非 settings.json 的 CLAUDE_MEM_WORKER_PORT
UID_NUM=$(id -u)
FORMULA_PORT=$((37700 + UID_NUM % 100))
SETTINGS_PORT=$(jq -r '.CLAUDE_MEM_WORKER_PORT' ~/.claude-mem/settings.json 2>/dev/null || echo "")
if [ -n "$SETTINGS_PORT" ] && [ "$SETTINGS_PORT" != "$FORMULA_PORT" ]; then
  echo "KNOWN_ISSUE_VIOLATION: claude-mem port drift (formula=$FORMULA_PORT, settings=$SETTINGS_PORT)"
  echo "  规避: 将 settings.json 端口改为 $FORMULA_PORT 后 restart worker，否则 doctor 误报 Worker no response"
fi

# doctor 综合健康（All required checks passed 才算 ok）
npx claude-mem@latest doctor 2>&1 | grep -iE "✗|✓|passed|failed" | head -10
```

**Step 9.3: Claude plugins 状态**

```bash
# 标准 §总览 pin：claude-mem 13.10.2 / superpowers 6.1.0 / codex 1.0.2 / claude-hud 0.3.0
if command -v claude >/dev/null 2>&1; then
  claude plugin list 2>&1 | grep -iE "claude-mem|superpowers|codex|claude-hud|context7" || echo "BROKEN: claude plugin list empty"
else
  echo "SKIP: Claude plugin checks (claude CLI not installed; valid for Codex-only adapter)"
fi
```

**Step 9.4: Codex context tools 配置层**

```bash
# 标准 §claude-mem Codex 兼容：13.10.2 用 marketplace plugin 方式
# 已知问题：npx install --ide codex-cli 注册本地路径 marketplace，Codex 要求 Git 源会失败
codex plugin list 2>&1 | grep "claude-mem@" | head -1 || echo "MISSING: claude-mem not installed in Codex"

# 若 plugin not installed，检查 marketplace 是否误注册为本地路径
codex plugin marketplace list 2>&1 | grep claude-mem

# Codex MCP 注册状态。server 名称以 config.toml 中的真实名称为准。
codex mcp get context7 || echo "MISSING: Codex MCP context7"
codex mcp get exa-search || echo "MISSING: Codex MCP exa-search"
codex mcp get mcp-search || echo "MISSING: Codex MCP mcp-search (claude-mem)"
```

这一步只证明配置已注册，不证明当前 agent session 已加载工具。修复 marketplace 的路径见标准 §claude-mem Codex 兼容（Git marketplace 方式）。

Codex MCP 的 key 由 `codex mcp get <server>` 显示的 server 私有配置负责传入。不得用当前 shell 的 `$EXA_API_KEY` / `$CONTEXT7_API_KEY` 是否存在来判断 Codex MCP 是否配置；否则会把 MCP 私有 env 误报为缺失。

**Step 9.5: Codex 当前 agent 工具面与最小调用探针**

Codex 配置层通过后，必须在**当前执行 project-check 的 Codex session** 中检查实际工具面，并执行最小只读调用。不要只看 `codex mcp list/get`。非 Codex adapter 跳过本步骤并进入对应平台检查。

Codex 的预期工具名：

- Context7：`mcp__context7__resolve_library_id`、`mcp__context7__query_docs`
- Exa：`mcp__exa_search__web_search_exa`、`mcp__exa_search__web_fetch_exa`
- claude-mem：`mcp__mcp_search__search`、`mcp__mcp_search__timeline`、`mcp__mcp_search__get_observations`

使用当前 host 的工具发现能力（tool search / available tools inventory）确认上述工具存在，然后逐项执行：

1. Context7：调用 `resolve_library_id` 查询一个公开库（例如 `claude-mem`）。
2. Exa：调用 `web_search_exa`，限制为 1 条公开结果。
3. claude-mem：调用 `search`，限制为 1–3 条索引结果；不在 readiness probe 中抓取 observation 全文。

按以下状态裁决：

- `READY`：配置存在、预期工具出现在当前工具面、最小调用成功。
- `RESTART_REQUIRED`：配置存在，但当前工具面缺少对应工具。提示用户重启当前 Claude/Codex session 后重跑 project-check；不得报告整体 ready。
- `BROKEN`：配置缺失，或工具已加载但最小调用失败。保留原始错误摘要，并按 plugin-setup-standard 对应工具的安装/修复路径处理。

**Step 9.6: Claude MCP/plugin 与 shell key（仅 Claude adapter）**

```bash
# 以下检查只用于 Claude adapter；Codex 不使用当前 shell env 判定 MCP 私有 key。
test -n "$EXA_API_KEY" && echo "exa: EXA_API_KEY present" || echo "MISSING: EXA_API_KEY (Claude adapter)"
claude plugin list 2>&1 | grep -q context7 && echo "context7: ok (plugin)" || echo "WARNING: context7 plugin not found"
```

**Step 9.7: 版本漂移判定**

对每项实际版本与标准 pin 比对。漂移时不自动升降级，输出建议并询问用户对齐方向：
- 实际 > pin 且功能正常 → 提示"保最新 + 更新标准 pin"或"降到 pin"
- 实际 < pin → 提示"升级到 pin"或"降 pin 到实际"

**修复操作**：

按分类分流，**不自行修复上游问题**：
- **MISSING/BROKEN** → 引导按标准 §对应工具 的官方安装命令修复；claude-mem doctor 失败先跑 `npx claude-mem@latest repair`
- **RESTART_REQUIRED** → 配置已存在但当前 session 未加载工具；重启对应 agent session 后重新执行 Step 9.5，不重复安装
- **KNOWN_ISSUE_VIOLATION** → 按标准规避策略告警，询问用户是否应用（如端口对齐需 restart worker，有短暂中断）
- **VERSION_DRIFT** → 询问对齐方向，确认后才动手；superpowers 等跨 session 工具默认保最新 + 更新 pin

**验证**: 所有工具 `--version` / `status` 正常；当前 adapter 的 context tools 配置存在且最小调用成功；claude-mem doctor 全绿；无 KNOWN_ISSUE_VIOLATION。`RESTART_REQUIRED` 必须在重启 session 并复查成功后才能转为 `READY`。

---

## Guardrails（交互原则）

1. **渐进式检查**：一个检查接一个检查，不会"停止"
2. **交互式修复**：每发现一个问题都询问用户是否修复
3. **用户可控**：用户决定是否修复，用什么方式修复
4. **密钥安全**：密钥输入时引导用户手动编辑文件，避免泄露到 shell history
5. **最后汇总**：所有检查完成后输出完整报告

---

## 汇总报告

**输出格式**：

```
## 检查完成

### 已验证（vibe-center 项目配置）
✅ vibe init 产物完整
✅ .gitignore 已补全 2 个条目
✅ 已创建 9 个 GitHub labels
✅ vibe-manager token 已配置
✅ 运行时验证通过

### Cross-Project Readiness（跨项目就绪状态）
✅ Global runtime assets: 13/13 present
✅ Target repo init: .vibe/config.yaml valid, profile=github-flow
✅ Agent/toolchain: all essential tools available
✅ Prompt readiness: plan/run/review/internal manager ok

### Diagnostic Categories（诊断分类）
如果发现失败，输出以下分类之一：
- GLOBAL_INSTALL_MISSING → "回到 vibe-center repo 运行 `vibe update run`"
- TARGET_REPO_NOT_INIT → "在目标 repo 运行 `vibe init --profile minimal|github-flow`"
- TARGET_CONFIG_INVALID → "编辑 `.vibe/settings.yaml` 修复格式"
- BACKEND_OR_KEY_MISSING → "安装缺失的后端 CLI 或运行 `vibe keys init`"
- PROMPT_READINESS_GAP → "检查 flow 绑定、issue 分支名与 prompt 资产完整性"
- TOOLCHAIN_DRIFT → "Phase 9：实际版本与 plugin-setup-standard pin 不一致，按建议对齐"
- RESTART_REQUIRED → "Phase 9：工具已配置但当前 agent session 未加载；重启 session 后重跑实际调用探针"
- KNOWN_ISSUE_VIOLATION → "Phase 9：命中标准已知上游问题且违反规避策略（如 claude-mem 端口漂移）"

### 项目状态
你的项目现在可以：
- 被 orchestra 管理
- 运行 vibe3 serve 启动服务
- 使用完整的 flow/task 工作流

### 下一步
运行 `vibe3 serve start` 启动 orchestra 服务
```

---

## 参考

- Issue #1810: feat(skills): add vibe-project-check skill
- Issue #1926: 扩展 vibe-project-check 为跨项目 vibe3 readiness 验证
- Issue #1924: global runtime distribution
- Issue #1925: config loading with target override
- Issue #1905: internal manager dry-run/show-prompt
- Issue #3322: Phase 9 第三方工具链合规检查（消费 plugin-setup-standard）
- CLAUDE.md: Skill-First 原则
- 现有 skill: `vibe-onboard`, `vibe-check`
- 设计文档: `docs/superpowers/specs/2026-06-02-vibe-project-check-redesign.md`

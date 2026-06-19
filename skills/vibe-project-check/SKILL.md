---
name: vibe-project-check
description: Use after `vibe init` to verify project configuration completeness. Interactively prompts user to fill missing items. Orchestrates existing commands without adding Python code. Supports cross-project vibe3 readiness verification (Phase 5-8). Do not use for system-level installation issues (use vibe-onboard instead).
---

# /vibe-project-check - 项目配置检查与补全

检查 vibe3 生态项目的配置是否完整、正确，发现缺失项时交互式询问用户是否补全。

**前提**：
- 已经在某个项目中
- 已经执行 `vibe init`（目录结构已创建）
- 想要验证配置是否完整、正确

**适用场景**：
- 新项目初始化后，验证配置是否正确
- Orchestra 启动前，检查项目是否能被管理
- 配置修改后，验证配置是否有效
- 问题诊断时，作为第一道环境检查

**注意**：此 skill 可在任意 repo 中运行。Phase 1–4 检查 vibe-center 项目配置；Phase 5–8 检查跨项目 readiness。

**完成后状态**：输出完整的检查报告，所有配置项已验证或补全，项目可以正常运行。

---

## Phase 1: vibe init 产物验证

**Step 1.1: 检查 .vibe/config.yaml**

```bash
# 检查文件是否存在
test -f .vibe/config.yaml || echo "missing"

# 检查 YAML 格式（容错处理）
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import sys; yaml_available = False
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

**Step 1.2: 检查 .claude/settings.json**

```bash
test -f .claude/settings.json && echo "exists" || echo "missing"
```

**Step 1.3: 检查 .agent/ 目录结构**

```bash
test -d .agent/skills && echo "skills exists" || echo "skills missing"
test -d .agent/workflows && echo "workflows exists" || echo "workflows missing"
```

---

## Phase 2: 配置补全检查

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

## Phase 3: Orchestra 管理配置

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

## Phase 4: 运行时验证

**Step 4.1: 验证 vibe3 scan**

```bash
vibe3 scan --dry-run
```

**Step 4.2: 检查 Python 环境**

```bash
uv run python --version
test -f pyproject.toml && echo "pyproject.toml exists" || echo "pyproject.toml missing"
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

## Phase 5: Global Runtime Asset Completeness

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

## Phase 6: Target Repo Init State

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
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import sys; yaml_available = False
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

## Phase 7: Agent/Toolchain Availability

检查 agent 运行所需的工具链是否就绪。

**Step 7.1: 检查基础工具链**

```bash
# 检查必需工具
vibe doctor --essential
```

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
esac
```

**修复操作**：

根据失败项提供具体指导：
- `vibe doctor` 失败 → "安装缺失工具（参见 `vibe doctor` 输出）"
- `vibe keys` 失败 → "运行 `vibe keys init` 或手动配置密钥"
- `gh auth` 失败 → "运行 `gh auth login`"
- 后端 CLI 缺失 → "安装所需后端 CLI 或修改 `.vibe/config.yaml` 中的 adapter 配置"

**验证**: 所有命令退出码为 0 且输出符合预期。

---

## Phase 8: Core Command Prompt Readiness

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

## 交互原则

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
- CLAUDE.md: Skill-First 原则
- 现有 skill: `vibe-onboard`, `vibe-check`
- 设计文档: `docs/superpowers/specs/2026-06-02-vibe-project-check-redesign.md`

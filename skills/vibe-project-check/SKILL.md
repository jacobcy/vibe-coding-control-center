---
name: vibe-project-check
description: 项目配置检查与补全。在 `vibe init` 之后运行，检查项目配置是否完整正确，发现缺失项时交互式询问用户是否补全。编排现有命令和文件读取，不新增 Python 代码。
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

### 已验证
✅ vibe init 产物完整
✅ .gitignore 已补全 2 个条目
✅ 已创建 9 个 GitHub labels
✅ vibe-manager token 已配置
✅ 运行时验证通过

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
- CLAUDE.md: Skill-First 原则
- 现有 skill: `vibe-onboard`, `vibe-check`
- 设计文档: `docs/superpowers/specs/2026-06-02-vibe-project-check-redesign.md`

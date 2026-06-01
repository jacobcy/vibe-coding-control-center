---
name: vibe-project-check
description: 项目冷启动环境检查。用于检查当前项目是否满足 vibe3 冷启动条件、初始化后验证环境、或 orchestra 启动前检查。编排现有原子命令，不新增 Python 代码。
---

# /vibe-project-check - 项目冷启动环境检查

检查当前项目是否满足 vibe3 冷启动条件，确保所有必要依赖和配置就绪。

**适用场景**：
- 创建新项目后，验证环境是否就绪
- 初始化 vibe3 配置后，检查配置是否正确
- 启动 orchestra 服务前，确认依赖是否满足
- 定期健康检查，确保环境未损坏

**完成后状态**：输出完整的环境检查报告，标记通过/失败/警告项，给出修复建议（不自动执行修复）。

---

## 核心职责

1. **Git 仓库检查**：确认在 git 仓库中且有 remote
2. **vibe3 配置检查**：确认 vibe3 数据目录存在
3. **依赖环境检查**：确认 Python 和 vibe3 可用
4. **Orchestra 状态检查**：确认 orchestra 服务状态
5. **GitHub 集成检查**：确认 gh 认证和 repo 可访问
6. **工具链检查**：确认必要工具和密钥

**分层原则**：
- 本 skill 只负责编排现有命令和解释输出
- 事实来源统一为底层命令输出（git、vibe3、gh、uv）
- 不新增 `src/vibe3/` 代码，不创建新的服务层

---

## 停止点

检查完成后输出报告，包含：
- ✅ 通过项（绿色对勾）
- ❌ 失败项（红色叉号）
- ⚠️ 警告项（黄色警告符号）
- 汇总统计：X/6 项通过
- 修复建议（不自动执行）

停止，等待用户根据报告决定下一步。

---

## 完整流程

```
/vibe-project-check
  ├─ Step 1: Git 仓库检查
  │   ├─ git rev-parse --show-toplevel
  │   ├─ git remote -v
  │   ├─ 若失败：标记 ❌，记录原因
  │   └─ 若成功：标记 ✅，显示仓库路径和 remote
  │
  ├─ Step 2: vibe3 配置检查
  │   ├─ ls -la "$(git rev-parse --git-dir)/vibe3/"
  │   ├─ vibe3 handoff status
  │   ├─ 若失败：标记 ❌，提示需初始化
  │   └─ 若成功：标记 ✅，显示配置路径
  │
  ├─ Step 3: 依赖环境检查
  │   ├─ uv run python --version
  │   ├─ which vibe3
  │   ├─ 若失败：标记 ❌，提示安装依赖
  │   └─ 若成功：标记 ✅，显示版本信息
  │
  ├─ Step 4: Orchestra 状态检查
  │   ├─ vibe3 serve status
  │   ├─ 若未运行：标记 ⚠️，提示可选启动
  │   ├─ 若运行中：标记 ✅，显示服务状态
  │   └─ 若失败：标记 ❌，提示检查配置
  │
  ├─ Step 5: GitHub 集成检查
  │   ├─ gh auth status
  │   ├─ 解析 owner/repo（从 git remote）
  │   ├─ gh api repos/{owner}/{repo}
  │   ├─ 若认证失败：标记 ❌，提示 gh auth login
  │   ├─ 若 repo 不可访问：标记 ⚠️，提示检查权限
  │   └─ 若成功：标记 ✅，显示 repo 信息
  │
  ├─ Step 6: 工具链检查
  │   ├─ vibe doctor --essential
  │   ├─ 若失败：标记 ❌，列出缺失工具
  │   └─ 若成功：标记 ✅，显示工具状态
  │
  └─ Step 7: 汇总报告
      ├─ 统计通过/失败/警告项数量
      ├─ 列出需要修复的项目
      ├─ 给出修复建议（命令示例）
      └─ 停止，等待用户决策
```

---

## 详细步骤

### Step 1: Git 仓库检查

**目标**：确认当前目录在 git 仓库中，且有 remote 配置。

**执行命令**：

```bash
# 检查是否在 git 仓库中
git rev-parse --show-toplevel

# 检查是否有 remote
git remote -v
```

**判断标准**：
- ✅ 在 git 仓库中且有 remote
- ❌ 不在 git 仓库中（`git rev-parse` 失败）
- ⚠️ 在 git 仓库中但无 remote（`git remote -v` 为空）

**失败时的修复建议**：
- 不在 git 仓库：`git init`
- 无 remote：`git remote add origin <url>`

### Step 2: vibe3 配置检查

**目标**：确认 vibe3 数据目录存在，配置已初始化。

**执行命令**：

```bash
# 获取 git 目录路径（支持 worktree 场景）
GIT_DIR=$(git rev-parse --git-dir)

# 检查 vibe3 数据目录
ls -la "$GIT_DIR/vibe3/"

# 检查 handoff 状态
vibe3 handoff status
```

**判断标准**：
- ✅ vibe3 目录存在且 handoff 可用
- ❌ vibe3 目录不存在
- ⚠️ vibe3 目录存在但 handoff 状态异常

**失败时的修复建议**：
- 目录不存在：运行项目初始化脚本（如 `zsh scripts/init.sh`）

**重要**：在 worktree 中 `.git` 是文件而非目录，必须使用 `$(git rev-parse --git-dir)` 获取正确的 git 目录路径。

### Step 3: 依赖环境检查

**目标**：确认 Python 和 vibe3 命令可用。

**执行命令**：

```bash
# 检查 Python 版本
uv run python --version

# 检查 vibe3 命令路径
which vibe3
```

**判断标准**：
- ✅ Python 和 vibe3 都可用
- ❌ Python 不可用（`uv run python` 失败）
- ❌ vibe3 不可用（`which vibe3` 失败）

**失败时的修复建议**：
- Python 不可用：安装 uv（`curl -LsSf https://astral.sh/uv/install.sh | sh`）
- vibe3 不可用：运行安装脚本（`zsh scripts/install.sh`）

### Step 4: Orchestra 状态检查

**目标**：确认 orchestra 服务状态。

**执行命令**：

```bash
vibe3 serve status
```

**判断标准**：
- ✅ Orchestra 正在运行
- ⚠️ Orchestra 未运行（可选服务，不强制要求）
- ❌ 命令执行失败（配置问题）

**失败时的修复建议**：
- 未运行：`vibe3 serve start`（可选）
- 命令失败：检查 vibe3 配置和日志

### Step 5: GitHub 集成检查

**目标**：确认 gh 认证状态和 repo 访问权限。

**执行命令**：

```bash
# 检查 gh 认证状态
gh auth status

# 解析 owner/repo
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

# 如果 remote URL 存在，解析并访问 repo
if [ -n "$REMOTE_URL" ]; then
  # 解析 owner/repo（支持 https 和 ssh 格式）
  REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github.com[/:]||; s|\.git$||')
  gh api "repos/$REPO"
fi
```

**判断标准**：
- ✅ gh 已认证且 repo 可访问
- ❌ gh 未认证（`gh auth status` 失败）
- ⚠️ gh 已认证但 repo 不可访问（权限问题）
- ⚠️ 无 remote URL，跳过 repo 检查

**失败时的修复建议**：
- 未认证：`gh auth login`
- repo 不可访问：检查 GitHub 权限设置

**边界处理**：
- 如果解析 remote URL 失败（如无 remote），标记为 ⚠️ 并跳过 API 调用
- 如果 repo 不在 GitHub（如 GitLab），标记为 ⚠️ 并说明不支持

### Step 6: 工具链检查

**目标**：确认必要工具和依赖已安装。

**执行命令**：

```bash
vibe doctor --essential
```

**判断标准**：
- ✅ 所有必要工具已安装
- ❌ 有缺失的必要工具
- ⚠️ 有可选工具缺失

**失败时的修复建议**：
- 根据 `vibe doctor` 输出安装缺失工具

### Step 7: 汇总报告

**输出格式**：

```
## 项目环境检查报告

### 检查结果
✅ Git 仓库: /path/to/repo (origin: https://github.com/owner/repo.git)
✅ vibe3 配置: /path/to/.git/vibe3/
✅ 依赖环境: Python 3.11.6, vibe3 at /usr/local/bin/vibe3
⚠️ Orchestra: 未运行 (可选服务)
✅ GitHub 集成: 已认证, repo: owner/repo
✅ 工具链: 所有必要工具已安装

### 汇总
通过: 5/6
失败: 0/6
警告: 1/6

### 修复建议
[如有失败或警告项，列出具体修复命令]

### 下一步
环境基本就绪，可以开始使用 vibe3 开发。
建议运行 `/vibe-onboard` 完成初始配置。
```

---

## 事实来源

本 skill 不直接做底层事实判断，统一以这些命令为准：

- `git rev-parse`、`git remote`：Git 仓库事实
- `vibe3 handoff status`：vibe3 配置事实
- `uv run python --version`、`which vibe3`：依赖环境事实
- `vibe3 serve status`：Orchestra 服务事实
- `gh auth status`、`gh api`：GitHub 集成事实
- `vibe doctor --essential`：工具链事实

如果命令执行失败或输出与预期不符，以命令输出为准，记录实际错误信息。

---

## 注意事项

1. **不自动修复**：只检查和报告，不自动执行修复操作
2. **支持 worktree**：使用 `git rev-parse --git-dir` 获取正确的 git 目录路径
3. **边界处理**：处理无 remote、非 GitHub repo 等场景
4. **错误捕获**：每个命令都要捕获错误输出，避免中断后续检查
5. **命令存在性**：如果命令不存在（如 `gh`、`vibe3`），标记为 ❌ 而不是报错

---

## 风险与回退

### 命令不存在风险（低）

**场景**：目标项目缺少 `gh`、`vibe3` 等命令。

**处理**：
- 捕获命令不存在的错误（`command not found`）
- 标记为 ❌
- 在修复建议中给出安装指引

### Remote URL 解析失败（中）

**场景**：无 remote 或 remote URL 格式不标准。

**处理**：
- 检查 `git remote get-url origin` 返回值
- 如果失败，标记 GitHub 集成检查为 ⚠️
- 跳过 `gh api repos/...` 调用

### Worktree 场景（低）

**场景**：在 worktree 中 `.git` 是文件而非目录。

**处理**：
- 使用 `$(git rev-parse --git-dir)` 获取真实 git 目录
- 不硬编码 `.git/vibe3/` 路径

---

## 约束检查

- ✅ 只调用已有命令，不新增 `src/vibe3/` 代码
- ✅ 不创建 `project_check_service.py` 或 `project_check.py`
- ✅ 事实来源统一为底层命令输出
- ✅ 输出格式清晰，易于理解

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
- 想要检查是否有遗漏的配置项

**适用场景**：
- 新项目初始化后，验证配置是否正确
- Orchestra 启动前，检查项目是否能被管理
- 配置修改后，验证配置是否有效
- 问题诊断时，作为第一道环境检查

**完成后状态**：输出完整的检查报告，所有配置项已验证或补全，项目可以正常运行。

---

## 核心职责

1. **vibe init 产物验证**：验证 `.vibe/config.yaml`、`.claude/settings.json`、`.agent/` 目录结构
2. **配置补全检查**：检查并补全 `.gitignore` 条目、GitHub labels
3. **Orchestra 管理配置**：检查 vibe-manager token、权限、repo 配置、scene_base_ref
4. **运行时验证**：验证 `vibe3 scan`、Python 环境

**分层原则**：
- 本 skill 只负责编排现有命令和解释输出
- 配置文件检查 → 文件读取 + 解析
- 运行时检查 → 命令调用 + 输出解析
- 权限检查 → API 调用
- 不新增 `src/vibe3/` 代码，不创建新的服务层

---

## 交互原则

1. **渐进式检查**：一个检查接一个检查，不会"停止"
2. **交互式修复**：每发现一个问题都询问用户是否修复
3. **用户可控**：用户决定是否修复，用什么方式修复
4. **提供选项**：对于有多种解决方案的问题，列出选项让用户选择
5. **最后汇总**：所有检查完成后输出完整报告

---

## 完整流程

```
/vibe-project-check
  │
  ├─ Phase 1: vibe init 产物验证
  │   ├─ 检查 .vibe/config.yaml
  │   │   ├─ 读取文件内容
  │   │   ├─ 验证 YAML 格式是否正确
  │   │   ├─ 验证 profile 字段是否存在
  │   │   ├─ 验证 adapter 字段是否存在（vibe-center profile）
  │   │   └─ 若失败：提示配置错误，建议检查文件内容
  │   │
  │   ├─ 检查 .claude/settings.json
  │   │   ├─ 检查文件是否存在
  │   │   └─ 若失败：询问是否从模板复制
  │   │
  │   └─ 检查 .agent/ 目录结构
  │       ├─ 检查 .agent/skills/ 是否存在
  │       ├─ 检查 .agent/workflows/ 是否存在
  │       └─ 若失败：询问是否创建
  │
```

### Phase 1 详细步骤

**Step 1.1: 检查 .vibe/config.yaml**

执行：
```bash
# 读取文件
cat .vibe/config.yaml

# 验证 YAML 格式（Python 解析）
python -c "import yaml; yaml.safe_load(open('.vibe/config.yaml'))"

# 检查关键字段
grep "profile:" .vibe/config.yaml
grep "adapter:" .vibe/config.yaml
```

判断标准：
- ✅ 文件存在且 YAML 格式正确
- ✅ profile 字段存在
- ✅ adapter 字段存在（如果是 vibe-center profile）
- ❌ 文件不存在或格式错误
- ❌ 缺少必要字段

失败时的交互：
```
Agent: 发现 .vibe/config.yaml 配置错误：
       - YAML 格式不正确
       或
       - 缺少 profile 字段

       建议检查文件内容或重新运行 `vibe init`。
       是否继续检查其他项？
User: 继续
```

---

**Step 1.2: 检查 .claude/settings.json**

执行：
```bash
# 检查文件是否存在
test -f .claude/settings.json && echo "exists" || echo "missing"
```

判断标准：
- ✅ 文件存在
- ❌ 文件不存在

失败时的交互：
```
Agent: 发现 .claude/settings.json 不存在。
       这个文件通常由 `vibe init` 从模板复制。

       是否从模板复制？
User: 是

Agent: [执行复制]
       ✅ 已创建 .claude/settings.json
```

---

**Step 1.3: 检查 .agent/ 目录结构**

执行：
```bash
# 检查目录是否存在
test -d .agent/skills && echo "skills exists" || echo "skills missing"
test -d .agent/workflows && echo "workflows exists" || echo "workflows missing"
```

判断标准：
- ✅ .agent/skills/ 存在
- ✅ .agent/workflows/ 存在
- ❌ 目录不存在

失败时的交互：
```
Agent: 发现以下目录不存在：
       - .agent/skills/
       - .agent/workflows/

       是否创建这些目录？
User: 创建

Agent: [创建目录]
       ✅ 已创建 .agent/skills/
       ✅ 已创建 .agent/workflows/
```

  │
  ├─ Phase 2: 配置补全检查
  │   │
  │   ├─ 检查 .gitignore 条目
  │   │   ├─ 读取 .gitignore 内容
  │   │   ├─ 检查是否包含：.vibe/ 或 .vibe3/、.worktrees/、.agent/plans/、.agent/reports/、temp/
  │   │   ├─ 若缺失：列出缺失条目，询问是否添加
  │   │   └─ 修复：读取文件 → 追加条目 → 写回文件
  │   │
  │   └─ 检查 GitHub labels
  │       ├─ 调用 gh label list
  │       ├─ 检查是否存在：state/ready、state/claimed、state/in-progress、state/blocked、state/handoff、state/review、state/merge-ready、state/done、state/failed
  │       ├─ 若缺失：列出缺失 labels，询问是否创建
  │       └─ 修复：调用 gh label create
  │

### Phase 2 详细步骤

**Step 2.1: 检查 .gitignore 条目**

执行：
```bash
# 读取 .gitignore
cat .gitignore

# 检查必要条目
grep -q "^.vibe/" .gitignore || echo "missing: .vibe/"
grep -q "^.worktrees/" .gitignore || echo "missing: .worktrees/"
grep -q "^.agent/plans/" .gitignore || echo "missing: .agent/plans/"
grep -q "^.agent/reports/" .gitignore || echo "missing: .agent/reports/"
grep -q "^temp/" .gitignore || echo "missing: temp/"
```

必要条目列表：
- `.vibe/` 或 `.vibe3/`
- `.worktrees/`
- `.agent/plans/`
- `.agent/reports/`
- `temp/`

失败时的交互：
```
Agent: 发现 .gitignore 缺少以下条目：
       - .vibe3/
       - temp/

       是否添加这些条目？
User: 添加

Agent: [读取 .gitignore]
       [追加条目]
       [写回文件]
       ✅ 已添加到 .gitignore
```

修复实现：
```bash
# 追加条目到 .gitignore
echo -e "\n# Vibe3 entries (added by vibe-project-check)" >> .gitignore
echo ".vibe3/" >> .gitignore
echo "temp/" >> .gitignore
```

---

**Step 2.2: 检查 GitHub labels**

执行：
```bash
# 获取现有 labels
gh label list --limit 100

# 检查必要 labels
gh label list | grep -q "state/ready" || echo "missing: state/ready"
gh label list | grep -q "state/claimed" || echo "missing: state/claimed"
# ... 其他 labels
```

必要 labels 列表：
```yaml
- name: state/ready
  description: Ready for manager dispatch
  color: "0E8A16"
- name: state/claimed
  description: 已认领,待进入执行
  color: "BFDADC"
- name: state/in-progress
  description: 执行中
  color: "0052CC"
- name: state/blocked
  description: 阻塞中
  color: "D73A4A"
- name: state/handoff
  description: 待交接
  color: "FBCA04"
- name: state/review
  description: 待 review
  color: "5319E7"
- name: state/merge-ready
  description: 已满足合并条件
  color: "0E8A16"
- name: state/done
  description: 已完成
  color: "0E8A16"
- name: state/failed
  description: Execution failed and needs recovery
  color: "B60205"
```

失败时的交互：
```
Agent: 发现缺少以下 labels:
       - state/ready
       - state/claimed
       - state/in-progress
       - state/blocked
       - state/handoff
       - state/review
       - state/merge-ready
       - state/done
       - state/failed

       是否创建这些 labels？
User: 创建

Agent: [创建 labels]
       ✅ 已创建 9 个 GitHub labels
```

修复实现：
```bash
# 创建 labels
gh label create "state/ready" --description "Ready for manager dispatch" --color "0E8A16"
gh label create "state/claimed" --description "已认领,待进入执行" --color "BFDADC"
gh label create "state/in-progress" --description "执行中" --color "0052CC"
gh label create "state/blocked" --description "阻塞中" --color "D73A4A"
gh label create "state/handoff" --description "待交接" --color "FBCA04"
gh label create "state/review" --description "待 review" --color "5319E7"
gh label create "state/merge-ready" --description "已满足合并条件" --color "0E8A16"
gh label create "state/done" --description "已完成" --color "0E8A16"
gh label create "state/failed" --description "Execution failed and needs recovery" --color "B60205"
```

  │
  ├─ Phase 3: Orchestra 管理配置
  │   │
  │   ├─ 检查 vibe-manager GitHub token
  │   │   ├─ 检查 config/keys.env 是否包含 VIBE_MANAGER_GITHUB_TOKEN
  │   │   ├─ 或检查环境变量 VIBE_MANAGER_GITHUB_TOKEN
  │   │   ├─ 或检查 ~/.vibe/config/keys.env
  │   │   ├─ 若缺失：列出配置方式，询问用户选择，引导输入 token
  │   │   └─ 修复：创建配置文件或导出到环境变量
  │   │
  │   ├─ 验证 GitHub token 权限
  │   │   ├─ 调用 gh auth status
  │   │   ├─ 调用 gh api user
  │   │   └─ 若失败：提示 token 无效或权限不足
  │   │
  │   ├─ 验证 repo 写权限
  │   │   ├─ 解析 git remote 获取 owner/repo
  │   │   ├─ 调用 gh api repos/{owner}/{repo}
  │   │   ├─ 检查 permissions.push
  │   │   └─ 若失败：提示需要 repo 写权限
  │   │
  │   └─ 检查 scene_base_ref
  │       ├─ 读取 config/v3/settings.yaml 的 scene_base_ref
  │       ├─ 检查分支是否存在
  │       └─ 若失败：询问是否修改为 main/master
  │

### Phase 3 详细步骤

**Step 3.1: 检查 vibe-manager GitHub token**

执行：
```bash
# 检查 config/keys.env
test -f config/keys.env && grep -q "VIBE_MANAGER_GITHUB_TOKEN" config/keys.env && echo "found in config/keys.env"

# 检查环境变量
test -n "$VIBE_MANAGER_GITHUB_TOKEN" && echo "found in env"

# 检查 ~/.vibe/config/keys.env
test -f ~/.vibe/config/keys.env && grep -q "VIBE_MANAGER_GITHUB_TOKEN" ~/.vibe/config/keys.env && echo "found in ~/.vibe/config/keys.env"
```

判断标准：
- ✅ 在任一位置找到 token
- ❌ 未找到 token

失败时的交互：
```
Agent: 未找到 VIBE_MANAGER_GITHUB_TOKEN 配置。

       需要配置 GitHub token 才能让 orchestra 管理项目。

       请选择配置方式：
       A. 创建 config/keys.env 文件（推荐，项目级配置）
       B. 使用 direnv 管理（适合多项目）
       C. 导出到 shell 配置文件（全局生效）

       你希望使用哪种方式？
User: A

Agent: 请输入你的 GitHub token（需要有 repo 权限）：
User: ghp_xxxx

Agent: ✅ 已保存到 config/keys.env
       注意：该文件不会被 git 追踪
```

修复实现（方式 A）：
```bash
# 创建目录
mkdir -p config

# 写入 token
echo "VIBE_MANAGER_GITHUB_TOKEN=ghp_xxxx" > config/keys.env

# 提示用户
echo "✅ 已保存到 config/keys.env"
echo "注意：该文件不会被 git 追踪"
```

修复实现（方式 B）：
```bash
# 检查 direnv
command -v direnv || echo "请先安装 direnv: brew install direnv"

# 创建 .envrc
echo "source ~/.vibe/config/keys.env" > .envrc

# 允许加载
direnv allow

# 提示用户
echo "✅ direnv 配置完成"
echo "请将 token 添加到 ~/.vibe/config/keys.env:"
echo "VIBE_MANAGER_GITHUB_TOKEN=your_token_here"
```

修复实现（方式 C）：
```bash
# 检测 shell
SHELL_RC="$HOME/.zshrc"
test -n "$BASH_VERSION" && SHELL_RC="$HOME/.bashrc"

# 追加配置
echo "export VIBE_MANAGER_GITHUB_TOKEN=\"ghp_xxxx\"" >> "$SHELL_RC"

# 提示用户
echo "✅ 已添加到 $SHELL_RC"
echo "请运行: source $SHELL_RC"
```

---

**Step 3.2: 验证 GitHub token 权限**

执行：
```bash
# 检查认证状态
gh auth status

# 验证 token 有效性
gh api user
```

判断标准：
- ✅ Token 有效
- ❌ Token 无效或过期

失败时的交互：
```
Agent: ❌ GitHub token 无效或权限不足

       请检查：
       1. Token 是否正确
       2. Token 是否过期
       3. Token 是否有必要的权限（repo）

       是否重新配置 token？
User: 是

Agent: [返回 Step 3.1 重新配置]
```

---

**Step 3.3: 验证 repo 写权限**

执行：
```bash
# 解析 remote
REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")

# 提取 owner/repo（支持 https 和 ssh 格式）
REPO=$(echo "$REMOTE_URL" | sed -E 's|.*github\.com[/:]||; s|\.git$||')

# 检查权限
gh api "repos/$REPO" --jq '.permissions.push'
```

判断标准：
- ✅ 有 push 权限
- ❌ 无 push 权限

失败时的交互：
```
Agent: ❌ 当前 token 对仓库 $REPO 无写权限

       请检查：
       1. Token 是否有 repo 权限
       2. 你是否是该仓库的协作者

       是否重新配置 token？
User: 是

Agent: [返回 Step 3.1 重新配置]
```

---

**Step 3.4: 检查 scene_base_ref**

执行：
```bash
# 读取配置
grep "scene_base_ref" config/v3/settings.yaml || echo "not configured"

# 获取分支名
SCENE_BASE_REF=$(grep "scene_base_ref" config/v3/settings.yaml | awk '{print $2}')

# 检查分支是否存在
git branch -r | grep -q "$SCENE_BASE_REF" && echo "branch exists" || echo "branch missing"
```

判断标准：
- ✅ scene_base_ref 配置正确且分支存在
- ⚠️ 未配置 scene_base_ref（使用默认值）
- ❌ 配置的分支不存在

失败时的交互：
```
Agent: 发现 scene_base_ref 配置错误：
       当前值: develop
       但分支 develop 不存在

       可用分支：
       - main
       - master

       使用哪个分支？
User: main

Agent: [修改配置]
       ✅ 已更新 scene_base_ref: main
```

修复实现：
```bash
# 修改配置文件
sed -i '' "s/scene_base_ref:.*/scene_base_ref: main/" config/v3/settings.yaml
```

  │
  └─ Phase 4: 运行时验证
      │
      ├─ 验证 vibe3 scan
      │   ├─ 调用 vibe3 scan --dry-run
      │   └─ 若失败：提示错误原因
      │
      └─ 检查 Python 环境
          ├─ 调用 uv run python --version
          └─ 若失败：提示安装 Python 或 uv
```

### Phase 4 详细步骤

**Step 4.1: 验证 vibe3 scan**

执行：
```bash
# 运行 dry-run
vibe3 scan --dry-run
```

判断标准：
- ✅ vibe3 scan --dry-run 成功
- ❌ 执行失败

失败时的交互：
```
Agent: ❌ vibe3 scan --dry-run 失败

       错误信息：
       [错误输出]

       可能原因：
       1. 数据库损坏
       2. 配置错误
       3. 依赖缺失

       建议运行 `vibe doctor` 检查系统环境。
       是否继续检查其他项？
User: 继续
```

---

**Step 4.2: 检查 Python 环境**

执行：
```bash
# 检查 Python 版本
uv run python --version

# 检查 pyproject.toml
test -f pyproject.toml && echo "pyproject.toml exists" || echo "pyproject.toml missing"
```

判断标准：
- ✅ Python 可用且版本满足要求
- ❌ Python 不可用或版本过低

失败时的交互：
```
Agent: ❌ Python 环境不满足要求

       请安装：
       - Python 3.12+
       - uv (Python 包管理器)

       安装命令：
       curl -LsSf https://astral.sh/uv/install.sh | sh

       是否继续检查其他项？
User: 继续
```

  │
  └─ Step 5: 汇总报告
      ├─ 统计通过/失败/警告项数量
      ├─ 列出已修复的项目
      ├─ 给出项目状态说明
      └─ 停止，等待用户决策
```

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

## 停止点

检查完成后输出报告，包含：
- ✅ 通过项（绿色对勾）
- ❌ 失败项（红色叉号）
- ⚠️ 警告项（黄色警告符号）
- 汇总统计：已验证和已修复的项目
- 项目状态说明
- 下一步建议

停止，等待用户根据报告决定下一步。

---

## 注意事项

1. **交互式询问**：每一步都需要用户明确确认，不要强制修复
2. **尊重用户选择**：如果用户拒绝某个修复，不要反复提示或强行执行
3. **密钥安全**：密钥输入时要保证安全，不要记录或泄露用户的密钥信息
4. **清晰指引**：对于有问题的检查项，要给出明确、可执行的解决方案
5. **友好引导**：对于不熟悉技术的用户也要容易理解，使用简单明了的语言

---

## 风险与缓解

### 风险 1：文件读写权限

**场景**：用户可能没有文件写权限

**缓解**：
- 修复前先检查权限
- 失败时提示用户手动修改

### 风险 2：GitHub API 限流

**场景**：频繁调用 `gh label create` 可能触发限流

**缓解**：
- 批量创建时添加延迟
- 失败时提示用户稍后重试

### 风险 3：配置文件格式变化

**场景**：`vibe init` 可能更新配置文件格式

**缓解**：
- 只检查关键字段（profile、adapter）
- 对格式变化保持容错

---

## 参考

- Issue #1779: feat(skills): 新增 vibe-project-check skill 用于 vibe3 生态项目冷启动环境检查
- Issue #1800: 关闭原因 - 实现方向错误
- CLAUDE.md: Skill-First 原则
- 现有 skill: `vibe-onboard`, `vibe-check`
- 设计文档: `docs/superpowers/specs/2026-06-02-vibe-project-check-redesign.md`

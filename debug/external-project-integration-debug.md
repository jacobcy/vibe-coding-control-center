# External Project Integration Debug Guide

> 本文记录将 vibe-center 作为工具集成到外部项目的完整调试流程，包含已知缺口与验证方法。

## 目标流程

```
1. git clone <vibe-center-repo> ~/vibe-center
2. cd ~/vibe-center && scripts/install.sh      # 安装到 ~/.vibe/
3. source ~/.zshrc                              # 重载 shell
4. mkdir ~/test && cd ~/test && git init
5. vibe init --profile github-flow             # 初始化外部项目 (非 vibe3 init)
6. 在项目内使用 skills 和 python tools
```

> **注意**：文档中有时写的是 `vibe3 init`，实际命令是 `vibe init`（shell 命令），`vibe3` CLI 无 `init` 子命令。见 [缺口 #1](#gap-1-vibe3-init-命令不存在)。

---

## 环境验证步骤

### Step 1: 验证安装产物

```bash
# 检查核心安装目录
ls ~/.vibe/

# 预期输出应包含：
# alias/ assets/ bin/ config/ lib/ lib3/ scripts/ skills/ src/
# loader.sh  pyproject.toml  settings.yaml  skills.json  uv.lock
```

```bash
# 检查 skills 目录内容
ls ~/.vibe/skills/

# 正常：应有 vibe-* 目录（如 vibe-new、vibe-continue 等）
# 异常：只有 agent-browser、brainstorming 等第三方 symlink（见 Gap #2）
```

```bash
# 检查 assets 子目录
ls ~/.vibe/assets/

# 正常：应有 policies/ 和 prompts/
# 异常：只有 policies/，缺少 prompts/（见 Gap #3）
```

```bash
# 检查 manifests 目录
ls ~/.vibe/manifests/

# 正常：应有 skills.json
# 异常：目录不存在（见 Gap #4），skills.json 实际在 ~/.vibe/skills.json
```

### Step 2: 验证 vibe init

```bash
cd ~/test
git init
vibe init --profile github-flow -y --skip-labels

# 验证生成内容
cat .vibe/config.yaml
ls .agent/ .claude/
ls .claude/skills/   # 正常情况下应有 vibe-* 软链接
```

**已知问题**：`.claude/skills/` 和 `.agent/skills/` 为空（见 Gap #5）

### Step 3: 验证 Python 工具可用性

```bash
# 检查 vibe3 命令
vibe3 --help

# 检查 flow 功能
vibe3 flow status

# 若提示找不到 vibe3，检查 PATH
which vibe3
echo $UV_PROJECT_ENVIRONMENT
```

### Step 4: 验证 Skills 可用性

在外部项目内打开 Claude Code，输入 `/vibe-new` 检查 skill 是否被识别。

```bash
# 手动检查 .claude/skills/ 内容
ls -la .claude/skills/

# 若为空，手动建立软链接验证
ln -sfn ~/.vibe/skills/vibe-new .claude/skills/vibe-new
```

---

## 已知缺口

### Gap #1: `vibe3 init` 命令不存在

- **现象**：运行 `vibe3 init` 报错 `No such command 'init'`
- **原因**：`vibe3` CLI（Python）无 `init` 子命令，该功能在 Shell 侧 `vibe init`
- **临时方案**：使用 `vibe init --profile <minimal|github-flow|vibe-center>`
- **Issue**：[#1093](https://github.com/jacobcy/vibe-coding-control-center/issues/1093)

### Gap #2: `install.sh` 不复制 `skills/vibe-*` 到 `~/.vibe/skills/`

- **现象**：`~/.vibe/skills/` 只含 superpowers 等第三方 symlink，无 `vibe-*` skill
- **原因**：`install.sh` 第 147 行的 dir 列表不含 `skills`（含 `bin lib lib3 config scripts alias src`）
- **影响**：`vibe init` 执行 Step 6（setup .claude/skills symlinks）时找不到任何 `vibe-*` 可链接
- **临时方案**：手动 `cp -R ~/vibe-center/skills/vibe-* ~/.vibe/skills/`
- **Issue**：[#1087](https://github.com/jacobcy/vibe-coding-control-center/issues/1087)

### Gap #3: `install.sh` 不创建 `~/.vibe/assets/prompts/`

- **现象**：`~/.vibe/assets/` 下只有 `policies/`，无 `prompts/`
- **原因**：`install.sh` 第 169 行只同步 `.agent/policies`，无对应 prompts 同步
- **影响**：外部项目 `config.yaml` 中 `prompts_root` 路径无效，依赖 prompts 的运行时功能降级
- **临时方案**：手动 `mkdir -p ~/.vibe/assets/prompts`（目前 prompts 功能暂未被强依赖）
- **Issue**：[#1089](https://github.com/jacobcy/vibe-coding-control-center/issues/1089)

### Gap #4: `profiles.sh` 中 `skills_manifest` 路径与实际安装路径不一致

- **现象**：`vibe init` 生成的 `.vibe/config.yaml` 写入 `skills_manifest: ~/.vibe/manifests/skills.json`，但该文件不存在
- **原因**：`install.sh` 将 `skills.json` 放在 `~/.vibe/skills.json`，而 `profiles.sh` 引用 `~/.vibe/manifests/skills.json`
- **影响**：config.yaml 中的路径为死路，skills manifest 无法被 runtime 加载
- **临时方案**：手动 `mkdir -p ~/.vibe/manifests && cp ~/.vibe/skills.json ~/.vibe/manifests/skills.json`
- **Issue**：[#1090](https://github.com/jacobcy/vibe-coding-control-center/issues/1090)

### Gap #5: `github-flow` profile 禁用 skills，导致 `.claude/skills/` 始终为空

- **现象**：`vibe init --profile github-flow` 后 `.claude/skills/` 为空目录
- **原因**：`profiles.sh` 中 `PROFILE_GITHUB_FLOW` 设置 `features.skills:false`，跳过 Step 6 的 symlink 建立
- **影响**：外部项目用最常见的 github-flow profile 初始化后，Claude Code 无法发现任何 vibe-* skill
- **临时方案**：改用 `vibe init --profile vibe-center`，或手动链接 `~/.vibe/skills/vibe-*`
- **Issue**：[#1091](https://github.com/jacobcy/vibe-coding-control-center/issues/1091)

### Gap #6: `vibe init` 不生成 CLAUDE.md 模板

- **现象**：init 完成后，项目只有 `.vibe/config.yaml`、`.agent/`、`.claude/` 空目录，没有 CLAUDE.md
- **原因**：`lib/init.sh` 只检查并警告缺少 CLAUDE.md，不生成最小模板
- **影响**：外部项目 Agent 缺少上下文，不知道 `vibe3` 命令存在，也不知道使用哪个 profile
- **临时方案**：参考本 repo 的 CLAUDE.md，手动创建最小 CLAUDE.md
- **Issue**：[#1092](https://github.com/jacobcy/vibe-coding-control-center/issues/1092)

### Gap #7: `vibe init` 不检查 GitHub remote，label 创建静默全失败但报假成功（运行验证）

- **现象（命令验证）**：
  ```
  ⚠️  Failed to create/update label: state/ready
  ... (10 个全部失败)
  ✅ GitHub labels created   # ← 假成功
  ```
- **原因**：`lib/init.sh` 只检查 `gh` 命令是否存在，不检查 remote。`gh label create` 失败被降级为 warning，循环继续，最终仍报 `✅ GitHub labels created`
- **影响**：
  - 用户认为 labels 已创建，实际 0 个创建成功
  - `vibe flow start` / supervisor 依赖 `state/*` labels 的所有功能全部失败
  - 无明确报错，用户难以定位原因
- **临时方案**：手动创建 remote 后重新运行 `vibe init`，或 `gh label create` 逐一手动执行
- **Issue**：[#1094](https://github.com/jacobcy/vibe-coding-control-center/issues/1094)

### Gap #8: `UV_PROJECT_ENVIRONMENT` 不在 `loader.sh` 中，外部项目运行 vibe 命令污染 `.venv`（运行验证）

- **现象（命令验证）**：
  ```bash
  cd ~/test && ~/.vibe/bin/vibe flow status
  # Creating virtual environment at: .venv  ← 在外部项目里创建 venv
  # Downloading openai (1.1MiB)...（下载全量依赖）
  ```
- **原因**：`install.sh` 将 `UV_PROJECT_ENVIRONMENT` 写入 `~/.zshrc`，但 `~/.vibe/loader.sh` 中没有这个变量。在新 shell / CI / 非交互式环境下，变量未设置，uv 在当前目录就地创建 `.venv`
- **影响**：外部项目被注入 `.venv/`（~200MB），下载耗时数分钟，若未 `.gitignore` 会意外提交
- **临时方案**：手动 `export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/vibe-center"` 后重试
- **Issue**：[#1095](https://github.com/jacobcy/vibe-coding-control-center/issues/1095)

---

## 完整缺口影响链

```
install.sh
  |- [Gap #2] skills/ 未复制 -> vibe-* skill 不在 ~/.vibe/skills/
  |- [Gap #3] prompts/ 未创建 -> ~/.vibe/assets/prompts/ 不存在
  +- [Gap #8] UV_PROJECT_ENVIRONMENT 不在 loader.sh -> 外部项目 .venv 污染 *验证*

profiles.sh
  +- [Gap #4] skills_manifest 路径错误 -> ~/.vibe/manifests/ 不存在

vibe init --profile github-flow
  |- [Gap #5] features.skills=false -> .claude/skills/ 始终为空
  |- [Gap #6] 不生成 CLAUDE.md -> Agent 无上下文
  +- [Gap #7] 不检查 GitHub remote -> label 全部静默失败 + 假成功报告 *验证*

文档
  +- [Gap #1] 文档写 vibe3 init，实际是 vibe init -> 用户迷失
```

---

## 快速诊断命令

```bash
# 一键诊断外部项目集成状态
echo "=== vibe install check ===" && \
  ls ~/.vibe/skills/vibe-* 2>/dev/null && echo "OK: vibe-* skills exist" || echo "FAIL: no vibe-* skills in ~/.vibe/skills/" && \
  ls ~/.vibe/assets/prompts 2>/dev/null && echo "OK: prompts dir exists" || echo "FAIL: ~/.vibe/assets/prompts missing" && \
  ls ~/.vibe/manifests/skills.json 2>/dev/null && echo "OK: manifests/skills.json exists" || echo "FAIL: ~/.vibe/manifests/skills.json missing" && \
echo "=== project init check ===" && \
  ls .claude/skills/ 2>/dev/null | grep vibe && echo "OK: vibe-* skills linked" || echo "FAIL: no vibe-* in .claude/skills/" && \
  ls .vibe/config.yaml 2>/dev/null && echo "OK: config.yaml exists" || echo "FAIL: .vibe/config.yaml missing" && \
  ls CLAUDE.md 2>/dev/null && echo "OK: CLAUDE.md exists" || echo "WARN: CLAUDE.md missing"
```

---

## 参考

- [portability 设计文档](../plans/2026-05-16-vibe3-portability-decoupling-design.md)
- [portability 验证文档](../superpowers/plans/2026-05-17-portability-validation.md)
- `scripts/install.sh` — 全局安装脚本
- `lib/init.sh` — `vibe init` 命令实现
- `lib/profiles.sh` — Profile 定义

---
name: vibe-new
description: Use when starting or switching to a new human-collaboration task. Confirm the target issue, bootstrap the corresponding dev/issue flow scene, and hand off to the chosen implementation workflow. Do not use for resuming an existing branch; use vibe-continue instead.
---

# /vibe-new

从 issue 进入一个新的协作 flow。

## 输入解析（优化：减少确认步骤）

从用户输入提取意图：

- `/vibe-new 2540` → issue=2540, branch=dev/issue-2540
- `/vibe-new 2540 create worktree` → issue=2540, worktree=true
- `/vibe-new 2540 superpowers` → issue=2540, workflow=superpowers
- `/vibe-new 2540 worktree superpowers` → issue=2540, worktree=true, workflow=superpowers
- `/vibe-new`（无参数）→ 询问 issue 号

**推断规则**：
- branch 名：`dev/issue-<id>`（自动推断，不问）
- worktree：用户说了 "worktree"/"create worktree" → true
- workflow：用户说了 "superpowers"/"vibe3" 等 → 直接用

## 1. 强制前置检查（优化：并行执行）

**并行执行**以下 4 条命令（不要串行）：

```bash
vibe3 flow show
git status
git fetch origin main
gh issue view <issue-number> --json labels,body,state
```

然后一次性判断：
- 如果已有活跃 flow 且目标 issue 相同 → 留在当前 scope，不要重新 bootstrap
- 如果已有活跃 flow 但需要恢复已有 branch → 改用 `/vibe-continue`
- 如果有明确 issue number 或用户已通过 `/vibe-issue` 完成 intake → 继续

禁止跳过 `vibe3 flow show` 直接进入 bootstrap。

## 2. Pre-Bootstrap Sync Check（强制）

在 bootstrap 前，**必须**检查 origin/main 是否有更新：

检查本地 main 是否落后（fetch 已在 Step 1 完成）：

```bash
git log main..origin/main --oneline | wc -l
```

**决策逻辑**：
- **如果落后 > 0 commits**：
  - 提示用户：`本地 main 分支落后 origin/main {N} commits，新分支将基于最新的 origin/main 创建`
  - 用户确认后直接继续 bootstrap（`vibe3 internal bootstrap` 会自动从 origin/main 创建分支）
- **如果 origin/main 与本地 main 一致**：直接继续 bootstrap

**用户选择**：
- 继续 Bootstrap → 进入 Step 6，由 `vibe3 internal bootstrap` 自动处理 fetch + 分支创建
- 跳过检查 → 记录风险：`vibe3 handoff append "跳过 main 同步检查，用户主动选择"`

**原因**：`vibe3 internal bootstrap` 内部已执行 `git fetch` + `git create_branch_ref(branch, start_ref=origin/main)`，不依赖本地 main 分支状态。新分支始终基于最新的 origin/main 创建，避免从落后代码开始的问题。

## 3. Epic 入口分流检查

在确认目标 issue 后，检查是否为 Epic 主 issue：

使用 Step 1 获取的 issue 数据。

检查逻辑：
- 如果 issue 有 `roadmap/epic` 标签 **且** body 包含 `## Sub-issues` 或 `## 子任务` section：
  - 打印 Sub-issues 列表（从 body 的 `## Sub-issues` section 解析）
  - 告知用户："该 issue 是 Epic 主 issue；主 issue 保持为治理容器，请选择具体 sub-issue 进入 /vibe-new，或先补齐拆分。"
  - 停止 — 不继续 bootstrap 主 issue
- 如果只有 `roadmap/epic` 标签但无 `## Sub-issues` section：
  - 提示用户："该 issue 标记为 Epic 但缺少 ## Sub-issues section，请先由 roadmap decider/manager 补齐拆分，或移除标签后按单 issue 继续"
  - 停止 — 不继续 bootstrap
- 否则继续正常流程

**注意**：必须同时满足标签和 section 两个条件才是有效的 Epic 主 issue。

## 4. 确认未提供的信息（优化：只问未指定的）

从输入解析中已确认的信息**不再询问**：
- worktree 已在输入中指定 → 不问
- workflow 已在输入中指定 → 不问
- 两者都未指定 → 依次询问：
  - 用当前仓库还是新建 worktree
  - 后续打算走哪条实现 workflow

可推荐但不强绑：
- `superpowers:writing-plans`
- `superpowers:executing-plans`
- `openspec:ff`
- repo-native `vibe3 plan/run/review`

## 5. 确认依赖关系

在 bootstrap 前，确认依赖关系：

1. 使用 Step 1 获取的 issue body，检查是否有 `## Dependencies` 或 `## 依赖` section

2. 如果存在依赖：
   - 提取依赖 issue 编号（格式：`Depends on #<id>`、`依赖 #<id>`、`blocked by #<id>`）
   - **验证依赖状态**：
     ```bash
     gh issue view <dep-id> --json state
     ```
   - 如果依赖状态为 `open`：
     - 提示用户："该 issue 存在未关闭的依赖 #<id>，bootstrap 后 flow 将进入 blocked 状态"
     - 等待用户确认是否继续
     - 添加 `--dependency <id>` 参数
   - 如果依赖状态为 `closed`：
     - 提示用户："依赖 #<id> 已关闭，无需阻塞"
     - **不添加** `--dependency` 参数

3. 如果无依赖：继续

## 6. Bootstrap flow scene

**强制要求**：必须使用 `vibe3 internal bootstrap` 作为唯一 bootstrap 路径，禁止手工拼接。

✅ **正确做法**：

```bash
vibe3 internal bootstrap <issue-number> \
  --branch dev/issue-<id> \
  [--worktree] \
  [--related <issue-number>]... \
  [--dependency <issue-number>]... \
  [--reactivate-existing]
```

❌ **禁止做法**：
- `git checkout -b` / `git switch -c` 手工建分支
- `vibe3 flow update` / `vibe3 flow bind` 手工组装 flow
- `vibe3 snapshot save` 单独打快照代替 bootstrap
- `git pull origin main && git checkout -b ...` 手工拉取建分支

**原因**：bootstrap 命令保证幂等性、统一的 actor 签名、完整的 baseline snapshot 和 flow 关系绑定。手工拼接会绕过这些契约，导致 flow 状态不一致。

**如遇 bootstrap 失败**：先诊断问题（网络、权限、分支冲突），不要回退到手工拼接。

这个命令会走共享底层路径，完成：
- branch/flow bootstrap
- task issue 绑定
- related issue 绑定
- dependency issue 阻塞登记（仅 open 状态的依赖）
- worktree context 准备（如果传了 `--worktree`）

## 7. 留痕（Trace）

bootstrap 成功后，根据当前环境留痕：

**判断环境**：
```bash
# 检测是否有 flow 环境
vibe3 flow show
```

**留痕规则**：
- **有 flow 环境**（正常情况）：使用 handoff 记录创建决策
  ```bash
  vibe3 handoff append "vibe-new: flow ready" --actor vibe-new --kind milestone
  ```

- **无 flow 但有 issue**（异常情况）：在 issue 中记录创建失败
  ```bash
  gh issue comment <issue-number> --body "## vibe-new 创建失败

  **原因**：<失败原因>

  **下一步**：<建议操作>
  "
  ```

- **都没有**：无需留痕

**留痕内容应包含**：
- Flow 创建结果（成功/失败）
- Issue 确认状态
- Branch 名称
- Worktree 路径（如有）
- 下一步建议

## 8. 指向 vibe-continue 工作流

bootstrap 完成后，**必须**告知用户下一步是 `/vibe-continue`：

> Flow 已 ready。如选择 vibe3 工作流，请执行 `/vibe-continue` 查看标准工作流方法并开始执行。

标准 vibe3 工作流由 `/vibe-continue` 定义，包含：
- `vibe3 plan` → `vibe3 run` → `vibe3 review` → `vibe3 run --publish`
- 每步之间可用 `vibe3 handoff show @<artifact>` 检查结果
- 详见 `/vibe-continue` 的"标准工作流方法"章节

## 停止条件

完成后应能明确说出：
- issue 已确认
- `dev/issue-<id>` flow 已 ready
- 如果请求了 worktree，执行目录也已 ready
- handoff 已记录
- 下一步建议的 workflow 已明确

## 限制

- 不在没有 issue 的情况下创建 flow
- 不进入业务实现阶段
- 不把 handoff 当真源；先看 `vibe3 flow show`

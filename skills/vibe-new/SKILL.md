---
name: vibe-new
description: Use when starting or switching to a new human-collaboration task. Confirm the target issue, bootstrap the corresponding dev/issue flow scene, and hand off to the chosen implementation workflow. Do not use for resuming an existing branch; use vibe-continue instead.
---

# /vibe-new

从 issue 进入一个新的协作 flow。

## 1. 强制前置检查

进入 `/vibe-new` 前，**必须**先确认当前现场：

```bash
vibe3 flow show
git status
```

根据检查结果决策：
- 如果已有活跃 flow 且目标 issue 相同 → 留在当前 scope，不要重新 bootstrap
- 如果已有活跃 flow 但需要恢复已有 branch → 改用 `/vibe-continue`
- 如果有明确 issue number 或用户已通过 `/vibe-issue` 完成 intake → 继续

禁止跳过 `vibe3 flow show` 直接进入 bootstrap。

## 2. Pre-Bootstrap Sync Check（强制）

在 bootstrap 前，**必须**确保从最新的 origin/main 创建分支：

```bash
# 1. Fetch latest main
git fetch origin main

# 2. 检查本地 main 是否落后
git log main..origin/main --oneline | wc -l
```

**决策逻辑**：
- **如果落后 > 0 commits**：
  - 提示用户：`本地 main 分支落后 origin/main {N} commits，建议先更新再创建新分支`
  - **推荐做法**（快速更新，不影响当前分支）：
    ```bash
    git checkout main
    git pull origin main
    git checkout -
    ```
  - **用户选择**：
    - 同意更新 → 执行上述命令，然后继续 bootstrap
    - 拒绝更新 → 记录风险并询问是否继续：`vibe3 handoff append "跳过 main 同步，新分支基于落后代码创建"`
- **如果 origin/main 与本地 main 一致**：直接继续 bootstrap

**原因**：避免 Issue #1250 类型的问题——长时间重构期间 main 已演进，新分支从一开始就落后会导致后续严重冲突。

## 3. Epic 入口分流检查

在确认目标 issue 后，检查是否为 Epic 主 issue：

```bash
gh issue view <issue-number> --json labels,body
```

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

## 4. 询问两件事

只需要确认：
- 用当前仓库还是新建 worktree
- 后续打算走哪条实现 workflow

可推荐但不强绑：
- `superpowers:writing-plans`
- `superpowers:executing-plans`
- `openspec:ff`
- repo-native `vibe3 plan/run/review`

## 5. 确认依赖关系

在 bootstrap 前，确认依赖关系：

1. 读取目标 issue body（已在 Epic 检查时获取，或重新获取）：
   ```bash
   gh issue view <issue-number> --json body
   ```

2. 检查是否有 `## Dependencies` 或 `## 依赖` section

3. 如果存在依赖：
   - 提示用户："该 issue 存在依赖关系，bootstrap 时需要添加 --dependency 参数"
   - 让用户确认依赖是否已满足（已关闭的依赖不需要添加）
   - **只对未关闭（open）的依赖**添加 `--dependency <id>` 参数

4. 如果无依赖：继续

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

## 7. 记录 handoff

bootstrap 成功后记录稳定恢复点：

```bash
vibe3 handoff append "vibe-new: flow ready" --actor vibe-new --kind milestone
```

## 8. 按需继续

如果已经具备条件，可以继续：

```bash
vibe3 pr create --agent -t "..." -b "..."
```

或者停在这里，转入用户选择的实现 workflow。

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

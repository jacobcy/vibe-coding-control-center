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

**Epic 入口阻断检查**（在确认目标 issue 后）：

```bash
gh issue view <issue-number> --json labels,body
```

检查逻辑：
- 如果 issue 有 `roadmap/rfc` 标签 **且** body 包含 `## Sub-issues` 或 `## 子任务` section：
  - 打印 Sub-issues 列表
  - 告知用户："该 issue 是 epic，请选择具体 sub-issue 进入 /vibe-new"
  - 停止 — 不继续 bootstrap
- 否则继续正常流程

**注意**：必须同时满足标签和 section 两个条件才阻断（有些非 epic issue 可能有 Sub-issues section 但无标签）。

禁止跳过 `vibe3 flow show` 直接进入 bootstrap。

## 2. 询问两件事

只需要确认：
- 用当前仓库还是新建 worktree
- 后续打算走哪条实现 workflow

可推荐但不强绑：
- `superpowers:writing-plans`
- `superpowers:executing-plans`
- `openspec:ff`
- repo-native `vibe3 plan/run/review`

## 3. Bootstrap flow scene

**强制要求**：必须使用 `vibe3 internal bootstrap` 作为唯一 bootstrap 路径，禁止手工拼接。

**自动解析依赖关系**（在 bootstrap 前）：

1. 读取目标 issue body（已在 Step 1 获取，或重新获取）：
   ```bash
   gh issue view <issue-number> --json body
   ```

2. 解析 `## Dependencies` 或 `## 依赖` section

3. 提取依赖关系（匹配以下任一格式）：
   - `Depends on #<id>`
   - `依赖 #<id>`
   - `blocked by #<id>`
   
   对每个匹配项，提取 issue number

4. 检查依赖状态：
   ```bash
   gh issue view <dep-id> --json state
   ```
   
   - 如果任何依赖状态为 `open`：
     - 警告用户："当前 issue 存在未关闭的依赖 #<id>，bootstrap 后 flow 将立即进入 blocked 状态。是否继续？"
     - 等待用户确认
   - 如果所有依赖已关闭或无依赖：继续

5. 组装 bootstrap 命令：
   - 对每个解析到的依赖添加 `--dependency <id>` 参数

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
- dependency issue 阻塞登记
- worktree context 准备（如果传了 `--worktree`）

## 4. 记录 handoff

bootstrap 成功后记录稳定恢复点：

```bash
vibe3 handoff append "vibe-new: flow ready" --actor vibe-new --kind milestone
```

## 5. 按需继续

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

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

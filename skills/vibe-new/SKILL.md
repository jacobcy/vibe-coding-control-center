---
name: vibe-new
description: Use when starting or switching to a new human-collaboration task. Confirm the target issue, bootstrap the corresponding dev/issue flow scene, and hand off to the chosen implementation workflow. Do not use for resuming an existing branch; use vibe-continue instead.
---

# /vibe-new

从 issue 进入一个新的协作 flow。

## 1. 先确认是否适合进入 `/vibe-new`

先看当前现场：

```bash
vibe3 flow show
git status
```

只在下面场景继续：
- 已经有明确的 issue number
- 或用户先经过 `/vibe-issue` 完成了 issue intake

如果当前目标只是恢复已有 branch / flow，改用 `/vibe-continue`。

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

标准调用方式：

```bash
vibe3 internal bootstrap-flow <issue-number> --branch dev/issue-<id> [--worktree]
```

如果需要补充 issue 关系：

```bash
vibe3 internal bootstrap-flow <issue-number> \
  --branch dev/issue-<id> \
  [--worktree] \
  [--related <issue-number>]... \
  [--dependency <issue-number>]...
```

**注意**：标准调用会自动 `git fetch origin` 确保基准分支最新。如果因特殊情况需要手动创建 worktree 和分支，记得先拉取最新代码：

```bash
git pull origin main
git checkout -b dev/issue-<id>
```

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

- 不在 skill 层手工拼接 `flow update` / `flow bind` / `wtnew` 作为 bootstrap 真源
- 不在没有 issue 的情况下创建 flow
- 不进入业务实现阶段
- 不把 handoff 当真源；先看 `vibe3 flow show`

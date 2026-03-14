# 04. Handoff And Cutover

目标：最后再做 3.0 的 flow-scoped handoff 责任链与入口切换，不把它们提前混进基础实现里。

## 必读输入

- `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- `docs/standards/v2/handoff-governance-standard.md`
- `docs/standards/git-workflow-standard.md`
- `docs/v3/03-pr-domain.md`

## 当前上下文

这一轮不是“再造一个本地数据库”，而是在 `v3` 主链已经稳定后，补一个更稳的本地责任链层，并决定默认入口何时切换。

这里最容易走样的地方有两个：

- handoff 一不小心重新长成第二套 shared-state
- 还没验证清楚就把 `bin/vibe` 直接切到 `vibe3`

这一轮只做这些事：

- **Markdown 自动刷新**：根据 SQLite/JSON 数据自动更新 GitHub Signpost/Memo 中的固定区块
- **本地 Handoff 索引同步**：确保本地 `.agent/handoff/` 索引与 Signpost 同步
- 验证 `vibe` / `vibe2` / `vibe3` 的切换策略

## 真源与边界

- handoff 责任链仍不是共享真源
- 真源仍然是：
  - shell 输出
  - git / branch / PR 现场
  - GitHub issue / PR / Project
- handoff 只做 flow 级责任链和必要备注
- 命令自动刷新固定区块或最小索引
- planner / executor / reviewer 只维护各自阶段交接物
- 入口切换要以验证证据为前提，不允许“感觉差不多了就切”

## 固定区块建议锁定

固定区块至少应包括：

- flow
- branch
- task issue
- repo issues
- spec ref
- plan ref
- report ref
- audit ref
- planner
- executor
- reviewer
- pr
- state
- next
- freeze / blocked by

自由区块至少应包括：

- blockers
- reminders
- follow-ups
- temporary notes

## 建议交付物

- flow-scoped handoff 自动渲染模板
- `vibe handoff refresh` (可选) 或命令执行后自动触发刷新
- note item 增删规则在 Signpost 中的体现
- `bin/vibe` / `bin/vibe2` / `bin/vibe3` 的切换与回退说明
- `tests3/handoff/`

## 验证证据 (历史记录，当前已失效)

以下证据来自上一轮失败执行，在战场清理后不再视为当前有效证据：

```text
 ✓ handoff memo created on first flow bind
 ✓ handoff memo fixed block updated on state change
```

功能点验证（历史记录，仅供复盘，不代表当前状态）：
- `vibe3` 任意 `flow/task/pr` 命令执行后，会自动刷新当前 flow 的 handoff 责任链。
- 自由备注区在刷新时得到保留。
- 切换验证：上一轮曾把 `bin/vibe` 指向 `bin/vibe3`，该结论已被 cleanup 回滚。

## 当前状态（清理后）

- `04` 仍然是最后阶段
- 上一轮“已收口”结论已失效
- 默认入口切换已被回滚
- 下一轮执行必须重新提交：
  - flow-scoped handoff 责任链的真实实现证据
  - 默认入口切换前后的 smoke 证据
  - 明确回退路径

状态：**待二次执行**。`bin/vibe` 仍不应默认切到 `vibe3`。

## 最终收口

Vibe3 的基础设计与顺序执行文档仍然有效，但上一轮实现证据已作废。
下一轮应在干净现场上重新执行，并在完成后重新写入验证证据。

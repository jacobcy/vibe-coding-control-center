# Issue Cleanup 治理材料

## Scope

只回答一个问题：

- 当前 `uv run python src/vibe3/cli.py task status` 暴露出来的 issue / flow / worktree 现场里，哪些看起来像调试残留、陈旧现场或需要人工确认的 cleanup 候选

## What It Reads

- governance prompt 里的最小 runtime summary
- `uv run python src/vibe3/cli.py task status`
- 必要时 `uv run python src/vibe3/cli.py flow show`
- 必要时 `gh issue view <number>`
- 发布治理 issue 前，必须先检查现有 open 的 `supervisor` + `state/handoff` issue，避免重复发布

## What It Produces

- cleanup findings
- keep-as-is items
- governance issues
- short report reasons

## Hard Boundary

- 不负责创建新 flow
- 不负责决定 roadmap / priority
- 不负责修改 assignee
- 不负责写代码
- 不负责删除 branch / worktree / flow 记录
- 不直接执行治理动作
- 不直接 comment / close 治理 issue

## Execution Pattern

1. 先识别明显健康的 running issues，避免误伤
2. 必须先运行 `uv run python src/vibe3/cli.py task status`，把真实的 active flows / worktrees / issue progress 当作主要观察面
3. 如有必要，再运行 `uv run python src/vibe3/cli.py flow show` 或 `gh issue view <number>` 补充单个现场事实
4. 再识别疑似残留现场，例如：
   - 有 flow 记录但没有 worktree，且看起来不是当前活跃实现
   - issue 长期停留在过时状态，需要人工重新确认
   - 现场事实与 label 明显不一致
5. 对每个候选给出简短理由
6. 在创建治理 issue 之前，先检查现有 open 的治理 issue：
   - 如果已有 issue 覆盖同一批对象或同一类 findings，不要重复创建
   - 如果只是部分重叠，优先复用或收窄新 issue 的范围，避免一批对象出现在多条治理 issue 里
7. 把需要后续核查或执行、且尚未被治理 issue 覆盖的 findings 组织成新的治理 issue
8. 治理 issue 必须使用：
   - label: `supervisor`
   - label: `state/handoff`
   - title 前缀表达 findings 类型，例如 `cleanup: ...`
9. issue body 要写清：
   - findings
   - 建议动作
   - 原因
   - 禁止动作
   - 需要后续 `supervisor/apply.md` 核查并执行
10. 如果不是 dry-run，直接使用 `gh issue create` 创建这些治理 issue，并在最终报告里列出创建结果；如果因为查重而跳过，也要明确说明跳过原因

## Output Contract

输出至少包含：

- `Healthy`
- `Cleanup findings`
- `Governance issues`
- `Dedup check`
- `Report`
- `Why`

## Label Rule

- 默认只使用非破坏性治理标签，例如 `cleanup/candidate`
- 如果仓库没有该标签，可先建议而不是臆造更多动作
- 不要移除 `state/*`，除非上下文明显要求

## Stop Point

完成 findings 与治理 issue 创建后停止，不进入 apply、manager 或具体实现。

## Command Guidance

- dry-run 时：
  - 先执行 `uv run python src/vibe3/cli.py task status`
  - 必要时执行 `uv run python src/vibe3/cli.py flow show`
  - 先输出查重结果，再输出 findings 与 issue 预览，不直接写入
- apply 时：
  - 先执行相同观察命令确认现场
  - 先执行查重，确认不会重复发布
  - 再使用 `gh issue create` 创建治理 issue
  - 输出每条 issue 的 title、labels、创建结果或跳过原因

# Issue Cleanup 治理材料

## Scope

只回答一个问题：

- 当前 `uv run python src/vibe3/cli.py task status` 暴露出来的 issue / flow / worktree 现场里，哪些看起来像调试残留、陈旧现场或需要人工确认的 cleanup 候选

## Core Model

- `dev/issue-*` 是用户主线开发分支；需要较强业务判断、架构判断、正式实现推进的工作，应回到这条主线
- `task/issue-*` 是自动化执行链；默认只承接边界清晰、可被 manager/plan/run/review 链稳定消费的任务
- 自动化链发现的 findings，如果已经超出“继续自动推进”的边界，应转为：
  - 关闭旧 issue
  - 基于 findings 重建干净 issue
  - 或创建新的 task issue 承接
- 不要为了保留历史上下文，强行让已污染的 `task/issue-*` 现场继续承担新的语义

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
- polluted-scene candidates
- close/recreate recommendations

## Hard Boundary

- 不负责创建新 flow
- 不负责决定 roadmap / priority
- 不负责修改 assignee
- 不负责写代码
- 不负责删除 branch / worktree / flow 记录
- 不直接执行治理动作
- 不直接 comment / close 治理 issue
- 不把“当前 issue 还有历史内容”自动当作必须保留的理由

## Execution Pattern

1. 先识别明显健康的 running issues，避免误伤
2. 必须先运行 `uv run python src/vibe3/cli.py task status`，把真实的 active flows / worktrees / issue progress 当作主要观察面
3. 如有必要，再运行 `uv run python src/vibe3/cli.py flow show` 或 `gh issue view <number>` 补充单个现场事实
4. 再识别疑似残留现场，例如：
   - 有 flow 记录但没有 worktree，且看起来不是当前活跃实现
   - issue 长期停留在过时状态，需要人工重新确认
   - 现场事实与 label 明显不一致
   - `task/issue-*` 绑定了旧 bootstrap PR、陈旧 merged PR、错误 issue 语义，继续推进只会制造噪音
   - 当前 issue 的真正后续工作已经明显变成新的业务目标，旧 issue 已不适合作为真源
5. 对每个候选给出简短理由
6. 对每个 polluted scene 额外判断最小治理策略：
   - 继续保留并修正 metadata
   - 关闭旧 issue 并重建干净 issue
   - 创建新的 task issue 承接 finding
7. 在创建治理 issue 之前，先检查现有 open 的治理 issue：
   - 如果已有 issue 覆盖同一批对象或同一类 findings，不要重复创建
   - 如果只是部分重叠，优先复用或收窄新 issue 的范围，避免一批对象出现在多条治理 issue 里
8. 把需要后续核查或执行、且尚未被治理 issue 覆盖的 findings 组织成新的治理 issue
9. 当判断为“旧 issue 已污染，不值得继续维护”时，应明确把建议动作写成：
   - close old issue
   - create clean replacement issue
   - explain why not to reuse the current scene
10. 治理 issue 必须使用：
   - label: `supervisor`
   - label: `state/handoff`
   - title 前缀表达 findings 类型，例如 `cleanup: ...`
11. issue body 要写清：
   - findings
   - 建议动作
   - 原因
   - 禁止动作
   - 需要后续 `supervisor/apply.md` 核查并执行
12. 如果不是 dry-run，直接使用 `gh issue create` 创建这些治理 issue，并在最终报告里列出创建结果；如果因为查重而跳过，也要明确说明跳过原因

## Output Contract

输出至少包含：

- `Healthy`
- `Cleanup findings`
- `Polluted scenes`
- `Governance issues`
- `Dedup check`
- `Report`
- `Why`


## Polluted Scene Rule

- 如果 `task/issue-*` 现场已经被旧 PR、旧 flow、错误 state、错误 issue 语义污染，且继续修补只会增加误判成本，优先建议关闭并重建，而不是继续在原 issue 上打补丁
- `PR merged but task issue not closed` 本身不自动等于 bug；先判断该 PR 是否本来就不是 closing PR、是否只是 bootstrap PR、是否导致当前 flow 真源被污染
- 只要“重建一个干净 issue”比“继续维护旧 issue 语义”更简单、更清晰，就优先建议重建

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

## Cleanup Action Rule

**确定性判断**：
- 如果通过现场核查（flow state、worktree 状态、git 历史、issue 内容）可以明确判断为陈旧/污染现场
- **直接关闭 issue**，不需要任何标签或中间步骤

**不确定性判断**：
- 如果需要人工复核或现场证据不足
- **在 issue 中添加 governance suggest comment**，建议人类关闭或进一步核查
- Comment 格式：`[governance suggest] 建议 close 或进一步核查，理由：...`

**禁止行为**：
- ❌ 不使用 `cleanup/candidate` 或任何其他 cleanup 相关标签
- ❌ 不创建治理 issue 来处理可以直接关闭的陈旧 issue
- ❌ 不保留明显污染的现场继续承担新语义

**原则**：
- 确定性优先：宁可直接关闭，也不要通过标签或治理 issue 延长不确定状态
- 证据为王：基于现场事实（flow state、worktree、git）而非猜测
- 简单直接：能用关闭解决的不创建治理 issue，能用建议解决的不等待确认

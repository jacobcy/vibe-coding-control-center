# 当前任务记录

更新时间：2026-03-13

====
关于handoff , 修改时不得删除重写，只修改必要部分，防止重要信息被删除，无法传递后续开发注意
vibe-new 增加 handoff，允许把 handoff 内容提炼做成 task，然后才可以清理 handoff 记录的开发注意

## Follow-up Issues

- **#119**: `vibe task update --bind-current` / `vibe flow pr` 未持久化 `runtime_branch` 与 `pr_ref`
- **#121**: `audit(code-quality)`: 复用实现、低质量代码与重复测试专项清扫
- **#122**: `perf(roadmap-sync)`: precompute mirrored issue refs during issue intake

## Completed (2026-03-11)

- **PR #114** (runtime-boundary-cleanup): 已 merge，分支已清理
- **PR #118** (issue-project-auto-sync): 已 merge
  - 实现了带 `vibe-task` 标签的 open issues 自动纳入 `vibe roadmap sync` intake 路径
  - 发布了版本 2.1.18
  - 已处理 Copilot review comments
  - `issue_refs=[]` 已确认不是 bug（task 当前没有绑定 repo issue）

## Skill Handoff
- skill: vibe-save
- updated_at: 2026-03-13T00:02:00+08:00
- flow: gh-100-roadmap-dependency-view
- branch: task/gh-100-roadmap-dependency-view
- task: 2026-03-11-gh-100-roadmap-dependency-view
- pr: #146
- issues: gh-100
- completed: 文档口径已收敛：dependency draft 已从 `docs/standards/roadmap-dependency-standard.md` 挪到 `docs/references/roadmap-dependency.md`；代码口径已收敛：`lib/roadmap_dependency.sh` 拆出依赖计算，`lib/roadmap_query.sh` 降到 300 行阈值内并改为真实 merged PR 证据；Serena review gate 已重写为隔离 `SERENA_HOME` 的本地执行链路，新增 `scripts/serena_gate.py`，`bash scripts/serena_gate.sh --file lib/roadmap_query.sh` 验证通过且不污染全局 `~/.serena/serena_config.yml`；已将 PR #146 的 Serena local review evidence 回贴到 `issuecomment-4047908452`；已对全仓 54 个 shell 文件做 Serena 全量扫描，并把低质量代码清理线索回贴到 issue #121：`issuecomment-4047937709`
- next: 下个 session 进入 vibe-integrate，围绕 PR #146 继续做 review/merge readiness 判断；优先检查线上 review evidence、CI、以及本次代码审查里剩余的语义阻断项；若转入 #121 清理，只把 Serena 全量扫描结果当参考，不直接据此删代码
- notes: 本机全局 Serena 已关闭 `web_dashboard` / `web_dashboard_open_on_launch`，旧的 Serena 调试进程已清理；当前 `.agent/reports/serena-impact.json` 是全量扫描产物，不是 PR 精确扫描产物

## Skill Handoff
- skill: vibe-commit
- updated_at: 2026-03-13T01:09:51+08:00
- flow: gh-100-roadmap-dependency-view
- branch: task/gh-100-roadmap-dependency-view
- task: 2026-03-11-gh-100-roadmap-dependency-view
- pr: #146
- issues: gh-100
- completed: 已按当前 dirty worktree 做 PR #146 归类。当前 PR 核心应保留 roadmap dependency view 的本地查询层与配套文档：`docs/plans/2026-03-12-gh-100-roadmap-dependency-final-plan.md`、`docs/standards/data-model-standard.md`、`docs/standards/roadmap-json-standard.md`、删除 `docs/standards/roadmap-dependency-standard.md`、新增 `docs/references/roadmap-dependency.md`、`lib/roadmap_dependency.sh`、`lib/roadmap_query.sh`、`tests/helpers/roadmap_common.bash`、`tests/roadmap/test_roadmap_query.bats`。其中还包含真实修复：多 task merged PR 判定、缺失 dependency item 显式报错、`gh` 不可用区分 `merge_status_unavailable`、以及 `show/list --json` 的 zsh 非法 JSON 输出 bug。
- next: 若继续收口 PR #146，先把本轮新增的远程 dependency 接口从当前 flow 中拆出来或暂不纳入：`lib/roadmap_issue_dependency.sh`、`tests/roadmap/test_roadmap_remote_dependency.bats`，以及 `lib/roadmap.sh` / `lib/roadmap_help.sh` 里的 `dep` 入口属于后续 issue #148 范围；`.agent/reports/serena-impact.json` 不应进入 PR，`scripts/serena_gate.sh` / `scripts/serena_gate.py` / `.serena/project.yml` 是否随本 PR 发布需单独决策，但从功能边界看更适合作为独立 follow-up。
- notes: 当前真实 blocker 已不再是本地 dependency 判定正确性，而是交付切片仍混有后续探索代码；另有 `vibe roadmap status --json` 在真实仓库超时的问题，尚未作为本 PR 内修复完成。

## Skill Handoff
- skill: vibe-commit
- updated_at: 2026-03-13T01:20:24+08:00
- flow: serena-gate-isolated-runtime
- branch: task/serena-gate-isolated-runtime
- task: none
- pr: #150
- issues: none
- completed: 已按串行拆 PR 完成 3 组提交与发布。A 组 `fix(roadmap): stabilize dependency query view` 已推到现有 PR #146；B 组 `feat(roadmap): add remote issue dependency commands` 先在临时分支生成 commit，再在新 flow `gh-148-remote-issue-dependency` 上 cherry-pick、rebase 到 `task/gh-100-roadmap-dependency-view` 并发布 PR #149；C 组 `chore(workflow): isolate serena gate and codify serial split flow` 在新 flow `serena-gate-isolated-runtime` 上 cherry-pick、rebase 到 `task/gh-148-remote-issue-dependency` 并发布 PR #150。`skills/vibe-commit/SKILL.md` 已补充“临时分支产出 commit -> 新 flow cherry-pick -> 串行 PR”的默认流程。
- next: 进入 vibe-integrate / review 阶段时，应按链路顺序检查 PR #146 -> PR #149 -> PR #150；其中 PR #149 依赖 PR #146，PR #150 依赖 PR #149。另需注意 shell 真源当前仍未把新 flow 的 `pr_ref` 持久化回 `vibe flow show --json`，这与已知问题 #119 一致。
- notes: 当前工作树仅剩 `.agent/reports/serena-impact.json` 本地产物未提交；它是 Serena gate 运行结果，不属于本轮 PR 受管文件。

## Skill Handoff
- skill: vibe-save
- updated_at: 2026-03-13T07:40:00+08:00
- flow: gh-100-roadmap-dependency-view
- branch: task/gh-100-roadmap-dependency-view
- task: 2026-03-11-gh-100-roadmap-dependency-view
- pr: #146 / #149 / #150
- issues: gh-100 / gh-148 / #152
- completed: 已澄清 stacked PR / merge 语义。当前真实链路是 `#146: main <- task/gh-100-roadmap-dependency-view`，`#149: task/gh-100-roadmap-dependency-view <- task/gh-148-remote-issue-dependency`，`#150: task/gh-148-remote-issue-dependency <- task/serena-gate-isolated-runtime`；且 #150 已 merged 到 `task/gh-148-remote-issue-dependency`，因此 #149 当前实际已包含 #150 的提交（含 merge commit `597a3bd`）。已确认：merge #146 不会让 #149/#150 “断掉”；正确主线收口顺序仍是先 merge #146，再 merge #149。merge #149 时，进入 `main` 的会是“相对已进 main 的 #146 额外新增部分”，因此会把 #149 与已并入其中的 #150 一起带进 `main`。同时已创建 bug issue #152 并补充评论：`vibe flow show` 在 `flow done` 后手动切到未登记分支时诊断不足，且暴露出 `worktrees.json` / `registry.json` / Git branch 三套 runtime 事实可漂移的问题；后续修 bug 时应一并考虑让 worktree 退出共享状态主模型，只保留 `registry.json` 中 `task <-> branch <-> issue/roadmap/PR` 关系。
- next: 下个 session 专注处理 merge / integrate。先看 PR #146 是否已满足 merge 条件；若可 merge，先 merge #146 到 `main`。随后回到 PR #149，按“#149 已包含 #150”心智做 review / CI / merge 判断，不要再把 #150 当成独立待入 `main` 的 PR。若在 #146 merge 之后还要继续往 `task/gh-100-roadmap-dependency-view` 加新提交，必须明确：原 PR #146 这根 `gh-100 -> main` 管子已结束，新提交不会自动进 `main`，需要新的 PR 承接。
- notes: 当前本地 flow/runtime 现场已偏离干净状态：Git 当前/共享状态/已记录 handoff 之间不再完全一致；下次进入时不要先信 `vibe flow show` 的默认结果，应先直接核对 `gh pr view 146/149/150`、`git branch --show-current`、以及必要时的 `git log --graph`。如果只是为了把既有 stacked PR 链收口进 `main`，优先以 PR base/head 关系和 commit 图为准，不要再继续做“往下层分支里合 PR”式操作。

## Skill Handoff
- skill: vibe-integrate
- updated_at: 2026-03-13T08:45:00+08:00
- flow: gh-100-roadmap-dependency-view
- branch: task/gh-100-roadmap-dependency-view
- task: 2026-03-11-gh-100-roadmap-dependency-view
- pr: #146
- issues: gh-100
- completed: 已核对 PR #146 的 review evidence / CI / review threads；发现 Copilot 5 条未解决线程后，补提交 `52de1d8 fix(roadmap): address dependency review follow-ups` 并推到远端。修复内容包含 `lib/roadmap_dependency.sh` 的 JSON 输出与 merged PR 获取失败语义、`lib/roadmap_store.sh` 默认补 `depends_on_item_ids: []`、新增对应 Bats 回归测试、以及 CHANGELOG scope 对齐。已本地验证 `bats tests/roadmap/test_roadmap_write_audit.bats tests/roadmap/test_roadmap_query.bats` 通过，`bash scripts/lint.sh` 通过（仅剩仓库既有 ShellCheck warnings）。
- next: 继续停留在 vibe-integrate。等待 PR #146 新一轮 CI 完成，然后复核线上 review threads；性能优化那条评论更适合作为 follow-up，不应在本轮 gate 内扩 scope。只有在 CI 通过且阻塞性 review 线程处理完后，才进入 merge 判断。
- notes: 当前 PR #146 远端 head 已更新为 `52de1d8dda51b48fd9633eb605549a37d0e67174`；截至 handoff 写入时 GitHub Actions `Lint & Test` 仍为 `QUEUED`。

## Skill Handoff
- skill: vibe-integrate
- updated_at: 2026-03-13T08:50:00+08:00
- flow: gh-100-roadmap-dependency-view
- branch: task/gh-100-roadmap-dependency-view
- task: 2026-03-11-gh-100-roadmap-dependency-view
- pr: #146 merged
- issues: gh-100
- completed: 已复核 PR #146 线上状态：CI `Lint & Test` 成功、Copilot/local review evidence 存在、6 条 review threads 已在线回复并 resolve；随后执行 merge（保留分支，不删 remote branch）。GitHub 现场已确认 `#146` 于 `2026-03-13T00:49:15Z` merge 到 `main`，merge commit 为 `a72b684a58481294062d694de0fdb4373c10cf04`。
- next: 转入下一个整合目标 PR #149。先核对 `#149` 当前 base/head 是否仍是 `task/gh-100-roadmap-dependency-view <- task/gh-148-remote-issue-dependency`，然后按“#149 已包含 #150”心智做 retarget / review / CI / merge readiness 判断；不要把 #150 当成独立待入 `main` 的 PR。
- notes: 由于本轮 merge 时没有删除 `task/gh-100-roadmap-dependency-view` 远端分支，`#149` 当前 stacked base 关系应仍可被 GitHub 正常识别；但继续操作前仍应先以 `gh pr view 149` 为准，不要先信本地 runtime 展示。

## Skill Handoff
- skill: vibe-integrate
- updated_at: 2026-03-13T09:05:00+08:00
- flow: gh-148-remote-issue-dependency
- branch: task/gh-148-remote-issue-dependency
- task: none
- pr: #149 open
- issues: gh-148 / #152 / #153
- completed: 已把本地 `task/gh-148-remote-issue-dependency` 切到当前 worktree，并先后 merge `origin/main` 与 `origin/task/gh-148-remote-issue-dependency`，消除 `#146` follow-up commit 带来的反向 diff，同时保留 `#150` 已吸收进 `#149` 的真实链路；已推送远端分支，并把 PR #149 retarget 到 `main`。当前相对 `main` 的增量范围为 remote dependency + serena gate 相关文件，不再引用 `task/gh-100-roadmap-dependency-view` 作为 base。已本地验证 `bats tests/roadmap/test_roadmap_remote_dependency.bats` 通过、`bash scripts/lint.sh` 通过（仅剩仓库既有 ShellCheck warnings）。
- next: 当前不能继续进入 `vibe-done 149` 或 `vibe-done 146`。PR #149 仍为 `OPEN`，直接 `gh pr merge 149 --merge` 被 GitHub 返回 “base branch policy prohibits the merge”；尝试 `--auto` 也失败，因为仓库未启用 pull request auto merge。后续需在 GitHub 侧补齐 branch policy 所需条件（至少 review / checks / 其他仓库规则），再回到 `vibe-integrate` 继续 merge；只有 #149 真正 merged 后，才进入 `vibe-done 149`，随后再评估 `vibe-done 146`。
- notes: 用户已明确这轮不再等待 GitHub 超限恢复，因此本轮没有继续轮询线上 CI / review。虽然 `#149` 已 retarget 到 `main`，但目前没有可用的线上 merge 证据，且仓库不支持 auto-merge，故阻塞属于外部 GitHub policy / API 条件，不是本地代码状态问题。

## Skill Handoff
- skill: vibe-integrate
- updated_at: 2026-03-13T09:25:00+08:00
- flow: gh-148-remote-issue-dependency
- branch: task/gh-148-remote-issue-dependency
- task: none
- pr: #149 open
- issues: gh-148 / #152 / #153 / #154 / #155
- completed: 已按本地 review findings 修复 `#149` 的两个 Serena gate P1：`.serena/project.yml` 恢复为 `languages: [bash]` schema；`scripts/serena_gate.sh` 增加冷启动自举逻辑，在缓存缺失时主动执行 `uvx --from \"$SERENA_SOURCE\" serena --help` 后重新解析 archive。新增回归测试 `tests/test_serena_gate.bats`，并验证 `bats tests/test_serena_gate.bats tests/roadmap/test_roadmap_remote_dependency.bats` 通过、`bash scripts/lint.sh` 通过。修复已提交并推送到 `task/gh-148-remote-issue-dependency`，远端 head 现为 `064e5516976bfa1a699744d7bb3c4e9eee2c0156`。
- next: `#149` 代码侧 blocker 已解除，但 merge 仍被 GitHub base branch policy 阻止。当前直接 `gh pr merge 149 --merge` 仍返回 policy block，因此不能进入 `vibe-done 149`，更不能先 `vibe-done 146`。后续需要在 GitHub 侧补齐仓库要求的 merge 前置条件后，再回到 `vibe-integrate` 完成 #149 merge / #149 done / #146 done。
- notes: 这轮已把用户提供的本地 review findings 视为正式 review evidence 来处理；后续通过 #154 再补“local reviewer 自动回贴 PR comment”的闭环，不在本次修复里扩 scope。

## Skill Handoff
- skill: vibe-integrate
- updated_at: 2026-03-13T09:35:22+08:00
- flow: gh-148-remote-issue-dependency
- branch: task/gh-148-remote-issue-dependency
- task: none
- pr: #149 open
- issues: gh-148 / #152 / #153 / #154 / #155
- completed: 已定位并修复 `#149` 的最新 CI blocker：GitHub Actions `Lint & Test` 因 shell 总 LOC `6181 > 6000` 失败。本轮只对 `lib/roadmap_issue_dependency.sh`、`lib/roadmap.sh`、`lib/roadmap_help.sh` 做等价压缩与帮助文案收缩，不改对外命令语义。已本地验证 `bash scripts/lint.sh` 通过、`bats tests/roadmap/test_roadmap_remote_dependency.bats tests/test_serena_gate.bats` 通过，且 `find lib/ bin/ -name '*.sh' -o -name 'vibe' | xargs cat | wc -l` 结果为 `5995`，已回到 CI 阈值内。
- next: 继续停留在 `vibe-integrate`。下一步应提交并推送这 3 个 shell 文件改动，触发 `#149` 远端 CI 重跑；随后复核线上 checks / review / merge policy 是否都满足，再决定能否 merge。若远端仍有额外 gate 阻塞，再按线上真源继续处理，不要提前进入 `vibe-done`。
- notes: 当前 worktree dirty 仅包含上述 3 个 shell 文件；这轮没有改测试、共享状态 JSON 或 PR 元数据，属于纯 follow-up 压缩修复。

## Skill Handoff
- skill: vibe-integrate
- updated_at: 2026-03-13T09:54:31+08:00
- flow: gh-148-remote-issue-dependency
- branch: task/gh-148-remote-issue-dependency
- task: none
- pr: #149 merged
- issues: gh-148 / #152 / #153 / #154 / #155
- completed: 已完成 `#149` 的整合收口。先以提交 `175e1dd` 修复 shell LOC 超限 CI，再以提交 `a5d34ba` 处理 Codex review 的两条 P2 follow-up：允许 `owner == repo` 的合法仓库，以及 `serena_gate.py` 使用仓库根目录初始化 `SerenaAgent`。对应回归测试已补到 `tests/roadmap/test_roadmap_remote_dependency.bats` 与 `tests/test_serena_gate.bats`。本地验证 `bash scripts/lint.sh`、`bats tests/roadmap/test_roadmap_remote_dependency.bats tests/test_serena_gate.bats` 通过，线上 `Lint & Test` 成功，两个 review thread 已 resolve。GitHub 已确认 `#149` 于 `2026-03-13T01:53:59Z` merge 到 `main`，merge commit 为 `7fc77651558d04c47058924d82fc924d7a239f53`。
- next: 当前 PR 整合阶段对 `#149` 已完成，下一步应转入 `vibe-done` 处理对应 flow / issue / handoff 收口；不要继续在已 merged 的 `#149` 上追加新需求。若要继续处理 runtime 漂移与 PR 流程问题，按既有 issue `#152/#153/#154/#155` 另起后续 flow。
- notes: 本地 worktree 在写入本条 handoff 前是干净的；`gh pr status` 另显示有外部 PR `#156 [WIP] Add remote issue dependency commands [codex/sub-pr-149]` 请求 review，但它不属于当前 `#149` 收口链路，当前 handoff 未将其纳入。

## Skill Handoff
- skill: vibe-done
- updated_at: 2026-03-13T10:23:00+08:00
- flow: gh-148-remote-issue-dependency
- branch: none
- task: none
- pr: #149 merged
- issues: gh-148 closed
- completed: 已完成 `gh-148-remote-issue-dependency` 的最终收口。真源确认 `#149` 已于 `2026-03-13T01:53:59Z` merge；随后执行 `vibe flow done --branch task/gh-148-remote-issue-dependency`，shell 已删除本地/远端分支并写入 closed history。当前 `vibe flow list` 显示该 flow 为 `[closed]`，closed_at 为 `2026-03-13T10:22:10+08:00`。同时已执行 `gh issue close 148 --comment 'Closed via PR #149, merged on 2026-03-13.'`，GitHub 真源确认 issue `#148` 于 `2026-03-13T02:22:36Z` 关闭。当前 worktree 已切回安全分支 `vibe/main-safe/wt-fix-pr-base-selection`。
- next: none
- notes: 本轮 `vibe-done` 没有关联 task 可关闭；`gh pr status` 中另见外部 PR `#156 [WIP] Add remote issue dependency commands [codex/sub-pr-149]` 请求 review，但它不属于本次 `#149/#148` 收口链路。若继续处理 runtime 漂移与流程补洞，请围绕 `#152/#153/#154/#155` 新开后续 flow。

## Skill Handoff
- skill: vibe-issue / flow-new
- updated_at: 2026-03-13T10:30:35+08:00
- flow: gh-157-closeout-governance-debt
- branch: task/gh-157-closeout-governance-debt
- task: none
- pr: none
- issues: gh-157 open
- completed: 已创建治理母 issue `#157 governance(closeout): converge flow/runtime/handoff cleanup debt`，并在正文中串联当前 closeout/runtime 治理范围：`#119 #121 #152 #153 #154 #155`，同时把“`vibe-done` 需要清理 handoff 中已完成/过时信息”写入 scope。随后已执行 `vibe flow new gh-157-closeout-governance-debt --branch origin/main`，当前 worktree 已切到 `task/gh-157-closeout-governance-debt`。另外，`vibe roadmap sync` 已实际执行一次，最新 roadmap mirror 中已可见 `gh-157`，当前状态为 `deferred`。
- next: 若继续正式进入执行链，先为 `#157` 产出 plan/spec，再创建并绑定 task；当前 shell 会拒绝“无 plan 直接 `vibe task add`”。在已有 plan/spec 之前，不要伪造 task 绑定。
- notes: 本轮尝试 `vibe task add "GH-157 Closeout governance debt convergence" --id 2026-03-13-gh-157-closeout-governance-debt --issue gh-157` 被 shell 明确阻断，错误为“Task creation requires a plan binding.”；因此当前现场只有 issue + flow，没有 task。另一个用户意图“以后 `vibe-done` 清理已完成 handoff 信息”已写入 `#157` scope，尚未实现。

## Skill Handoff
- skill: brainstorming / writing-plans
- updated_at: 2026-03-13T11:04:54+08:00
- flow: gh-157-closeout-governance-debt
- branch: task/gh-157-closeout-governance-debt
- task: none
- pr: none
- issues: gh-157 open / gh-158 open
- completed: 已围绕“GitHub 真源优先、本地 roadmap 只做 projection/cache/backup”完成本 flow 的总设计与实施路线图梳理。新增 issue `#158 design(data-model): let task bind repo issue directly and support local-first roadmap drafts` 作为总设计锚点，并提交两份规划文档：`docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-design.md` 与 `docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-plan.md`。文档已随提交 `a08e4b3 docs(plan): map remote-first roadmap governance` 落到当前分支。
- next: 按规划图依次推进，不要并发重做所有治理 issue。推荐顺序是：先冻结标准语义（以 `#158` 为主），再解除 task 对 roadmap mirror 的硬依赖，然后重构 `vibe roadmap sync` 为 remote-first projection，最后统一 PR/issue/closeout contract，并把 `#122/#119/#152/#153/#154/#155` 作为后置实施或并行 follow-up。
- notes: 本轮已明确一个推论：GitHub 官方支持 issue dependency、sub-issues、Project hierarchy fields、PR linked issue auto-close，因此这些关系语义应直接跟随 GitHub；但“父 issue 在所有子 issue 完成后自动关闭”未被当作当前核心契约，需要留作后续 automation / policy 议题，而不是先写入数据模型。

## Skill Handoff
- skill: vibe-commit
- updated_at: 2026-03-13T13:19:00+08:00
- flow: gh-152-worktrees-json-retirement
- branch: task/gh-152-worktrees-json-retirement
- task: 2026-03-13-gh-152-worktrees-json-retirement
- pr: #159 open / runtime PR blocked
- issues: gh-158 / gh-152 / gh-157
- completed: 已按“不可在 `task/gh-157-closeout-governance-debt` 直接提交”的约束，把当前 dirty 现场先切到临时分支 `codex/tmp-gh-157-pr-split`，并拆成两个可迁移 commit：`84acfdf docs(semantics): freeze branch-first runtime vocabulary` 与 `468699b refactor(runtime): retire worktrees state from flow paths`。随后新建并绑定两个独立 flow/task：`gh-158-semantic-cleanup` -> `2026-03-13-gh-158-semantic-cleanup`（spec=`docs/plans/2026-03-13-gh-157-semantic-cleanup-expansion-plan.md`），以及 `gh-152-worktrees-json-retirement` -> `2026-03-13-gh-152-worktrees-json-retirement`（spec=`docs/plans/2026-03-13-gh-157-worktrees-json-retirement-implementation-plan.md`）。语义 flow 因依赖 `a08e4b3` 中已创建的总设计 plan，实际迁移时一并 cherry-pick 了 `a08e4b3` 和 `84acfdf`；runtime flow 迁移了 `468699b`。语义分支已通过 plan/skill/workflow 语义审计型 `rg` 验证，并已执行 `vibe flow pr --base main` 发出 PR `#159`：<https://github.com/jacobcy/vibe-coding-control-center/pull/159>。runtime 分支已本地验证 `bats tests/flow/test_flow_help_runtime.bats tests/task/test_task_count_by_branch.bats tests/contracts/test_flow_contract.bats tests/test_vibe.bats tests/flow/test_flow_pr_review.bats tests/task/test_task_ops.bats tests/flow/test_flow_lifecycle.bats tests/flow/test_flow_bind_done.bats` 通过，且 `bash scripts/lint.sh` 通过（仅剩仓库既有 warnings，0 errors）。
- next: 语义 flow 进入 `vibe-integrate`，检查 `#159` 的 review evidence / CI / merge readiness。runtime flow 当前被 shell 的串行发布墙阻塞：`main` 已存在 open PR `#159`，因此不能再对 `main` 发第二个独立 PR。后续二选一：1）等待 `#159` merge 后，再对 `task/gh-152-worktrees-json-retirement` 执行 `vibe flow pr --base main`；2）若接受 stacked，则改为对 `task/gh-158-semantic-cleanup` 发 runtime PR。
- notes: `vibe flow pr` 仍会自动 bump version / 更新 `CHANGELOG.md`；因此若后续坚持两条独立到 `main` 的 PR，第二条在第一条 merge 后大概率还需要 rebase 或 follow-up 处理版本文件冲突。另一个已知事实是：虽然 `#159` 已创建成功，但 shell 目前没有自动把 `pr_ref` 回写到 flow dashboard；task 侧已手动补写 `pr_ref=159`，这与既有 runtime 元数据漂移问题同类。

## Skill Handoff
- skill: vibe-issue / vibe-commit
- updated_at: 2026-03-13T13:27:30+08:00
- flow: gh-152-worktrees-json-retirement
- branch: task/gh-152-worktrees-json-retirement
- task: 2026-03-13-gh-152-worktrees-json-retirement
- pr: #161 open
- issues: gh-152 / gh-157 / gh-160
- completed: 已确认 PR `#159` 于 GitHub 真源中处于 `MERGED` 状态，因此串行发布墙解除。随后按用户要求先补治理 issue `#160 feat(vibe-commit): support text-only fast submit and dependency-aware PR batching`，用于承接“纯文本快速提交不要求 review 验证”与“无依赖 PR 并行、存在依赖 PR 串行”的 `vibe-commit` 后续变更；本轮未把该独立 skill 治理改动混入当前 runtime PR。runtime 分支已先 `git fetch origin && git rebase origin/main` 对齐最新主干，再执行 `vibe flow pr --base main` 成功发布 PR `#161 refactor(runtime): retire worktrees state from flow paths`：<https://github.com/jacobcy/vibe-coding-control-center/pull/161>。发布过程中 shell 自动追加 bump commit `8b175eb chore: bump version to 2.1.32` 并携带受管 artifact：`docs/plans/2026-03-13-gh-157-worktrees-json-retirement-implementation-plan.md`、`VERSION`、`CHANGELOG.md`。随后已手动在 PR #161 发布 GitHub 评论 `issuecomment-4052844617`，内容为 `@codex` 在线 review 请求，说明当前 Copilot quota 不可用，并请其聚焦 runtime semantics、`worktrees.json` 清退边界与 flow/task query 回归风险。
- next: 停在当前状态，等待 PR `#161` 上的 `@codex` 在线评论与后续 review evidence；当前不要继续做 merge、done、额外 follow-up 提交，也不要现在实现 `#160`。
- notes: `#160` 只是后续治理 intake，本轮尚未修改 `skills/vibe-commit/SKILL.md`。若后续真的实现 `#160`，应新开独立 flow/PR，不要回头混到 `#161` 这个 runtime 实现 PR 中。

## Skill Handoff
- skill: vibe-new
- updated_at: 2026-03-13T14:05:00+08:00
- target: gh-121
- plan: docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md
- task: none
- flow: none
- next: /vibe-start。执行 `#121` 时严格按 `docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md` 推进，并保持 `lib/task_query.sh` 与 `gh-152 / PR #161` 代码面排除在外。
- notes: 真源核对结果：`vibe flow show --json` 仍显示当前 worktree 绑定 `gh-152` / task `2026-03-13-gh-152-worktrees-json-retirement` / PR `#161`；`gh pr view 161 --json` 显示 `mergeStateStatus=BLOCKED` 且 CI `Lint & Test` 失败；`gh issue view 121 --json` 显示 issue open 且带 `vibe-task` 标签。仓库内尚未发现 `#121` 对应 plan/spec，因此本次只完成 intake 判断，不进入执行。另已将 `task_query.sh` 的边界建议回贴到 PR `#161`：`issuecomment-4052919850`。GH-121 excludes `lib/task_query.sh` and any PR #161-only cleanup.

## Skill Handoff
- skill: executing-plans
- updated_at: 2026-03-13T15:25:00+08:00
- target: gh-121
- plan: docs/plans/2026-03-13-gh-121-code-quality-cleanup-plan.md
- task: none
- flow: none
- completed: 已完成 `#121` 第一轮 code-quality cleanup，并保持 `lib/task_query.sh` / `gh-152 / PR #161-only cleanup` 排除不动。已删除确认零调用点 helper：`lib/roadmap_store.sh` 的 `_vibe_roadmap_has_version_goal`、`_vibe_roadmap_get_current_issues`，`lib/flow.sh` 的 `_flow_shared_dir`，`lib/check_pr_status.sh` 的 `_check_pr_merged_status`。同时对非 `gh-152` 范围测试做最小收敛：合并重复的 `flow help` / `roadmap status` 文案断言，删除重复的 `version set-goal` 输出断言。已将结果摘要回贴到 issue `#121`（`issuecomment-4053030567`）与 PR `#161`（`issuecomment-4053031272`）。
- next: 若要继续处理唯一剩余失败项，应在 `gh-152 / PR #161` 自己决定是否收口 `tests/contracts/test_roadmap_contract.bats` 对 `vibe roadmap help` 的文案契约漂移；`#121` 本轮无需继续扩 scope。
- notes: 最终验证结果：`bash scripts/lint.sh` 通过（0 errors，仅仓库既有 warnings）；聚焦 bats 套件共 86 条中 85 条通过，唯一失败仍是 `tests/contracts/test_roadmap_contract.bats` 对 `task / flow / spec bridge fields stay local` 的帮助文案断言，该失败在本轮清理前已存在，不是本轮引入的新回归。

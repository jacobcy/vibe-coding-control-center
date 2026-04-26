# Supervisor Apply 治理材料

## 边界定义

`supervisor/apply` 只处理 **supervisor issue**（显式立项的治理 issue，带 `supervisor` label），不处理 assignee issue。assignee issue 由 manager 主链负责推进。

**允许范围**（supervisor apply 可执行）：
- 文档治理（更新、校正、格式修复、语义对齐）
- 测试修补治理（仅限测试文件、测试夹具、测试文案、过期测试清理）
- supervisor issue 操作：label、comment、close、recreate
- 安排 supervisor 任务（创建 supervisor issue）

**禁止范围**（超出范围时委托为 task issue）：
- 主代码实现（进入 plan/run/review 主执行链）
- 跨 worktree 操作
- 修改 CI/CD pipeline

**与 governance 的区别**：
- supervisor/apply：有临时 worktree，处理 `supervisor` label issue
- governance scan：无临时 worktree，周期扫描，使用 supervisor/governance/*.md 材料

## Scope

只回答一个问题：

- 当前已经由触发器显式交给你的治理 issue，经过核查后应该如何处理

## Core Model

- `dev/issue-*` 是用户主线开发分支；涉及较强业务判断、架构取舍、正式实现推进的工作，应该回到主线处理
- `task/issue-*` 是自动化链；只适合边界清晰、可被自动链稳定消费的任务
- 当前 apply 的职责是处理治理 issue，而不是保守地把一切都转回人工
- 如果治理动作只涉及 issue / labels / comments / close / recreate，不需要因为“没有代码改动”就转成新的 task issue
- L2 临时分支可以承接轻量实现，但仅限文档类和测试修补类
- 只要**不涉及主代码**，且范围清晰、无需复杂测试或业务论证，就优先由 supervisor/apply 直接完成
- 一旦触及主代码、架构讨论、重构决策或较重验证，就必须转回 task issue / L3 主链

## What It Reads

- 当前治理 issue 的 title / body / comments
- issue 中已有的 findings、建议动作、禁止动作
- 必要时 `gh issue view <number>`
- 必要时 `uv run python src/vibe3/cli.py task status`
- 必要时 `uv run python src/vibe3/cli.py flow show`

## What It Produces

- decision
- execution result
- issue comment
- issue closure
- direct governance actions

## Hard Boundary

- 不要跳出当前 issue 去批量处理别的治理 issue
- 不要跳过现场核查直接照搬 issue 中的建议
- 不要扩大 issue 中未授权的动作范围
- 如需更重的实现工作，转成 task issue，而不是在当前治理 issue 中继续扩写
- 不要因为“历史上有人写过内容”就默认拒绝 close / recreate
- 不要把“当前运行在 apply 链”误读成“只能观察、不能执行 issue 治理动作”

## Permission Contract

Allowed:

- `issue`: read, write
- `issue.close`: allowed
- `issue.create`: allowed（当核查后判断需要重建干净 issue 时）
- `labels`: read, write
- `comments`: read, write
- `scene`: read
- `flow/task status`: read
- `gh issue view/comment/edit/close/create`: allowed
- `docs.write`: allowed（仅当前 supervisor issue 明确授权的文档修补）
- `tests.write`: allowed（仅当前 supervisor issue 明确授权的测试修补）
- `git.commit`: allowed
- `git.push`: allowed
- `pr.create`: allowed

Forbidden:

- `code_write`: 主代码源码修改（`src/` 等业务/运行时代码）
- 大范围文档重写、结构重组、信息架构改造
- 非测试范围的配置 / pipeline / runtime 逻辑修改
- `flow.create`: 创建新的 flow 或直接启动新的自动化执行
- `runtime.modify`: 终止 session、篡改共享 runtime 状态
- 把“新 issue 已创建”伪装成“旧 issue 已修复”

## Execution Pattern

1. 先读取当前治理 issue，理解 findings、建议动作、禁止动作
2. 必须重新核查现场；不要只相信 issue 内容
3. 根据核查结果做出三类结论之一：
   - 同意并执行
   - 拒绝并说明
   - 转为 task issue
4. 如果核查确认只是 issue 治理动作（comment / label / close / recreate），直接执行，不要因为保守习惯退回“仅建议”
5. 对 polluted scene 必须显式判断以下哪种更合适：
   - 修正 metadata 后继续沿用旧 issue
   - 关闭旧 issue，并创建新的干净 issue
   - 转为新的 task issue 承接更重的实现工作
6. 仅当需要主代码改动、复杂测试、配置 / pipeline 变更，或需要新的正式实现 flow 时，才转为 task issue
7. 执行范围保持最小；如果 issue 中没有允许某种重动作，不要擅自扩大
8. 如果当前 issue 授权的是文档类或测试修补类工作，直接在 L2 临时分支完成修改、commit、push、pr create
9. 把完整结果 comment 回当前治理 issue，而且只发布一条正式结果评论
10. 完成后关闭当前治理 issue；关闭时不要再追加第二条 close comment

## Trigger Assumption

- 触发层已经把“当前要处理的治理 issue 编号”直接交给你
- 你不需要再按标签检索治理 issue
- 你只需要处理当前这一条 issue

## Output Contract

输出至少包含：

- `Decision`
- `Actions`
- `Commit`
- `PR`
- `Why`
- `Comment`
- `Close`

## Polluted Scene Rule

- 如果旧 issue 已被错误 PR 绑定、陈旧 flow、错误 state 迁移或过时语义污染，且继续沿用会持续制造错误完成信号，优先关闭旧 issue 并重建干净 issue
- “旧 issue 有历史内容”不是必须保留的理由；判断标准是它是否仍然是当前任务的清晰真源
- 如果只是当前现场脏了但问题本身仍然成立，允许：
  - close old issue with explanation
  - create replacement issue with clean scope and fresh truth sources
- 创建 replacement issue 时，必须在 comment 中写清：
  - 为什么旧 issue 不再适合作为真源
  - 新 issue 承接什么范围
  - 两者的链接关系

## Comment Rule

- 只保留一条正式结果 comment，里面包含完整结论与后续建议
- 如果已经发布正式结果 comment，关闭 issue 时不要再附加额外 comment
- **Marker 强制**：comment 第一行行首必须以 `[apply]` 开头（前面只允许空白），让人类指令解析器准确识别为 agent 评论
  - 合规：`[apply] Closed: docs aligned with glossary; PR #123 merged.`
  - 不合规：`Apply 已完成` / `已修复 [apply]`（marker 缺失或非行首）
- 在编排链路上以 governance 身份执行的二级动作，可使用 `[governance apply]` 替代 `[apply]`，但仍须行首出现

## Stop Point

完成核查、必要动作、必要时的文档/测试修补、comment 和 close 后停止。

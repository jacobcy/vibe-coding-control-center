# Skills Shell Help And Signature Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收敛 `issue #60` 与 `issue #39` 在 skills/workflows 中的命令调用描述和署名链路，确保 shell 只是工具入口、参数不确定时先查 `-h`、并把 `--agent` / 身份校验写进正确位置。

**Architecture:** 本次只修文档与 workflow/skill 指令文本，不改业务逻辑。执行时以 shell 帮助输出为唯一命令事实源，统一补一段“参数不确定先运行 `<command> -h`/`--help`”提示，并移除任何暗示 agent 直接写真源文件或把 shell 当成业务执行者的描述。署名链路分两层处理：`vibe flow new/bind` 使用显式 `--agent` 文案；`/vibe-start`、`/vibe-continue` 增加运行时身份自检和签名补记要求。

**Tech Stack:** Zsh CLI (`bin/vibe`, `lib/*.sh`)、Markdown skills (`skills/*/SKILL.md`)、workflow files (`.agent/workflows/*.md`)、ripgrep、Bats（只做现有命令帮助验证，不新增业务测试）。

---

## 审计结论

### 已确认的事实

- `bin/vibe flow -h`、`bin/vibe flow new -h`、`bin/vibe flow bind -h`、`bin/vibe task -h`、`bin/vibe roadmap -h`、`bin/vibe skills -h` 当前都可返回帮助文本。
- `vibe flow new` 与 `vibe flow bind` 已支持 `--agent`，且 `lib/flow.sh` 会通过 `_flow_set_identity` 写入 `git config user.name/user.email`。
- `vibe flow continue` 当前不存在；执行 `bin/vibe flow continue` 只会回落到 `vibe flow` 总帮助。
- 根命令 `vibe start` 当前不存在；`/vibe-start` 只是 workflow，不是 shell 子命令。

### 当前阻塞问题

1. `issue #60`: `skills/` 中几乎所有涉及 CLI 的 skill 都没有统一要求“参数不确定先查 `-h`/`--help`”。
2. `issue #60`: `skills/vibe-task/SKILL.md` 存在多处与当前 CLI 不一致的示例参数：
   - `--branch` 用于 `vibe task add`
   - `--from-pr`
   - `--openspec-change`
   - `--source-path`
3. `issue #60`: `skills/vibe-continue/SKILL.md` 指向了不存在的 shell 命令 `vibe flow continue`。
4. `issue #39`: `skills/vibe-done/SKILL.md` 仍写有“只写 `.git/vibe/*.json`”这类越权描述，和 Shell API first 原则冲突。
5. 署名链路不完整：`.agent/workflows/vibe-new.md` 多处提示 `vibe flow new` / `vibe flow bind`，但没有同步要求追加 `--agent <agent>`。
6. 署名链路不完整：`.agent/workflows/vibe-start.md` 与 `.agent/workflows/vibe-continue.md` 都没有要求执行前进行身份自检，也没有要求在上下文/报告中补记“当前操作者”。

### 非目标

- 不处理 `issue #44` 的 roadmap 业务闭环、调度逻辑或集成测试。
- 不新增 `vibe flow continue` 或 `vibe start` shell 实现。
- 不改 `bin/vibe` / `lib/*.sh` 的业务逻辑，除非执行期发现文档无法对齐现有帮助输出。

## 任务拆分

### Task 1: 建立命令帮助校验基线

**Files:**
- Modify: `skills/vibe-check/SKILL.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `skills/vibe-done/SKILL.md`
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-skills/SKILL.md`
- Modify: `skills/vibe-task/SKILL.md`

**Step 1: 写出统一文案块**

在每个涉及 CLI 的 skill 首次出现命令处统一加入一段规则：

```md
参数、子命令或 flag 只要有任何不确定，先运行 `<command> -h` 或 `<command> --help` 确认。
Shell 命令是 agent 的工具入口，不是给用户背命令列表；对用户只汇报你要做什么和结果，不把命令教学当主输出。
```

**Step 2: 按命令域替换旧示例**

- `vibe task` 示例全部以 `bin/vibe task -h` 当前帮助为准。
- `vibe roadmap` 示例全部以 `bin/vibe roadmap -h` 当前帮助为准。
- `vibe flow` 示例全部以 `bin/vibe flow -h` / `new -h` / `bind -h` 为准。

**Step 3: 删除明显错误命令**

至少移除或改写以下示例：

```text
vibe flow continue
vibe task add ... --branch ...
vibe task add ... --from-pr ...
vibe task add ... --openspec-change ...
vibe task add ... --source-path ...
vibe task update ... --openspec-change ...
```

**Step 4: 运行文本扫描**

Run: `rg -n --fixed-strings 'vibe flow continue' skills .agent/workflows && rg -n -- '--from-pr|--openspec-change|--source-path' skills/vibe-task/SKILL.md`

Expected: 无命中。

### Task 2: 收敛 Shell API first 边界

**Files:**
- Modify: `skills/vibe-done/SKILL.md`
- Modify: `skills/vibe-skills/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `skills/vibe-save/SKILL.md`

**Step 1: 清理越权描述**

把任何类似“只写 `.git/vibe/*.json`”“直接更新 JSON 文件”的描述改成：

```md
共享真源只允许通过 shell API 更新，例如 `vibe task update`、`vibe flow bind`、`vibe skills ...`。
Skill 可以读取状态并解释，不直接手工改写真源文件。
```

**Step 2: 保留只读读取，但显式标记为读取**

对于 `registry.json` / `worktrees.json` 路径说明，补一句：

```md
这些路径仅用于状态读取、定位和解释；需要写入时必须回到 shell API。
```

**Step 3: 运行文本扫描**

Run: `rg -n "只写 .*registry\\.json|只写 .*worktrees\\.json|直接修改 .*registry\\.json|直接修改 .*worktrees\\.json" skills`

Expected: 无越权指令残留。

### Task 3: 补齐 `--agent` 文案与署名入口

**Files:**
- Modify: `.agent/workflows/vibe-new.md`
- Modify: `.agent/workflows/vibe-continue.md`
- Modify: `.agent/workflows/vibe-start.md`
- Modify: `skills/vibe-done/SKILL.md`

**Step 1: 更新 `vibe-new` 的 shell 提示**

把所有 `vibe flow new` / `vibe flow bind` 的推荐写法改成显式：

```bash
vibe flow new <feature> --agent <agent>
vibe flow bind <task-id> --agent <agent>
```

并补一句：

```md
若不确定 agent 取值，先运行 `vibe flow -h` 确认，再使用与你当前执行代理一致的 `--agent`。
```

**Step 2: 在 `/vibe-continue` 加入身份自检**

workflow 至少要求：

- 先确认当前执行代理身份
- 对比 `git config user.name`
- 不一致时先执行 `wtinit <agent>` 或等价修正动作
- 在输出中追加一行 `当前操作者: <agent>`

**Step 3: 在 `/vibe-start` 加入身份自检**

与 `/vibe-continue` 同步，且在开始执行 checklist 前先完成。

**Step 4: 与 `/vibe-done` 文案对齐**

保持 `vibe-done` 的“结项操作者”概念，但把写入方式表述成 shell/workflow 审计记录，而不是直接写 JSON。

**Step 5: 手工验证**

Run:
- `bin/vibe flow -h`
- `bin/vibe flow new -h`
- `bin/vibe flow bind -h`
- `git config user.name`

Expected:
- 帮助输出中能看到 `--agent`
- workflow/skill 文案与帮助保持一致
- 身份检查步骤有明确落点

## 预计修改文件

- `skills/vibe-check/SKILL.md`
- `skills/vibe-commit/SKILL.md`
- `skills/vibe-continue/SKILL.md`
- `skills/vibe-done/SKILL.md`
- `skills/vibe-roadmap/SKILL.md`
- `skills/vibe-save/SKILL.md`
- `skills/vibe-skills/SKILL.md`
- `skills/vibe-task/SKILL.md`
- `.agent/workflows/vibe-new.md`
- `.agent/workflows/vibe-continue.md`
- `.agent/workflows/vibe-start.md`

## 验证命令

```bash
bin/vibe flow -h
bin/vibe flow new -h
bin/vibe flow bind -h
bin/vibe task -h
bin/vibe roadmap -h
bin/vibe skills -h
bin/vibe flow continue
bin/vibe -h
rg -n --fixed-strings 'vibe flow continue' skills .agent/workflows
rg -n -- '--from-pr|--openspec-change|--source-path' skills/vibe-task/SKILL.md
rg -n '参数不确定|查看帮助|--help|-h' skills .agent/workflows
rg -n '当前操作者|Identity|--agent' skills .agent/workflows
```

## 预期结果

- 所有涉及 shell 的 skill 都有统一的 help 自检提示。
- `skills/vibe-task/SKILL.md` 不再引用不存在或过时的 task flags。
- `skills/vibe-continue/SKILL.md` 不再引用不存在的 `vibe flow continue`。
- `skills/vibe-done/SKILL.md` 不再暗示直接写真源 JSON。
- `.agent/workflows/vibe-new.md` 明确推荐 `vibe flow new/bind --agent <agent>`。
- `.agent/workflows/vibe-start.md` 与 `.agent/workflows/vibe-continue.md` 明确追加身份自检与“当前操作者”署名记录。

## 变更摘要（预估）

- 新增：约 `40-70` 行
- 删除：约 `25-45` 行
- 修改：约 `80-140` 行
- 总文件数：`11`

## 执行备注

- 因为预计修改文件数 `>5`，进入执行前需要用户确认。
- 若执行期发现某条 skill 文案与实际 shell 帮助继续冲突，以 `bin/vibe ... -h` 的当前输出为准，不自行扩写业务语义。

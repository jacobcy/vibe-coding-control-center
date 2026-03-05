# Vibe New 三层分离计划

## Goal

- 收敛 `vibe-new` 相关职责，明确三层分离：
  - `config` 层：只负责路径、环境变量、密钥与默认值。
  - `workflow skills` 层：保留 `task / flow / save / continue / check` 这类直接面向用户、代表一个业务流程动作的 skill。
  - `supervisor` 层：统一管理 gate、生命周期编排、skills/plugin/symlink/audit 等治理能力，不再散落在 `skills/` 业务目录内。
- 让 `vibe-new` 在文档和命令入口上指向新的职责边界，避免继续把入口编排、业务 workflow skill、治理型 supervisor 混在一起。
- 统一共享运行态概念到 `.git/vibe/`，废弃 `.git/shared` 的概念漂移。
- 保持 artifact 可读性：计划、README、说明等正文继续放在 `docs/`，共享目录只保存状态和指针，不长期保存 artifact 正文。

## Non-Goals

- 不重写 `vibe task` / `vibe flow` 的 registry 或 worktree 模型。
- 不改变现有 alias 具体命令行为，只调整归属和加载路径。
- 不重写 `task / flow / save / continue / check` 这些 workflow skill 的对外语义。
- 不重做 skills registry 数据结构。
- 不在本期引入复杂 supervisor 守护进程；这里的 supervisor 指 shell 编排层，不是常驻后台服务。
- 不把计划正文、任务 README、长文档长期迁入 `.git/vibe/`。

## Tech Stack

- Zsh shell scripts
- bats
- `scripts/lint.sh`

## Current Findings

- `bin/vibe` 直接 `source "$VIBE_ROOT/lib/config.sh"`，随后在 `alias` 子命令里再 `source "$VIBE_CONFIG/aliases.sh"`，说明 alias 仍被视为 config 附属物。
- `lib/config.sh` 当前职责已经足够聚焦，仅包含路径、utils、keys、defaults；真正的耦合点主要是 `bin/vibe` 的 alias 入口和 `config/aliases.sh` 的落位。
- `lib/skills.sh` 只是 CLI dispatcher，但通过 `lib/skills_sync.sh` 承担了 plugin 检查、全局安装、agent symlink、本地 skill 链接、审计报告等 supervisor 级编排职责。
- 当前代码实际读写的共享真源是 `$(git rev-parse --git-common-dir)/vibe/`，不是 `.git/shared/`。
- `.git/shared/` 目前只剩遗留文件，缺乏稳定读写路径；继续保留这个概念会误导 workflow 和 skill 设计。
- `skills/` 目录当前同时包含两类内容：
  - 面向用户动作的 workflow skills，例如 `vibe-check`、`vibe-continue`、`vibe-save`、`vibe-task`、`vibe-commit`。
  - 面向治理和门禁的 guard/orchestrator skills，例如 `vibe-orchestrator`、`vibe-scope-gate`、`vibe-rules-enforcer`、`vibe-audit`、`vibe-test-runner`。
- 当前真正需要拆出来的是第二类治理型能力，而不是把全部 skills 从目录层面迁走。
- `vibe-save` / `vibe-continue` 已经在 skill 文案里依赖 `task.json` 中的 pointer 字段（如 `plan_path`），但 shell 端还没有完整的 artifact pointer 写入能力。

## Proposed Architecture

### Layer 1: Entry / Workflow

- `bin/vibe` 与 `/vibe-new` 只负责入口和路由说明。
- 直接面向用户的 workflow skills 继续留在 `skills/`，例如：
  - `vibe-task`
  - `vibe-check`
  - `vibe-save`
  - `vibe-continue`
  - `vibe-commit`
  - 以及与 `flow` 直接对应的 workflow skill
- 这些 skill 表达“用户要做什么”，不负责 gate 编排或全局治理。

### Layer 2: Runtime Surface

- `lib/config.sh` 保持纯配置入口。
- 新建独立 alias loader（建议 `lib/alias.sh`），由 `vibe alias` 子命令调用。
- `config/aliases.sh` 降级为兼容壳或删除，取决于测试迁移成本。

### Layer 3: Supervisor / Governance

- 新建独立 `supervisor/` 目录，承载治理型能力，而不是继续把它们混放在 `skills/`。
- 迁移对象优先包括：
  - gate 类能力：`scope gate`、`plan/spec/test/review/audit` 相关编排
  - orchestrator 类能力：`vibe-orchestrator`
  - skills 生命周期治理：plugin、symlink、sync、audit
- `vibe skills` 保留为领域命令，只做用户语义入口；真正的治理编排委托给 supervisor 层。
- 目标不是新增常驻服务，而是把“流程生命周期控制器”独立成单独目录与职责面。

### Shared State Model

- 共享运行态真源统一为 `$(git rev-parse --git-common-dir)/vibe/`：
  - `registry.json`
  - `worktrees.json`
  - `tasks/<task-id>/task.json`
- `docs/` 继续保存人类可读 artifact：
  - `docs/plans/*.md`
  - `docs/tasks/*/README.md`
  - 其他 spec / review / note
- `.git/vibe/tasks/<task-id>/task.json` 只保存 pointer 和运行态摘要，例如：
  - `plan_path`
  - `memory_path`
  - `readme_path`
  - `status`
  - `next_step`
  - `assigned_worktree`
- `.vibe/` 继续作为 worktree 本地缓存，不是真源。

## Tasks

### Task 1: 先用测试锁定“workflow skills vs supervisor”边界

**Files to modify**
- `tests/test_vibe.bats`
- `tests/test_skills.bats`
- `tests/test_utils.bats`

**Work**
- 为 `vibe alias` 增加边界测试，确认 alias 加载不再依赖 `config/aliases.sh` 作为主入口。
- 为 `vibe skills` 增加边界测试，确认 CLI 仍可用，但治理实现通过 supervisor 层委托。
- 为 `lib/config.sh` 增加约束测试，确认其不再暴露 alias/supervisor 特有职责。
- 为目录边界增加断言：
  - workflow skills 继续在 `skills/`
  - gate / orchestrator / lifecycle 能力迁入 `supervisor/`
- 为共享状态模型增加断言：
  - `.git/vibe` 是唯一共享运行态目录
  - `.git/shared` 不再作为主路径出现在 workflow/skill 契约中
  - artifact 正文继续留在 `docs/`

**Test command**
```bash
bats tests/test_vibe.bats tests/test_skills.bats tests/test_utils.bats
```

**Expected result**
- 新增断言先失败，明确现状与目标边界不一致。

### Task 2: 把 aliases 从 config 目录语义中拆出来

**Files to modify**
- `bin/vibe`
- `lib/config.sh`
- `lib/alias.sh`（新增）
- `config/aliases.sh`

**Work**
- 新增 alias loader，统一处理 `VIBE_ROOT`、repo root、main 路径与 alias 子文件加载。
- 将 `bin/vibe` 的 `alias)` 分支改为 source 新的 alias 模块。
- 保持 `config` 层只负责环境与默认值，不承载 alias 入口语义。
- 评估 `config/aliases.sh` 保留兼容转发还是删除；优先选择兼容转发，减少现有 shell 用户断裂。

**Test command**
```bash
bats tests/test_vibe.bats tests/test_utils.bats
```

**Expected result**
- `vibe alias` 行为不变。
- `lib/config.sh` 仍可被其他测试安全 source，不隐式引入 alias 逻辑。

### Task 3: 把治理型能力从 `skills/` 分离到 `supervisor/`

**Files to modify**
- `bin/vibe`
- `lib/skills.sh`
- `supervisor/`（新增目录）
- `lib/skills_sync.sh` 或对应兼容层
- `tests/test_skills.bats`

**Work**
- 把 gate / orchestrator / lifecycle 相关治理能力从 `skills/` 迁到 `supervisor/`。
- 把 `lib/skills_sync.sh` 中的 sync/plugin/symlink/audit 编排迁到 supervisor 层。
- `lib/skills.sh` 缩成领域命令分发层，只保留 `vibe skills <subcommand>` 的语义接口。
- 根据实现成本决定：
  - 方案 A：保留原治理型 `SKILL.md` 作为兼容壳，内部转发到 `supervisor/`
  - 方案 B：直接改引用路径，并同步更新 workflow 文档
- 如新增 `vibe supervisor` 命令或 supervisor 入口文档，help 文案必须明确它是治理层，不与 workflow skills 混淆。

**Test command**
```bash
bats tests/test_skills.bats tests/test_vibe.bats
```

**Expected result**
- 现有 `vibe skills check/sync` 对外行为保持兼容。
- workflow skills 仍在 `skills/`。
- gate 与 lifecycle 治理职责已脱离 `skills/` 目录。

### Task 4: 统一 `.git/vibe` 真源与 artifact pointer 模型

**Files to modify**
- `lib/task_actions.sh`
- `lib/task_write.sh`
- `lib/task_help.sh`
- `tests/test_task*.bats`
- `skills/vibe-save/SKILL.md`
- `skills/vibe-continue/SKILL.md`
- `.agent/workflows/vibe-new.md`

**Work**
- 为 `vibe task add/update` 增加 pointer 字段写入能力，至少覆盖：
  - `plan_path`
  - `readme_path`
  - `memory_path`（如确有共享 memory）
- 明确 pointer 指向 `docs/` 下 artifact，而不是把正文复制到 `.git/vibe/`
- 清理所有仍把 `.git/shared` 当成主路径的文档和契约
- 保持 `task.json` 是共享状态索引，而不是 artifact 正文容器

**Test command**
```bash
bats tests/test_task.bats tests/test_task_ops.bats tests/test_task_sync.bats
```

**Expected result**
- shell 能把 artifact 路径登记到 `.git/vibe/tasks/<task-id>/task.json`
- skills 通过 pointer 找到 `docs/` 中的真实 artifact
- `.git/shared` 不再出现在主流程契约中

### Task 5: 对齐 vibe-new 文档与入口说明

**Files to modify**
- `.agent/workflows/vibe-new.md`
- `skills/vibe-orchestrator/SKILL.md`
- `tests/test_vibe.bats`

**Work**
- 将 `vibe-new` 的边界说明改成三层模型，避免后续文档继续把 alias/config/supervisor/skills 混说。
- 更新顶层 help 或相关说明文案，使用户从入口就能看到新的职责划分。

**Test command**
```bash
bats tests/test_vibe.bats
```

**Expected result**
- help 与 workflow 文档指向一致的层级模型。

### Task 6: 全量验证与收口

**Files to modify**
- 无新增功能文件；只收口前面任务的必要调整

**Test command**
```bash
bash scripts/lint.sh
bats tests/test_vibe.bats tests/test_skills.bats tests/test_utils.bats tests/test_task*.bats
```

**Expected result**
- shell lint 通过。
- 相关 bats 用例全绿。
- `vibe alias`、`vibe skills`、`vibe-new` 的帮助与边界描述一致。
- `.git/vibe` 与 `docs/` 的分工清晰，pointer 路径可被 skill 稳定消费。

## Expected Result

- `config` 成为纯配置层。
- `alias` 成为独立运行时入口层。
- `skills/` 只保留 workflow 类能力。
- `supervisor/` 单独承载 gate、orchestrator、lifecycle 治理能力。
- `.git/vibe` 成为唯一共享运行态真源。
- `docs/` 保持 artifact 正文真源，`.git/vibe` 只保存状态与 pointer。
- `vibe-new` 的入口叙事与代码结构一致，不再把 workflow 和治理职责混在一处。

## Change Summary Estimate

- Added: 2 个新模块文件，约 120-180 行。
- Modified: 5-7 个现有文件，约 80-140 行。
- Removed: 旧耦合代码约 40-80 行，优先通过兼容转发渐进迁移。

---
document_type: plan
title: Vibe3 Parallel Rebuild Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-16
related_docs:
  - docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/plans/2026-03-13-shell-thinning-python-core-plan.md
  - docs/plans/2026-03-13-gh-157-worktrees-json-retirement-implementation-plan.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/data-model-standard.md
related_issues: []
---

# Vibe3 Parallel Rebuild Design Freeze Plan

> **定位说明：** 这是 `planner` 侧的 design-freeze checklist，不是 `executor` 的 implementation playbook。
> `executor` 可以写或维护 `docs/v3/` 下的 playbook，但不得在执行实现时反向改写本文件要冻结的语义边界。

> **数据真源**: 数据库字段定义见 [docs/standards/v3/handoff-store-standard.md](../standards/v3/handoff-store-standard.md)。
> **GitHub 调用**: 远端调用标准见 [docs/standards/v3/github-remote-call-standard.md](../standards/v3/github-remote-call-standard.md)。

**Goal:** 在当前仓库内把 `vibe3` 的新语义冻结下来，尤其是 `repo issue -> task issue(Project) -> flow(branch) -> plan/spec ready -> draft PR` 这条主链，并据此收敛命令契约、目录结构、Python 栈与依赖策略；真正的实施顺序改由 `docs/v3/` 编号文档承载。

**Architecture:** 保留 `lib/` 与 `tests/` 作为 2.x 现行实现，不先改名，也不先迁移，便于其他分支继续提交 bugfix。`vibe3` 先停留在设计冻结阶段：先讨论命令、目录、Python 框架与依赖，等这些结论稳定后，再开始并行实现。

**Tech Stack:** Markdown, Zsh, Python 3（框架与依赖待定）, Git, GitHub CLI

---

## Task 1: 冻结 `vibe3` 主链与命令边界

**Files:**
- Create: `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- Create: `docs/plans/2026-03-13-vibe3-parallel-rebuild-plan.md`
- Inspect: `docs/standards/v2/command-standard.md`
- Inspect: `docs/standards/v2/shell-capability-design.md`

**Step 1: Write the design gap audit**

- 列出当前还没讨论清楚的 `v3` 命令问题：
  - `roadmap` 是否退出主命令面
  - `pr` 是否独立成域
  - `flow` 是否以 `branch` 为唯一身份锚点
  - `flow freeze --by ...` 是否进入首批命令
  - 一个 flow 是否允许多个 `repo issue`、但只允许一个 `task issue`
  - 是否同时支持快捷路径和 agent 分步路径
  - `flow bind task <repo-issue>` 是否作为最终形态
  - `task add --repo-issue` 与 `task link` 是否分层
  - `task` / `pr` 分组是否进入首批模型，以及默认 bump 策略如何绑定分组
  - `task --agent` / `pr --agent` 是否进入首批参数
  - 署名是否统一展示为 `agent/model`
  - `flow new --save-unstash` / `flow switch` 的 stash 规则
  - `flow show` / `flow status` 默认展示哪些链路字段
  - `report` 是否作为 executor -> reviewer 的对等交接物
  - `audit` 是否作为 reviewer -> ready/merge 的对等交接物
  - `plan/report/audit` 是否作为 merge 前必须可见的审查文件
  - 若 task 过大，executor 是否可以提出 scope challenge 并退回 sub issue 拆分
  - 3.0 strong handoff 是否只存责任链，而不存 GitHub Project 镜像
  - `--json` 契约哪些必须保留
  - 自动版本号 / 自动 changelog 保留在哪个 PR 阶段
  - `spec_ref` 如何进入 `pr draft` / `pr ready`
  - issue auto-link / auto-close 哪些保留为核心语义
  - publish preflight、stacked/base safety 是否作为 `pr` 域护栏保留
  - `pr review` 是否作为独立首批子命令，并要求 review 结果回贴 PR
  - handoff 是否提升为 flow 级固定 memo，由命令自动刷新固定区块

**Step 2: Run audit to verify gaps are real**

Run:

```bash
rg -n "roadmap|task|flow|check|--json" docs/standards/v2/command-standard.md docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
```

Expected:
- 当前设计还没有完全冻结 `v3` 主链与命令边界

**Step 3: Write minimal design update**

- 在 design 文档中补齐：
  - `repo issue -> task issue(Project) -> flow(branch) -> plan/spec ready -> draft PR`
  - `roadmap` 退出主命令面
  - `pr` 独立成域
  - `flow freeze --by ...` 的用途
  - `flow` 可绑定多个 `repo issue`，但只绑定一个 `task issue`
  - 人类可用 `flow new --bind ... --pr-draft`，agent 仍建议分步
  - `flow bind task <repo-issue>` 直接把 repo issue 提升为 task issue
  - `task add --repo-issue` 负责提升，`task link` 只负责链接
  - `task` / `pr` 分组进入设计，并绑定默认 bump 策略
  - `task --agent` / `pr --agent` 保留署名能力
  - `vibe auth` 退出 3.0 主线，统一改由 `vibe handoff` 承担阶段身份声明
  - `vibe handoff plan/report/audit --agent <agent> --model <model>` 固定为推荐形态
  - 署名展示默认使用 `agent/model`
  - 本地只保留 flow-scoped handoff 责任链，不引入 `sessions.json` / PID / 进程级 auth
  - `.agent/context/task.md` 明确降级为 2.x legacy local handoff
  - `flow new --save-unstash` 保留，`flow switch` 默认 stash / restore
  - 所有命令都必须有清晰提示，不允许空回复
  - 自动版本号 / changelog 作为 `pr` 域保留能力继续存在
  - `pr draft` 是 planner 在 planning ready 后的收尾动作，负责远端锚点与元数据绑定；`pr ready` 负责 publish gate
  - `pr review` 负责本地 Codex 审查与 PR comment 回贴
  - `spec_ref` 必须进入 PR 链路
  - `report` / `audit` 作为正式交接物进入设计
  - `plan/report/audit` 作为 merge 前审查文件进入设计
  - 若 task 过大，executor 可以提出 scope challenge，并退回给 planner / 人类拆成 sub issue
  - auto-link、preflight、stacked/base safety 作为保留护栏写入设计
  - handoff 作为 flow 级 memo 进入设计，当前仍先用 Markdown

**Step 4: Run audit to verify it passes**

Run:

```bash
rg -n "命令契约|待决|未冻结|不进入实现" docs/plans/2026-03-13-vibe3-parallel-rebuild-*.md
```

Expected:
- 主链与命令边界已显式写出

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md docs/plans/2026-03-13-vibe3-parallel-rebuild-plan.md
git commit -m "docs(vibe3): freeze chain and command boundaries"
```

## Task 2: 冻结目录结构讨论范围

**Files:**
- Modify: `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- Inspect: `STRUCTURE.md`
- Inspect: `bin/vibe`
- Inspect: `lib/`

**Step 1: Write the directory decision audit**

- 列出还未定的目录问题：
  - 是否按 `flow / task / pr` 分子目录
  - shell / python / tests 三层如何对应
  - 是否需要 `bin/vibe2`

**Step 2: Run audit to verify ambiguity exists**

Run:

```bash
rg -n "lib3|tests3|src|bin/vibe2|bin/vibe3" docs/plans/2026-03-13-vibe3-parallel-rebuild-*.md
```

Expected:
- 目录层当前只是方向，不是最终定稿

**Step 3: Write minimal design update**

- 在 design 文档中明确：
  - `lib/` 继续保留
  - `lib3/` 只是候选名，不是最终承诺
  - 目录设计冻结前，不创建新实现目录
  - 本地缓存目录不承担主链真源职责
  - 目录优先按 `flow / task / pr` 分域

**Step 4: Run audit to verify it passes**

Run:

```bash
rg -n "继续保留|候选名|不创建新实现目录" docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
```

Expected:
- 目录讨论边界已写清

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
git commit -m "docs(vibe3): freeze directory discussion scope"
```

## Task 3: 冻结 Python 框架与依赖策略讨论范围

**Files:**
- Modify: `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- Inspect: `docs/plans/2026-03-13-shell-thinning-python-core-design.md`

**Step 1: Write the stack decision audit**

- 列出还未定的点：
  - 使用 `uv` 是否冻结为默认工具
  - 只用 stdlib 还是允许少量三方依赖
  - 是否引入 CLI framework
  - JSON / schema / GitHub API 解析怎么组织
  - Project / PR / issue 链路重建时用哪些远端接口

**Step 2: Run audit to verify gaps remain**

Run:

```bash
rg -n "stdlib|依赖|框架|CLI" docs/plans/2026-03-13-shell-thinning-python-core-design.md docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
```

Expected:
- Python 技术选型仍未冻结

**Step 3: Write minimal design update**

- 在 design 文档中明确：
  - Python 方向成立
  - `uv + 最小依赖` 是当前优先方向
  - `check` 和 cache 暂不进入第一批实现
  - 没有结论前不创建 Python 骨架

**Step 4: Run audit to verify it passes**

Run:

```bash
rg -n "待决项|依赖策略|框架|不创建 Python 骨架" docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
```

Expected:
- Python 选型边界已显式写清

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
git commit -m "docs(vibe3): freeze python stack discussion scope"
```

## Task 4: 产出实现前的最终设计冻结结论

**Files:**
- Modify: `docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md`
- Modify: `docs/plans/2026-03-13-vibe3-parallel-rebuild-plan.md`

**Step 1: Write the final decision checklist**

- 对以下四项给出最终结论：
  - `v3` 主链与命令边界
  - 目录结构
  - Python 框架
  - 依赖策略

**Step 2: Run checklist audit**

Run:

```bash
rg -n "待决项|未冻结" docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
```

Expected:
- 仍存在待决项，不能进入实现

**Step 3: Write minimal design resolution**

- 把待决项收敛为正式设计结论
- 生成下一版“可执行实现计划”

**Step 4: Run audit to verify it passes**

Run:

```bash
rg -n "待决项|未冻结" docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
```

Expected:
- 不再存在阻止实现的设计缺口

**Step 5: Commit**

```bash
git add docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md docs/plans/2026-03-13-vibe3-parallel-rebuild-plan.md
git commit -m "docs(vibe3): freeze pre-implementation decisions"
```

## Task 5: 实施文档已就绪，开始按阶段执行

> **🔥 状态更新**：实施文档已完成！详见 **[docs/v3/infrastructure/](../v3/infrastructure/README.md)**

**Files:**
- ✅ Created: `docs/v3/infrastructure/README.md` - 实施索引
- ✅ Created: `docs/v3/infrastructure/00-skeleton-setup.md` - 骨架搭建指南
- ✅ Created: `docs/v3/infrastructure/01-config-management.md` - 配置管理
- ✅ Created: `docs/v3/infrastructure/06-error-handling.md` - 异常处理
- ✅ Created: `docs/v3/infrastructure/05-logging.md` - 日志系统
- ✅ Created: `.agent/rules/python-standards.md` - Python 标准
- ✅ Updated: `docs/v3/handoff/v3-rewrite-plan.md` - 阶段划分

**Step 1: 验证实施文档完整性**

Run:

```bash
ls -la docs/v3/infrastructure/
```

Expected:
- ✅ 所有实施文档已创建
- ✅ Python 标准文件已创建

**Step 2: 验证阶段划分**

Run:

```bash
grep -n "Phase [0-9]:" docs/v3/handoff/v3-rewrite-plan.md
```

Expected:
- ✅ Phase 0-6 已定义
- ✅ 每个 Phase 有明确目标和验收标准

**Step 3: 开始执行**

**执行顺序**：
1. **Phase 0**（准备）：阅读设计文档（1-2 小时）
2. **Phase 1**（骨架）：搭建基础设施（2-3 小时）
   - 参考：[docs/v3/infrastructure/00-skeleton-setup.md](../v3/infrastructure/00-skeleton-setup.md)
3. **Phase 2**（Client）：封装外部依赖（3-4 小时）
4. **Phase 3**（Service）：实现业务逻辑（5-6 小时）
5. **Phase 4**（Command）：提供命令接口（3-4 小时）
6. **Phase 5**（测试）：验证端到端流程（2-3 小时）
7. **Phase 6**（文档）：完善文档和发布（2-3 小时）

**总时间**：18-25 小时（约 3-4 个工作日）

**Step 4: Commit**

```bash
git add docs/v3/infrastructure/
git add .agent/rules/python-standards.md
git add docs/v3/handoff/v3-rewrite-plan.md
git commit -m "docs(v3): complete implementation documentation with phase-based execution plan

- Add Python standards (.agent/rules/python-standards.md)
- Add skeleton setup guide (00-skeleton-setup.md)
- Add config management guide (01-config-management.md)
- Add error handling guide (06-error-handling.md)
- Add logging system guide (05-logging.md)
- Update rewrite plan with Phase 0-6 definition
- Total estimated time: 18-25 hours"
```

**Step 5: 开始 Phase 0**

现在可以开始执行了！请查看：

1. **[docs/v3/handoff/v3-rewrite-plan.md](../v3/handoff/v3-rewrite-plan.md)** - 了解各阶段目标
2. **[docs/v3/infrastructure/README.md](../v3/infrastructure/README.md)** - 查看快速开始指南
3. **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** - 遵循 Python 标准

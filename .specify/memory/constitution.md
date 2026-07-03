<!--
=== Sync Impact Report ===
Version change: (unset) → 1.0.0
Rationale: 首次为 spec-kit 工作流确立 constitution。MAJOR = 初始采纳。

Design principle: 本文件是 **桥接文档**，严格遵守 SOUL.md §0 单一事实原则 ——
只定义 spec-kit 工作流特有的规则，不重复阐述上游真源（SOUL.md / CLAUDE.md /
.claude/rules/*）的内容，仅引用。

Authority hierarchy: SOUL.md > CLAUDE.md > .claude/rules/* > 本文件

Evidence anchors（理据中的 issue/PR 编号）取自近 30 合并/开放议题，用于说明
原则在开发实践中的体现，不在本文件重新定义这些实践规则。

Modified principles (all NEW):
  - I.   Cognition First, Spec Before Code
  - II.  Single Source of Truth (Reference, Don't Reimplement)
  - III. Verification Before Claim
  - IV.  Bridge, Don't Reimplement (Skill-First Alignment)
  - V.   Worktree-Isolated Specs

Added sections:
  - "Spec-Kit Workflow Conventions"        (替换 [SECTION_2_NAME])
  - "Authoritative Source References"       (替换 [SECTION_3_NAME])

Removed sections: 无

Templates requiring updates:
  - .specify/templates/plan-template.md        ✅ 无需改动 — Constitution Check 运行时从本文件派生
  - .specify/templates/spec-template.md        ✅ 无需改动
  - .specify/templates/tasks-template.md       ✅ 无需改动
  - .specify/extensions/superspec/             ✅ 已安装（v1.0.1），hooks 激活

Follow-up TODOs: 无
Inference basis: SOUL.md + CLAUDE.md (19 HARD RULES) + .claude/rules/* + 近 30 issues/PR
===
-->

# Vibe Center Spec-Kit Constitution

本文件治理 **spec-kit 工作流**在本项目中的使用。项目通用的宪法、边界与硬规则
不在本文件重复，分别由 [SOUL.md](../../SOUL.md) 与
[CLAUDE.md](../../CLAUDE.md) 承载。

**权限层级**：`SOUL.md` > `CLAUDE.md` > `.claude/rules/*` > 本文件。
任何冲突一律以上游真源为准。

## Core Principles

### I. Cognition First, Spec Before Code

对齐 [SOUL.md](../../SOUL.md) §3「认知优先，代码次之」与 [CLAUDE.md](../../CLAUDE.md)
HARD RULES #1。

- 非平凡变更 MUST 先有 spec（`.specify/specs/NNN-*/spec.md`）再写实现。
- spec-kit 六阶段流程为本项目默认规格化路径：
  `brainstorm → specify → plan → tasks → implement → review`。
- 纯问答、文档阅读、临时分析（[CLAUDE.md](../../CLAUDE.md)「开发入口规则」已列）
  无需走 spec-kit 流程。

理据：近 30 PR 中 21 次 refactor 与 41 次 fix 反映「先想清楚再改」的回报极高；
`#3282`/`#3293` 类 dispatch 缺陷均源于语义未先规格化导致的状态判定不一致。

### II. Single Source of Truth (Reference, Don't Reimplement)

对齐 [SOUL.md](../../SOUL.md) §0「单一事实原则 + 渐进披露」与
[.claude/rules/modularity-standards.md](../../.claude/rules/modularity-standards.md)。

- 每条 spec 规则只在**一处**定义；上游已有真源的，spec MUST 引用而非复述。
- spec.md 是 feature 的需求真源；plan/tasks 派生自 spec，MUST NOT 反向发明需求。
- 跨 feature 的通用约束 MUST 指向 `.claude/rules/*` 或 `docs/standards/*`，不在
  多个 spec 间复制。

理据：`#3267`/`#3290`（remove dead exports / dead domain）、`#3261`（remove dead
public exports）连续修复同一类「重复定义漂移」问题 —— 规格层同样必须避免。

### III. Verification Before Claim

对齐 [CLAUDE.md](../../CLAUDE.md) HARD RULES #3（验证先于声称完成）、#14
（CI 优先的测试节奏）与 superpowers `test-driven-development`。

- 每条 task MUST 带可验证证据（测试输出、命令结果、可复现步骤），与 HARD RULES #3 一致。
- TDD 在 spec-kit `implement` 阶段强制：Red-Green-Refactor（由 superspec
  `before_implement` hook 保障）。
- 本地避免全量回归，定向测试 + CI 复验（HARD RULES #14）。

理据：`#3260`（plan.policy 增加 test behavior verification rule）、
`#3269`（record qualify gate failures in error_log）—— 验证门已是一等公民。

### IV. Bridge, Don't Reimplement (Skill-First Alignment)

对齐 [CLAUDE.md](../../CLAUDE.md) HARD RULES #15（最短路径优先）、#16
（Skill-First 命令准入三问法）与 `superspec` 扩展的 bridge 定位。

- spec-kit 与项目已有 `vibe-*` skills 是**互补**关系，不是替代：
  - `/vibe-new` 仍是开发入口（HARD RULES「开发入口规则」），负责 issue 绑定、
    worktree bootstrap、flow scene。
  - spec-kit 负责**规格产出**（spec/plan/tasks 文档），由 superspec bridge 接入
    superpowers 的 brainstorm / writing-plans / TDD / code-review。
- spec 描述的「做什么」，MUST NOT 规定「用什么命令实现」—— 命令准入走 #16 三问法。
- 编排型能力 MUST 走 Skill，不在 spec 中隐式要求新增 Python 命令层。

理据：`#3279`/`#3295`（public API sections）、`#3271`（delegate SQL to
ErrorTrackingService）—— 现有能力「接线复用」是项目主流路径。

### V. Worktree-Isolated Specs

对齐 [CLAUDE.md](../../CLAUDE.md) HARD RULES #8（Agent 与 worktree 一对一）、
#5（Git 纪律，feature 分支）。

- 每个 feature spec 对应一个 `dev/issue-<id>` 或 `task/issue-<id>` worktree。
- spec/plan/tasks 产出在 `.specify/specs/NNN-<slug>/`，随分支流转，合入 main 后
  归档为该 feature 的规格真源。
- 路径解析相关的 spec 条款 MUST 兼容 bare-repo + linked-worktree 模型（HARD RULES #8）。

理据：`#3268`/`#3253`/`#3246`（bare repo compatibility）、`#3259`/`#3277`
（path anchoring to main repo root）—— worktree 兼容是不可协商边界。

## Spec-Kit Workflow Conventions

本节定义 spec-kit 在本项目内的**特有约定**（其余行为遵循 spec-kit 默认）。

- **Integration**：`claude`（见 `.specify/integration.json`）。
- **Feature numbering**：`sequential`（001, 002, ...，见 `.specify/init-options.json`）。
- **Spec 目录**：`.specify/specs/NNN-<slug>/{spec,plan,tasks}.md`。
- **Constitution 真源**：`.specify/memory/constitution.md`（本文件）。
- **扩展**：`superspec` v1.0.1（bridge），3 个 optional hooks 全部启用（auto_execute）。
- **Git 追踪策略**：追踪 `memory/`、`specs/`、`templates/`、`workflows/`、`*.yml/json`；
  忽略 `.specify/extensions/`（安装产物）、`.specify/scripts/`（CLI 依赖）。详见
  项目 `.gitignore` 的「Spec-Kit」段落。
- **与 OpenSpec 的关系**：本项目 `openspec/` 此前未实际使用（空），已被 `.gitignore`
  忽略。spec-kit 是本项目唯一的 spec-driven 工具链，避免双轨（原则 II）。

## Authoritative Source References

本 constitution **不承载**以下内容，仅提供引用链（渐进披露，SOUL.md §0）：

| 真源 | 路径 | 承载内容 |
|------|------|----------|
| 项目宪法 | [SOUL.md](../../SOUL.md) | 价值观、边界、优先级、单一事实原则 |
| 硬规则 | [CLAUDE.md](../../CLAUDE.md) §HARD RULES | 19 条最小不可协商规则 |
| 项目结构 | [STRUCTURE.md](../../STRUCTURE.md) | 目录结构、Three-Tier 架构、文件职责 |
| 术语真源 | [docs/standards/glossary.md](../../docs/standards/glossary.md) | 项目术语定义 |
| Python 标准 | [.claude/rules/python-standards.md](../../.claude/rules/python-standards.md) | 分层、依赖方向、uv、测试隔离 |
| 模块化 | [.claude/rules/modularity-standards.md](../../.claude/rules/modularity-standards.md) | 公开 API、`__all__`、lazy import、barrel |
| 编码细则 | [.claude/rules/coding-standards.md](../../.claude/rules/coding-standards.md) | 文件/函数大小、Shell/Skill 边界、交付纪律 |
| 执行模式 | [.claude/rules/patterns.md](../../.claude/rules/patterns.md) | 常规/快速模式、Context First、Fail Fast |
| Agent 工作流 | [docs/standards/agent-workflow-standard.md](../../docs/standards/agent-workflow-standard.md) | plan/run/review 权威流程 |

spec 产出 MUST 引用上述真源而非复述。发现 spec 与真源冲突时，修正 spec，
不修正真源（除非真源本身需演进，届时走真源自身的维护流程）。

## Governance

- **与 SOUL.md 的关系**：本文件 subordinate 于 SOUL.md。SOUL.md §6 权限层级
  （`SOUL.md > CLAUDE.md > .claude/rules/* > 其他`）对本文件完全适用。
- **Amendments**：修订 MUST (a) 遵循 SOUL.md §0 单一事实原则（不得把上游内容
  复制进本文件）、(b) 更新顶部 Sync Impact Report、(c) 按 semver 更新版本号。
- **版本策略**：MAJOR = 原则删除/重定义或权限层级调整；MINOR = 新增原则或
  section；PATCH = 措辞、引用链接、对齐上游变更。
- **合规审查**：`/speckit.superspec.review` 在 implement 后对照 spec 与真源；
  plan 阶段的 Constitution Check（见 plan-template）从本文件派生 gate。
- **运行时指导**：Agent 执行规则见 [CLAUDE.md](../../CLAUDE.md) 与
  [.claude/rules/](../../.claude/rules/)；本文件不替代它们。

**Version**: 1.0.0 | **Ratified**: 2026-07-03 | **Last Amended**: 2026-07-03

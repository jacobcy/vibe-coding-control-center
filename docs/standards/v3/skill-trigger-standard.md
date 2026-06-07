---
document_type: standard
title: Skill Trigger And Intervention Standard
status: active
scope: skill-routing
authority:
  - skill-trigger-routing
  - skill-intervention-timing
  - adjacent-skill-conflict-resolution
author: GPT-5.4
created: 2026-03-10
last_updated: 2026-06-03
related_docs:
  - SOUL.md
  - CLAUDE.md
  - ../../README.md
  - ../glossary.md
  - ../action-verbs.md
  - skill-standard.md
  - skills/vibe-issue/SKILL.md
  - skills/vibe-roadmap/SKILL.md
  - skills/vibe-task/SKILL.md
  - skills/vibe-check/SKILL.md
  - skills/vibe-new/SKILL.md
  - skills/vibe-continue/SKILL.md
  - skills/vibe-commit/SKILL.md
  - skills/vibe-integrate/SKILL.md
  - skills/vibe-done/SKILL.md
  - skills/vibe-closeout/SKILL.md
  - skills/vibe-onboard/SKILL.md
  - skills/vibe-project-check/SKILL.md
  - skills/vibe-instruction/SKILL.md
  - skills/vibe-skill-audit/SKILL.md
  - skills/vibe-skills-manager/SKILL.md
  - skills/vibe-debug-serve/SKILL.md
  - skills/vibe-redundancy-audit/SKILL.md
  - skills/vibe-rules/SKILL.md
  - skills/vibe-save/SKILL.md
  - skills/vibe-team-review/SKILL.md
---

# Skill Trigger 与介入时机标准

本文档定义具体 Vibe skills 的应用时机、自然语言触发矩阵和相邻 skill 的分流优先级。

本文档**不**重新定义 `skill`、`workflow`、`task`、`roadmap`、`flow`、`worktree` 等术语；正式语义以 `../glossary.md` 为准。skills 的源码/运行时边界以 `skill-standard.md` 为准。

## 1. 设计目标

- 让 skill 在"该介入时能介入"，而不是只靠显式 slash 命令。
- 让相邻 skill 在用户自然语言模糊时也能稳定分流。
- 让 `description` 成为发现面，而不是流程摘要。

## 2. 路由原则

### 2.1 先看对象层级，再看动作类型

路由时按以下顺序判断：

1. 用户在处理的对象属于哪一层：Issue、Roadmap、Task Registry、Runtime、Skill Governance、Installed Skills、Orchestra Service。
2. 用户当前动作是什么：创建、规划、核对、修复、治理、同步、提交、整合、收口、调试。
3. 如果多个 skill 都像能接，优先进入对象更窄、动作更确定的 skill。

### 2.2 高层规划优先于低层执行建议

- "当前版本/下一个版本该做什么"属于 roadmap 层。
- "已有现场里先回哪个 flow / task"属于 task 层；worktree 只用于描述该现场当前由哪个物理目录承载。

### 2.3 Runtime 修复晚于 Registry 审计

- 只要问题本质是 `roadmap <-> task`、task registry、task 数据质量，走 `vibe-task`。
- 只要问题本质是 `task <-> flow`、worktree runtime、stale binding，走 `vibe-check`。
- 其中 `vibe-task` 是 task-centered audit，`vibe-check` 是 runtime / recovery audit。
- 此处的 `worktree runtime` 只表示物理目录承载与兼容期 hint，不把 `worktree` 视为 flow 主体。

### 2.4 Skill 治理与 Skills 管理必须分开

- "怎么创建/审查 repo 内的 `skills/vibe-*`"走 `vibe-skill-audit`。
- "装了哪些 skills、要不要清理、怎么同步到 IDE"走 `vibe-skills-manager`。

## 3. 核心 Skill 触发矩阵

| Skill | 职责层 | 适用场景 | 冲突分流 (Do NOT use if...) | 自然语言触发词 |
|---|---|---|---|---|
| `vibe-instruction` | Meta Guide | 快速了解项目结构、可用命令和标准开发工作流 | 已经在处理具体开发任务或调试 serve | "怎么用", "项目导览", "vibe 介绍", "instruction" |
| `vibe-onboard` | System Setup | 安装后的引导、依赖检查、密钥配置、核心功能介绍 | 项目已就绪且处于正常开发周期 | "onboard", "安装后引导", "setup", "开始使用" |
| `vibe-project-check` | Project Health | 检查项目配置（labels, keys, gitignore）是否完整正确 | 已经在做常规 flow/task 审计或 runtime 修复 | "project-check", "项目配置检查", "检查 label", "验证配置" |
| `vibe-orchestra` | Orchestra Governance | Issue pool 管理、RFC/blocked issues、版本规划 | 视角是监控 orchestra service 运行状态、FailedGate | "Orchestra 治理", "RFC issues", "blocked issues", "版本规划" |
| `vibe-debug-serve` | Service Debug | 监控 orchestra service 状态、检查 FailedGate、调试 heartbeat/dispatch | issue pool 治理建议、roadmap 规划 | "检查 serve status", "orchestra 健康状态", "FailedGate 检查", "debug serve" |
| `vibe-issue` | Issue intake | 用户要创建、补全、查重、润色、落 GitHub issue | 已经在讨论版本归类、task 映射、runtime 修复 | "创建 issue", "提 issue", "查重", "补 issue 模板" |
| `vibe-roadmap` | Roadmap planning | 用户要排版本、定目标、做 backlog triage、决定 issue 放哪版 | 只是在看当前 flow 该去哪，或修 runtime/registry | "版本规划", "下一个版本做什么", "这个 issue 放哪一版" |
| `vibe-new` | Flow transition | 用户要开始新任务、确认目标 issue、创建/注册 flow、绑定 issue 并创建 PR draft | 已经进入实现、跨 worktree 调度 | "开始新任务", "进入新 flow", "切主 issue", "vibe-new" |
| `vibe-continue` | Execution resume | 用户要恢复已有分支的工作、重新加载当前 flow 上下文 | 创建新 issue、创建新 branch、新任务启动 | "恢复执行", "继续工作", "加载上下文", "vibe-continue" |
| `vibe-commit` | Commit & PR | 整理变更、创建提交分组、创建 PR draft、处理 pre-commit | 要做 PR 整合决策、合并 PR 或 final closeout | "提交代码", "发 PR", "create PR", "commit" |
| `vibe-integrate` | PR Convergence | 评估 PR 状态、检查 CI/Review 阻塞、确认合并条件 | 整理提交分组、创建 PR 或 PR 后的清理 | "integrate", "检查 CI", "可以合并吗", "PR 状态" |
| `vibe-done` | Flow Closure | PR 合并后的终态收口：关 issue、删分支、清理资源 | 还在做业务代码开发或 PR 整合 | "任务完成", "收口", "done", "清理现场" |
| `vibe-closeout` | Service Cleanup | 由 manager 触发的自动化现场清理、执行 cleanup 指令 | 处于人机协作的终态收口周期 | "vibe-closeout", "cleanup flow", "清理 terminal flow" |
| `vibe-task` | RFC & Blocked issues | 用户要检查 RFC issues、blocked issues、问题 issue 状态 | 项目级版本规划、Issue intake、runtime stale repair、正常运行 issues | "检查 RFC issues", "看 blocked issues", "问题 issue 检查" |
| `vibe-check` | Runtime / task-flow binding | 用户要解释或修复 `task <-> flow` / worktree runtime 不一致 | roadmap 归类、task registry 审计、Issue 治理 | "binding 不对", "runtime stale", "check runtime", "当前 worktree 状态不对" |
| `vibe-review-code` | Code review | 用户要对 source changes 做 pre-PR 审查、复核 PR review feedback、检查实现风险与测试覆盖 | docs-only review、standards/changelog 审查 | "review 这段代码", "代码审查", "PR 前 review", "根据 review feedback 修代码" |
| `vibe-review-docs` | Documentation review | 用户要审查 docs/、入口文件、standards、changelog，或检查概念漂移与文档治理问题 | source-code implementation review | "review docs", "文档审查", "审一下 CLAUDE.md", "检查标准文档" |
| `vibe-team-review` | Team Collaboration | 多 agent 协作审查：PR、架构决策、复杂代码变动 | 单 agent 可胜任的小型审查或纯文档审查 | "team review", "团队审查", "复杂 PR 评审" |
| `vibe-redundancy-audit` | Code Quality | 查找冗余业务逻辑、重复模式、迁移残留、过度设计 | 正常的业务代码评审或 bug 修复 | "redundancy audit", "重复代码", "冗余逻辑", "清理旧路径" |
| `vibe-rules` | Rules Governance | 检查 rules 冲突、重复、清理过时规则 | 编写新技能或进行 flow 治理 | "vibe-rules", "规则冲突", "清理 rules", "rules check" |
| `vibe-skill-audit` | Repo-local skill governance | 用户要创建、更新、审查、收紧 repo 内 `skills/vibe-*` 文案与边界 | 已安装 skills 的 inventory、同步、清理 | "创建 skill", "审查 skill", "skill 文案", "自动匹配语义", "vibe-skill" |
| `vibe-skills-manager` | Installed skills management | 用户要查看已安装 skills、做同步、清理、推荐、跨 IDE 管理 | repo 内 skill 文案治理、skill 审查、skill 边界设计 | "skills 乱了", "同步 skills", "清理 skills", "推荐 skills", "/vibe-skills-manager" |
| `vibe-save` | Session Handoff | 保存当前会话上下文、写入 handoff、记录下一步 | 正常开发过程中的常规 commit 或 PR 提交 | "save session", "保存进度", "handoff append", "vibe-save" |

## 4. 相邻 Skill 的冲突裁决

### 4.1 `vibe-issue` vs `vibe-roadmap`

- 还没形成正式 GitHub issue，或在补模板/查重：优先 `vibe-issue`。
- issue 已存在，正在讨论它属于当前版本、下版本还是延期：优先 `vibe-roadmap`。

### 4.2 `vibe-roadmap` vs `vibe-task`

- 用户问"项目层面下一步做什么""当前版本该装什么内容" | 尚未涉及具体 issue 归档 | "版本规划", "下一个版本做什么", "这个 issue 放哪一版" |
- 用户问"有哪些 RFC issues 需要讨论""有哪些 blocked issues 需要解除" | 项目级版本规划 | "检查 RFC issues", "看 blocked issues", "问题 issue 检查" |

### 4.3 `vibe-task` vs `vibe-check`

- 问题发生在共享任务事实、registry 数据、`roadmap <-> task` 对应关系：优先 `vibe-task`。
- 问题发生在现场 runtime、worktree 缺失、binding stale、`task <-> flow` 投影：优先 `vibe-check`。

### 4.4 `vibe-skill-audit` vs `vibe-skills-manager`

- 目标是 repo 内 `skills/vibe-*` 的创建、审查、收敛：优先 `vibe-skill-audit`。
- 目标是已安装 skill 的同步、inventory、推荐、删除：优先 `vibe-skills-manager`。

### 4.5 `vibe-orchestra` vs `vibe-debug-serve`

- 视角是"orchestra service 治理""RFC issues""blocked issues""版本规划"：优先 `vibe-orchestra`。
- 视角是"监控 orchestra service 运行状态""FailedGate 检查""serve status"：优先 `vibe-debug-serve`。

### 4.6 `vibe-review-code` vs `vibe-review-docs`

- 审查对象是 source code diff、实现正确性、调用影响、测试回归与 review feedback：优先 `vibe-review-code`。
- 审查对象是 docs、standards、entry docs、changelog、术语与概念漂移：优先 `vibe-review-docs`。

### 4.7 `vibe-commit` vs `vibe-integrate` vs `vibe-done`

- 视角是"整理当前改动并创建/更新 PR"：优先 `vibe-commit`。
- 视角是"检查 PR 是否 ready for merge"（CI/Review 状态）：优先 `vibe-integrate`。
- 视角是"PR 已合并，需要清理现场"：优先 `vibe-done`。

## 5. Description 写法要求

每个高频 Vibe skill 的 `description` 必须满足：

1. 以 `Use when...` 开头。
2. 只写触发条件，不写完整流程。
3. 同时覆盖：
   - 用户的目标动作
   - 邻近冲突场景的排除条件
   - 2 到 5 个自然语言触发词
4. 不把"审计后自动修复""智能分析全部完成"写成默认承诺。
5. 高风险路由措辞必须避免把 `flow` 直接说成 `worktree`；如果提到 `worktree`，只能用于说明"当前由哪个物理目录承载该 flow/现场"，不能写成"进入哪个 worktree""继续当前 worktree 绑定的 task"这类把物理容器当成运行时主体的表述。
6. 若提到 task 与 issue 的主从关系，必须区分 `issue_refs` 与 `primary_issue_ref`；不能把任意 `issue_ref` 默认写成 `task issue`。

## 6. 文档同步规则

- 新增或修改核心 Vibe skill 的 `description` 时，若影响到相邻 skill 的分流，必须同步审阅本文档。
- 若先修改了本文档中的触发矩阵，相关 `skills/*/SKILL.md` 与 `.agent/workflows/*.md` 必须在同一变更线内同步。
- 若某个新 skill 会与现有 skill 竞争入口，必须先在本文档中补冲突裁决规则，再落 skill 文案。

## 7. 变更检查清单

修改核心 Vibe skill 的触发语义时，逐项确认：

1. 是否先明确对象层级，再定义动作类型？
2. `description` 是否只写触发条件，没有偷塞完整流程摘要？
3. 是否为真实用户会说的话提供了自然语言触发词？
4. 是否写清了最相邻 skill 的排除边界？
5. 如果新增短别名或 slash 入口，是否保持为同一 skill 的薄入口，而不是第二套业务逻辑？

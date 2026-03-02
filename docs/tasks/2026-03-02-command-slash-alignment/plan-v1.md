---
task_id: "2026-03-02-command-slash-alignment"
document_type: task-plan
title: "Command vs Slash Alignment Plan"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
status: planning
---

# Command vs Slash Alignment Plan

## 1. 背景与理念 (Background & Idea)

目前由于双路开发并行打桩，导致出现以下两种“割裂场景”：
1. **Slash 滥用了超能力** (例如直接利用文本替换或正则来篡改 `registry.json`)：这不仅容易导致 JSON 损坏、产生死锁/幻觉字段，同时与 Vibe 体系追求的确定性控制极不匹配。JSON 数据应采用确定性的 Shell API (`jq`) 进行交互，由 Shell 保障数据的完整型与事务安全。
2. **Shell 残留了老一派流程** (例如要求人类敲击 `vibe flow review` -> `vibe flow pr`): 这种无 AI 交互、呆板的控制条实际上剥离了我们在“提交信息智能合并、代码风格自动审查、智能撰写 PR Description”上的想象力。Shell 应退化为最朴素的武器端，交由 Slash 这个高级智囊前端来握持。

故我们应当以 **「控制层：Slash 做调度端 / Vibe Agent」** 以及 **「数据访问及强校验：Shell API 做服务层 / Vibe Core」** 重新设计现有的重叠指令。

## 2. 改造方向一：把 Shell API 改造成 Slash 的微服务
这一步用于拔除部分 Slash command 里直接操作文件替换带来的痛点（尤其是数据同步阶段）。

### 当前痛点
- `/vibe-new`、`/vibe-save`、`/vibe-continue`、`/vibe-done` 在其指令规约里，几乎全是要求 AI 自己靠匹配正则或重写文件的方式改变项目状态表。

### Shell 新功能拓展计划 (CRUD 接口化)
需要赋予 `bin/vibe` 一些底层状态机接口供 AI 代理调用：
- **`vibe task set-status <task-id> <status>`**: 底层 `jq` 专用更新指令。例如从 `in_progress` -> `completed`。Slash 只需要抛弃手写替换的方式，通过这行直接无痛完结大盘。
- **`vibe task push-worktree <task-id> <worktree_dir> <branch>`**: 给 `worktrees.json` 加/改挂载点。
- **`vibe check json <filepath>`**: 作为门卫（Gate），供 AI 自行检测它刚才可能修改的某些数据结构是否合法。

**改造后 Slash 的收益：**
- AI 不需要再面对超长的长文本 JSON 并理解其逻辑关联。只要知道执行 `vibe task set-...`，即可优雅控制流转。

## 3. 改造方向二：使用 Slash 命令整合孤立的 Shell 工作流
这一步用于隐藏难用的生涩命令行、拓展 AI 功能：

### 待改造项目：
1. **`/vibe-check` (取代裸奔 `vibe check`)**
   - **原本**: `vibe check` 负责校验依赖工具 `jq`, `gh`，`vibe-check` Agent 技能负责核对 SOUL 灵魂规约是否前后对冲。
   - **对齐**: `/vibe-check` 开场先悄无声息地通过执行 `vibe check` 验证终端是否满足生存环境，再展开 `SOUL.md` 进行抽象审理。
   - **拓展**: 一次 Slash 命令，涵盖环境检测（Shell级）和逻辑/规约审计（Slash逻辑层）。

2. **`/vibe-skills` (取代 `vibe skills sync/check`)**
   - **对齐**: 以后 Agent 管理体系时，必须使用底层的同步引擎 `vibe skills sync` 而不是凭空想象哪些该存在。

3. **创建新项目的一键启动流 `/vibe-new`**
   - **对齐前**: 人类得先打开终端打上 `vibe flow start feature` 退回，然后切回侧边栏敲 `/vibe-new feature`。
   - **未来拓展**: 当不处在工作区时，呼叫 `/vibe-new xxx` 时，Agent 会利用超能力优先为您无感执行 `vibe flow start xxx` 命令去创建并拉起工作分支，再引导您切入环境进行需求讨论。 

## 4. 实施阶段（Execution Phases，本期仅设卡为记录）

本大版计划（即建立“壳(Shell)-肉(Slash)分离的 MVC 模型”）暂不实施在当前阶段流。留有记录：

- **Phase A**: 开发 `lib/task.sh` 提供底层的 `jq`-based 写入修改指令，并测试数据注入。（Task JSON CRUD）
- **Phase B**: 重写那四大 Slash 生命周期指令（`/vibe-save/continue/done/new`），用 Phase A 提供的新命令替换它旧文档里的正则手写替换行为。
- **Phase C**: 将目前仍挂在 `vibe flow`（如 `start / pr`）中的所有工作流，作为“底层武器包”封装进入 `/vibe-orchestrator` 控制流程下的标准 Agent Slash 触发流程中。致此完全实现零 Terminal 操作流（全程依赖 AI 对话控制大局）。

---
**当前行动指南：**本 Plan 正式写入任务表进行留存，等待后续单独启动。

---
name: vibe-roadmap
description: Use when user wants to manage roadmap, version goals, issue classification, or says "vibe roadmap", "/roadmap", "版本规划", "下一个版本做什么". **RECOMMENDED: Run as subagent to save tokens.**
---

# /vibe-roadmap - 智能调度器

维护 mirrored GitHub Project items，管理 milestone / 兼容性的版本目标，对 roadmap item 的 `type` 和规划窗口进行调度。

**核心原则:** CLI 负责读写数据，skill 负责调度决策。

**Announce at start:** "我正在使用 vibe-roadmap 技能来管理版本路线图。"

## Trigger Examples

- `vibe roadmap`
- `/vibe-roadmap`
- `/roadmap`
- `版本规划`
- `下一个版本做什么`
- `管理许愿池`
- `版本目标`

## Hard Boundary

- 必须先运行 `bin/vibe roadmap` 相关命令
- 不得直接修改 `registry.json` 底层数据
- 必须通过 Shell API 写入数据
- 调度器无法判断优先级时，必须要求人类讨论

## Workflow

### Step 1: 检查版本目标

运行 `bin/vibe roadmap status` 获取当前版本目标状态：

- 当前 milestone / 规划窗口是什么
- 有哪些 repo issue 等待进入 GitHub Project / roadmap
- 各个 roadmap item `type` 和状态下有多少项

### Step 2: 调度决策

根据当前状态做出决策：

**场景 A: 没有版本目标**
- 提示用户定义版本目标
- 展示许愿池中的 Issue 供选择
- 要求人类讨论确定目标

**场景 B: 有版本目标但有新 Issue**
- 对新 repo issue 对应的 roadmap item 进行分类：P0/当前版本/下一个版本/延期/拒绝
- 按优先级排序

**场景 C: 版本结束**
- 确认下一版本目标
- 重新评估待分类 Issue

### Step 3: 输出状态

输出当前路线图状态：

```text
## 当前版本: v2.0

### P0 (紧急)
- #36: GitHub Projects 整合

### 当前版本
- #34: Issue 同步
- #35: save 自动关联

### 下一个版本
- 待定

### 延期
- 待讨论
```

### Step 4: 响应 vibe-new 调用

当 `/vibe-new` 触发时：

- 检查是否有版本目标
- 无目标 → 要求人类讨论确定
- 有目标 → 提示当前规划窗口有哪些 roadmap item 可供继续拆成 task
- 有目标 → 提示当前规划窗口有哪些 roadmap item 可供继续拆成 execution records
- 是否拆 task、拆几个、绑定到哪个 flow，由上层 skill / agent 决定

## Issue 分类状态

| 状态 | 含义 | 行为 |
|------|------|------|
| P0 | 阻断性问题，需要立即处理 | 优先进入规划讨论，不直接等于 branch 当前任务 |
| 当前版本 | 明确纳入当前规划窗口 | 可被后续 skill 拆成 task，但不等于 branch 当前任务 |
| 下一个版本 | 有更优先的事项，但要做 | 本版本结束后自动成为下版本目标 |
| 延期 | 待决定，暂时不做 | 等下次讨论 |
| 拒绝 | 不做 | 关闭 |

## Failure Handling

如果 `bin/vibe roadmap` 失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法进行路线图管理
- 不要自行 fallback 到直接修改 JSON

## Terminology Contract

- `版本目标`: 对 milestone 的兼容性文本表达
- `repo issue`: 需求来源层对象
- `Roadmap Item`: mirrored GitHub Project item
- `feature` / `task` / `bug`: roadmap item 的 `type`
- `Task`: execution record，不是另一套产品规划对象
- `Flow`: task 的运行时容器，通常绑定一个 worktree / branch

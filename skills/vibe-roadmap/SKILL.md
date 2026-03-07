---
name: vibe-roadmap
description: Use when user wants to manage roadmap, version goals, issue classification, or says "vibe roadmap", "/roadmap", "版本规划", "下一个版本做什么". **RECOMMENDED: Run as subagent to save tokens.**
---

# /vibe-roadmap - 智能调度器

维护全景路线图，管理版本目标，对 Issue 进行分类，决定下一个版本做什么。

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

- 当前版本目标是什么
- 有哪些 Issue 等待分类
- 各个分类下有多少 Issue

### Step 2: 调度决策

根据当前状态做出决策：

**场景 A: 没有版本目标**
- 提示用户定义版本目标
- 展示许愿池中的 Issue 供选择
- 要求人类讨论确定目标

**场景 B: 有版本目标但有新 Issue**
- 对新 Issue 进行分类：P0/当前版本/下一个版本/延期/拒绝
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
- 有目标 → 从当前版本 backlog 中分配最高优先级任务

## Issue 分类状态

| 状态 | 含义 | 行为 |
|------|------|------|
| P0 | 阻断性问题，需要立即处理 | 不受版本约束，调度器立即分配 |
| 当前版本 | 明确纳入本版本 | 按优先级分配给 vibe-new |
| 下一个版本 | 有更优先的事项，但要做 | 本版本结束后自动成为下版本目标 |
| 延期 | 待决定，暂时不做 | 等下次讨论 |
| 拒绝 | 不做 | 关闭 |

## Failure Handling

如果 `bin/vibe roadmap` 失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法进行路线图管理
- 不要自行 fallback 到直接修改 JSON

## Terminology Contract

- `版本目标`: 当前版本要完成的目标
- `许愿池`: GitHub Issues (需求池)
- `Issue`: 心愿，不是具体任务
- `Task`: 具体的执行单元，最小单位

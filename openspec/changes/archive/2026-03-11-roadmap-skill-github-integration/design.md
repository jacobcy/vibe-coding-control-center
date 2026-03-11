## Context

当前 Vibe Center 采用三层架构（Supervisor/Skills/Shell），缺少"智能调度器"能力：
- GitHub Issue 是"许愿池"，但不污染代码
- vibe task list 只有任务基础功能，没有调度能力
- 没有版本目标概念，不知道 v2/v3 做到什么程度

## Goals / Non-Goals

**Goals:**
1. 创建智能调度器（vibe-roadmap），维护版本目标和 Issue 分类
2. 每次 `/vibe-new` 发动时，在任务编排器之前先调用调度器
3. 用户指定具体任务 → 直接交给编排器
4. 用户未指定 → 调度器分配优先任务
5. 版本结束时自动管理：确认下版本目标、分类未决定 Issue

**Non-Goals:**
- 不替代本地 `vibe task` 执行流
- Issue（许愿）和 Task（执行单元）是多对多关系，不强制绑定
- 不在技能层直接改写底层 JSON 真源（必须走 Shell API）

## Decisions

### D1: Issue 分类状态机

**Alternatives considered:**
- A: Now/Next/Later/Blocked/Exploration - 静态分类，无版本概念
- B: 纯标签化（versions: [v2.0, v2.1]）- 无调度逻辑
- C: 版本目标驱动 + 5 种分类 - 有明确版本周期

**Chosen:** C - 更符合"调度器自检本周期的任务是什么"的逻辑

| 状态 | 含义 | 行为 |
|------|------|------|
| P0 (紧急) | 阻断性问题，需要立即处理 | 不受版本约束，调度器立即分配 |
| 当前版本 | 明确纳入本版本 | 按优先级分配给 vibe-new |
| 下一个版本 | 有更优先的事项，但要做 | 本版本结束后自动成为下版本目标 |
| 延期 | 待决定，暂时不做 | 等下次讨论 |
| 拒绝 | 不做 | 关闭 |

### D2: 调度器触发机制

**Chosen:** 每次 `/vibe-new` 发动时触发

```
/vibe-new <feature>
    │
    ├── 指定具体任务？ ──Yes──▶ 直接交给编排器
    │
    └── No ──▶ 调用调度器
                  │
                  ├── 有版本目标？ ──No──▶ 要求人类讨论确定目标
                  │
                  └── Yes ──▶ 分配优先任务 → 交给编排器
```

### D3: Issue ↔ Task 多对多关系

**Chosen:** 标签关联，不强制绑定

- Issue 只是"心愿"，可以关联 0-N 个 Task
- Task 可以解决 0-N 个 Issue 的问题
- Task 是最小执行单元，Issue 不是

### D4: 版本号规则

**Chosen:** 简化版本号
- 大功能 +0.1
- 小功能 +0.01
- 不需要严格定义，区分 major/minor 即可

## Risks / Trade-offs

- **Risk:** 调度器无法判断优先级 → **Mitigation:** 要求人类讨论，不自行猜测
- **Risk:** 版本目标频繁变化 → **Mitigation:** 版本结束时才重新确认目标
- **Risk:** GitHub API 限流 → **Mitigation:** 启动前检查 `gh auth status`

## Migration Plan

1. Phase 1: 创建 Roadmap Skill + 注册
2. Phase 2: 实现调度器核心逻辑（版本目标 + Issue 分类）
3. Phase 3: 集成到 /vibe-new 流程
4. Phase 4: GitHub Issue 同步（许愿池）
5. Phase 5: Changelog 自动生成

## Open Questions

- P0 紧急修复是否需要单独的工作流（不走 vibe-new）？
- "延期"和"下一个版本"的区分是否足够清晰？

name: "vibe:issue"
description: Skill-backed workflow that routes repo issue intake to the vibe-issue skill before roadmap planning.
---

# vibe:issue

**指令**：优先运行 `/vibe-issue create "<标题>"` 开启治理引导；若标题未定，可先运行 `/vibe-issue` 进入引导。

## 定位

- `vibe:issue` 是一个 `skill-backed workflow`。
- 它只负责 issue intake 入口，不直接承载模板检查、查重和创建细节。
- `repo issue` 是来源层对象，不是本地执行 task，也不是 flow runtime 的主语。

## Steps

1. 回复用户：`我会先把当前请求解释为 repo issue intake，再委托 vibe-issue skill 处理查重、模板和创建。`
2. 委托 `skills/vibe-issue/SKILL.md` 处理：
   - Template Gate
   - Duplication Gate
   - Roadmap 侧前置检查
   - `gh issue create` 编排
3. 返回创建结果或阻塞说明。

## Boundary

- workflow 不承载 issue 查重、模板匹配或标签策略细节。
- 不得把 issue intake 入口写成本地 task 创建入口。

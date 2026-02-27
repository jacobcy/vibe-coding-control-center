# PRD: Context Scoping - 执行计划上下文圈定

## 1. Overview

Context Scoping 是 Execution Plan 的**强制字段要求**，要求 AI 在执行前明确列出"需要读取的文件"，防止乱读代码库导致幻觉和胡乱修改。

## 2. Goals

- **强制圈定**：Execution Plan 必须包含上下文圈定，否则阻断执行
- **最小化要求**：只需要"需要读取的文件"列表
- **格式灵活**：支持多种 Markdown 标题形式

## 3. Non-Goals

- **不限制实际读取**：不强制检查 AI 实际读取的文件是否在列表内
- **不要求禁止列表**：不需要"禁止读取的文件"列表
- **不要求改动预估**：不需要"预计改动范围"

## 4. Check Logic

**Plan Gate 检查流程：**

```
Plan Gate 读取 Execution Plan
    │
    ├── 扫描文件内容
    │
    ├── 查找上下文标题（任一匹配）：
    │     - ## Context
    │     - ## 上下文
    │     - ## 需要读取的文件
    │     - ## 相关文件
    │     - ## 上下文圈定
    │
    ├── 找到标题 → 检查下方是否有文件列表
    │     │
    │     ├── 有列表 → ✅ 通过
    │     └── 无列表 → 🟡 警告（标题存在但无内容）
    │
    └── 未找到标题 → 🔴 阻断
          │
          └── "Execution Plan 缺少上下文圈定，请添加 ## Context 部分"
```

**列表识别规则：**
- Markdown 列表项：`- path/to/file` 或 `* path/to/file`
- 至少包含 1 个文件路径

## 5. Format Example

**有效的上下文圈定：**

```markdown
## Context

- lib/flow.sh - 流程控制主逻辑
- lib/utils.sh - 工具函数
- bin/vibe - CLI 入口

## 任务详情
...
```

或中文：

```markdown
## 上下文

- lib/flow.sh
- lib/utils.sh
- bin/vibe

## 任务详情
...
```

## 6. Error Message

**阻断时输出：**

```markdown
🚫 Plan Gate 阻断：Execution Plan 缺少上下文圈定

文件：{execution_plan_path}

请在 Execution Plan 中添加上下文圈定部分，格式如下：

## Context

- path/to/file1 - 简要说明
- path/to/file2 - 简要说明

这能帮助 AI 聚焦相关文件，避免幻觉和无关修改。
```

## 7. Implementation Approach

| 组件 | 职责 | 文件 |
|------|------|------|
| Skill | 检查逻辑 | 增强 `skills/vibe-orchestrator/SKILL.md` |
| 模板 | 引导格式 | `docs/templates/execution-plan-template.md`（可选） |

**调用关系：**
```
vibe-orchestrator (Plan Gate)
    │
    ├── 读取 Execution Plan（通过 plan-gate.sh）
    │
    └── 检查上下文圈定
          │
          ├── 存在 → 通过，进入下一阶段
          └── 不存在 → 阻断，输出错误消息
```

## 8. Success Criteria

| 场景 | 预期行为 |
|------|----------|
| 有 Context 标题 + 文件列表 | 通过 |
| 有中文标题 + 文件列表 | 通过 |
| 有标题但无列表 | 警告，允许通过 |
| 无上下文圈定 | 阻断，输出引导 |

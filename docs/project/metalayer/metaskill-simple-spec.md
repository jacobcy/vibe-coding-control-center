---
document_type: spec
title: Meta Layer 极简设计约束
status: draft
scope: meta-layer-constraints
author: Claude Sonnet
related_docs:
  - README.md
  - metalayer-prd.md
---

# Meta Layer 极简设计约束

本文档定义 Meta Layer 的强制设计约束，确保系统保持极简。

> **核心原则**：先让系统"有记忆"，再考虑"如何聪明使用记忆"

## 1. 设计原则（必须遵守）

1. 不做智能判断
2. 不做复杂筛选
3. 不做训练
4. 一切保持可解释、可 debug

## 2. 系统目标

实现一个最小 Meta Layer：

```
记录 → 总结 → 注入（少量）
```

## 3. Skill 系统

### 3.1 数据结构

```json
{
  "id": "uuid",
  "content": "调用 API 前必须初始化 client",
  "created_at": 1710000000
}
```

### 3.2 存储

- 路径：`~/.meta-layer/skills.json`
- 数量限制：最多 50 条
- 超出策略：删除最旧的

### 3.3 去重规则

- 如果 content 完全相同 → 不新增
- **不做** embedding
- **不做** 语义判断

## 4. Skill 注入策略

**唯一规则**：`skills[-3:]`（最近 3 条）

**注入格式**：

```
[LEARNED_SKILLS]
- xxx
- xxx
- xxx
```

**禁止**：

- 关键词匹配
- 分类
- 相关性计算

## 5. Skill 生成

### 5.1 触发条件

task 结束时

### 5.2 输入格式

```
以下是执行过程：

事件：
- tool_failed: ...
- user_corrected: ...
- test_failed: ...

请总结一条经验（必须具体、可执行，一句话）
```

### 5.3 输出要求（强约束）

必须满足：

- 具体（不能抽象）
- 可执行（能指导行为）
- 单条（只允许一句）

**禁止输出**：

- "要注意错误"
- "需要优化代码"

### 5.4 写入规则

```python
if skill 不为空 AND 不重复:
    append
```

### 5.5 过滤函数

```python
def is_valid_skill(skill: str, existing: list[str]) -> bool:
    s = skill.strip()

    if len(s) < 10: return False
    if any(bad in s.lower() for bad in ["注意", "优化", "检查", "确保", "问题"]):
        return False
    if len(set(s)) < len(s) * 0.5: return False  # 去掉重复字符垃圾
    if s in existing: return False
    if s.endswith("..."): return False
    if "必须" not in s and "需要" not in s: return False  # 强制可执行语气

    return True
```

## 6. Event 系统

### 6.1 支持事件

- `tool_failed`
- `tool_success`
- `test_failed`
- `test_passed`
- `user_corrected`

### 6.2 存储

```json
{
  "events": []
}
```

**不做**：分析、分类

## 7. Trace 系统

### 7.1 结构

```json
{
  "task_id": "",
  "events": [],
  "messages": []
}
```

### 7.2 用途

**只用于**：生成 skill

**不做**：统计、打分、replay

## 8. Proxy 行为

### 输入流程

1. 接收请求
2. 注入 `skills[-3:]`
3. 转发给 LLM

### 输出流程

1. 返回结果
2. 记录 messages

## 9. Harness 集成

**只做三件事**：

1. tool 后上报：`"type": "tool_failed"`
2. test 后上报：`"type": "test_failed"`
3. 用户修改上报：`"type": "user_corrected"`

**不允许更多逻辑**

## 10. CLI

```bash
meta-layer start
meta-layer skills
meta-layer clear
```

## 11. 明确不做

**禁止**：

- embedding
- 小模型
- LoRA
- skill 分类
- 智能选择

## 12. 成功标准

| 时间 | 预期状态 |
|------|---------|
| Day 1 | `skills = []` |
| Day 3 | `["调用 API 前必须初始化 client", "路径必须使用绝对路径"]` |
| Day 7 | 明显减少重复错误 |

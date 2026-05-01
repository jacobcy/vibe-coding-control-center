# Team 多代理协作指南

> 本文档基于 2026-05-01 的 Team 功能实验总结，记录如何正确使用 Claude Code 的 Team 功能。

## 核心原则

### 1. 不信任单一 teammate 的结论

**反面案例**：deep-reviewer 声称 "已合并，无漏洞"，实际上：
- PR 全是 draft 状态，根本没有合并
- 安全保护机制存在根本性缺陷

**正确做法**：
- 每个结论必须有证据支撑（命令输出、文件引用）
- 关键结论需要交叉验证

### 2. 同一问题，分工协作，交叉验证

**错误模式**：
```
PR #1 → teammate A 独立审查 → 报告完成
PR #2 → teammate B 独立审查 → 报告完成
PR #3 → teammate C 独立审查 → 报告完成
         ↓
      简单汇总（不可靠）
```

**正确模式**：
```
                    ┌─ 背景调查员 — 收集上下文
                    │
同一 PR ──→ 分工 ──┼─ 主审查员 —— 架构/代码审查
                    │
                    └─ 红队审查员 — 寻找绕过方式
                              ↓
                         交叉验证
                              ↓
                         差异上报 team-lead
                              ↓
                         综合判断
```

### 3. 注入领域知识

Teammate 默认缺乏项目上下文，需要在 prompt 中注入：

```python
prompt = """
**项目特定知识**：
- 分支命名规范：task/issue-*, dev/issue-*
- Worktree 路径格式：.worktrees/<branch>
- 安全边界：不同 tmux session 不能操作同一个 worktree

**审查重点**：
1. worktree_path 从哪里来？是否可靠？
2. tmux session 识别是否可被伪造？
3. takeover 是否有授权检查？
"""
```

---

## Team 架构设计

### PR 审核 Team（推荐）

适用于：复杂 PR 或涉及核心组件修改的 PR

```yaml
Team: pr-review-team

Roles:
  team-lead:
    agentType: general-purpose
    model: sonnet
    职责:
      - 判断 PR 复杂度
      - 分配任务给调研员
      - 综合判断，得出结论
      - 处理调研员之间的差异

  context-researcher:
    agentType: Explore
    model: haiku
    职责:
      - 收集项目背景
      - 收集 PR 相关领域知识
      - 检查是否有类似实现/替代方案
      - 判断 PR 是否过时

  code-analyst:
    agentType: Explore
    model: haiku
    职责:
      - 分析 PR 代码框架
      - 检查是否符合项目架构
      - 识别技术债
      - 判断是否造成新技术债

  security-reviewer:
    agentType: security-reviewer
    model: sonnet  # 或 opus（关键 PR）
    职责:
      - 安全漏洞审查
      - 寻找绕过保护机制的方法
      - 验证安全声明的真实性

  codex-expert:
    model: gpt-5.4  # 通过 Bash 调用
    职责:
      - 深度安全审查（关键 PR）
      - 复杂问题的根因分析
    注意:
      - 不能通过 Agent tool 直接 spawn
      - 必须通过 codex-companion.mjs 脚本调用
```

### 工作流程

```
1. Team-lead 接收 PR → 判断复杂度
   ├─ 简单 PR（<50行，无安全影响）→ 单人审查
   └─ 复杂 PR → 分工协作

2. 调研阶段（并行）：
   ├─ context-researcher: 收集背景 → 输出背景报告
   └─ code-analyst: 分析代码 → 输出代码分析报告

3. 汇总阶段：
   └─ Team-lead 汇总两份报告 → 提炼关键问题

4. 专家审查：
   └─ security-reviewer: 针对关键问题做深度审查
      ├─ 尝试绕过保护机制
      └─ 验证代码实现的正确性

5. Codex 确认（关键 PR）：
   └─ codex-expert: 深度追踪，交叉验证

6. 综合判断：
   └─ Team-lead 整合所有结论 → 最终决策
```

---

## 防幻觉机制

### 验证规则

| 声称 | 必须提供证据 |
|------|-------------|
| "已合并" | `gh pr view <number>` 输出 |
| "CI 通过" | `gh pr checks <number>` 输出 |
| "无漏洞" | 列出检查了哪些文件和函数 |
| "代码符合架构" | 引用架构文档 + 代码位置 |

### 幻觉检测

```python
# 在 prompt 中添加
"""
**验证要求**：
- 每个结论必须有证据支撑
- 不能假设，必须验证
- 发现不确定的信息立即上报
"""
```

---

## Codex 集成

### 限制

`Agent` tool 的 `model` 参数只支持 Claude 模型（sonnet/opus/haiku），不支持 Codex 模型。

### 解决方案

```bash
# 方案：通过 codex-companion 脚本调用
node ~/.claude/plugins/cache/openai-codex/codex/1.0.3/scripts/codex-companion.mjs \
  task --model gpt-5.4 "审查任务描述"

# 或直接使用 codex CLI
codex --model gpt-5.4 "审查任务描述"
```

### 适用场景

- 关键 PR 的安全审查
- 复杂问题的根因分析
- 交叉验证其他 teammate 的结论

---

## Agent 定义参考

### 创建新 Agent

在 `~/.claude/agents/` 目录下创建 `<agent-name>.md`：

```markdown
---
name: pr-security-reviewer
description: |
  PR 安全审查专家，负责深度审查 PR 的安全性。
  特别适用于：安全修复 PR、涉及认证/授权的 PR、涉及数据处理的 PR。
model: sonnet
tools: Read, Grep, Glob, Bash
---

你是一个安全审查专家，负责深度审查 PR 的安全性。

**审查流程**：

1. **理解保护机制**：
   - 这个 PR 试图保护什么？
   - 保护机制的设计意图是什么？

2. **寻找绕过方式**（红队思维）：
   - 如何绕过这个保护机制？
   - 有哪些边界条件被忽略？
   - 非预期用户能否触发？

3. **验证实现正确性**：
   - 代码实现是否匹配设计意图？
   - 是否有遗漏的路径？
   - 错误处理是否完整？

4. **检查审计追踪**：
   - 操作是否有日志？
   - 日志是否可靠？
   - 日志能否被篡改？

**输出格式**：

### 安全评估

| 项目 | 结果 |
|------|------|
| 保护机制有效性 | 有效/可绕过 |
| 绕过方式 | 列举发现 |
| 实现正确性 | 正确/有问题 |
| 审计完整性 | 完整/缺失 |

### 发现的问题

[具体问题列表]

### 建议

[修复建议]
```

---

## 最佳实践

### 1. 任务分配

- **背景调查** → haiku（快速、便宜）
- **代码分析** → haiku（快速、便宜）
- **安全审查** → sonnet/opus（需要深度推理）
- **交叉验证** → Codex（独立视角）

### 2. 结果汇总

```markdown
## Team 审查汇总

### 调研员 A 发现
- [发现内容]

### 调研员 B 发现
- [发现内容]

### 交叉验证结果
- 一致项：[列表]
- 差异项：[列表] → 需要进一步调查

### 综合结论
[Team-lead 的判断]
```

### 3. 差异处理

当 teammates 结论不一致时：

1. 不要简单"求和"
2. 标记差异点
3. 要求各自提供证据
4. Team-lead 做最终判断
5. 必要时调用 Codex 仲裁

---

## 常见问题

### Q: 为什么不使用多个 teammate 并行处理多个 PR？

A: 并行处理会导致：
- 责任分散，无人对整体负责
- 幻觉不被发现
- 缺乏交叉验证

正确做法是：**同一问题，多人分工，交叉验证**

### Q: 什么时候使用 Codex？

A:
- 关键 PR 的安全审查
- 其他 teammate 结论不一致时
- 需要深度追踪源码时

### Q: Team-lead 应该用什么模型？

A:
- 简单任务：sonnet
- 复杂判断：opus
- 关键决策：需要 Codex 交叉验证

---

## 更新日志

- 2026-05-01: 初始版本，基于 Team 功能实验总结

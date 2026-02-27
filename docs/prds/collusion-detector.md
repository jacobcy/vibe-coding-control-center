# PRD: Collusion Detector - AI 串通检测机制

## 1. Overview

Collusion Detector 是 Review Gate 后的**独立安全层**，通过 Spec vs Code vs Audit 三方对比，检测 AI 编码员和 AI 审计员是否存在"串通"（审计放水、概念偷换）。

## 2. Goals

- **三方对比**：逐项检查 Spec 要求 → Code 实现 → Audit 确认的一致性
- **阻断串通**：检测到不一致时阻断合并，要求人类介入
- **透明输出**：输出详细对比报告到对话

## 3. Non-Goals

- **不检测测试质量**：不评估测试覆盖率或测试逻辑
- **不检测 git 历史**：不对比 Spec vs Code 变更历史
- **不自动修复**：只检测和报告，不修复

## 4. Detection Logic

**三方对比流程：**

```
读取 Spec 不变量列表
    │
    └── 对每个不变量：
          │
          ├── 检查 Code 中是否有对应实现
          │
          ├── 检查 Audit 报告中是否确认该项
          │
          └── 对比结果：
                │
                ├── Spec 有 + Code 有 + Audit 确认 → ✅ 绿
                ├── Spec 有 + Code 无 + Audit 确认 → 🔴 串通（审计撒谎）
                ├── Spec 有 + Code 有 + Audit 未提及 → 🟡 警告（审计遗漏）
                └── Spec 有 + Code 无 + Audit 未提及 → 🟡 警告（都遗漏）
```

**串通判定标准：**

| Code 实现 | Audit 确认 | 判定 |
|-----------|-----------|------|
| 无 | 确认通过 | 🔴 **串通** |
| 部分 | 确认通过 | 🔴 **串通** |
| 有 | 未提及 | 🟡 警告 |
| 无 | 未提及 | 🟡 警告 |

## 5. Output Format

**对话输出示例：**

```markdown
## Collusion Detection Report

### 串通风险评级：无 / 警告 / 检测到

### 逐项对比

| Spec 不变量 | Code 实现 | Audit 确认 | 状态 |
|-------------|-----------|------------|------|
| 接口返回 JSON | ✅ 有 | ✅ 确认 | 🟢 |
| 错误返回 500 | ❌ 无 | ✅ 确认 | 🔴 串通 |
| 超时重试 | ✅ 有 | ⚠️ 未提及 | 🟡 |

### 结论

🔴 **检测到串通**：审计报告存在虚假确认，阻断合并。

请人类介入检查以下问题：
- 错误返回 500：Code 未实现，但 Audit 确认通过
```

## 6. Trigger Flow

```
Review Gate
    │
    ├── vibe-rules-enforcer 完成合规审查
    │
    └── 触发 Collusion Detector
          │
          ├── 读取 Spec 不变量列表
          ├── 读取 Code 实现
          ├── 读取 Audit 报告
          ├── 执行三方对比
          │
          └── 输出结果：
                │
                ├── 无串通 → 允许合并
                ├── 警告 → 输出警告，允许合并（人类决定）
                └── 检测到串通 → 阻断合并，要求人类介入
```

## 7. Implementation Approach

| 组件 | 职责 | 文件 |
|------|------|------|
| Skill | 三方对比逻辑 | `skills/vibe-collusion-detector/SKILL.md` |

**调用关系：**
```
vibe-orchestrator (Review Gate)
    │
    ├── 调用 vibe-rules-enforcer
    │
    └── 调用 vibe-collusion-detector
            │
            ├── 读取 Spec（通过 plan-gate.sh）
            ├── 读取 Code（扫描 lib/, bin/）
            ├── 读取 Audit 报告（从 enforcer 输出）
            └── 执行对比 → 输出到对话
```

## 8. Success Criteria

| 场景 | 预期行为 |
|------|----------|
| Spec/Code/Audit 一致 | 输出"无串通"，允许合并 |
| Audit 虚假确认 | 检测到串通，阻断合并 |
| Audit 遗漏检查 | 输出警告，允许合并 |
| Spec 无不变量定义 | 跳过检测，提示"Spec 缺少不变量" |

# PRD: Spec Critic - AI 刺客找茬机制

## 1. Overview

Spec Critic 是 Plan Gate → Execution Gate 之间的**独立审查层**，在 Spec 锁定前进行逆向提问，专门挑刺找漏洞，输出报告由人类裁决。

## 2. Goals

- **强制审查**：进入 Execution Gate 前必须触发 critic
- **多维检查**：边界完备性、假设检验、完整性、过度设计
- **人类裁决**：critic 输出报告，人类决定是否继续

## 3. Non-Goals

- **不负责修改 Spec**：只输出问题，不自动修复
- **不负责执行阻断**：只提供报告，由人类裁决
- **不替代人类判断**：是辅助工具，不是决策者

## 4. Review Dimensions

**默认审查四个维度，可在 governance.yaml 中配置：**

| 维度 | 检查内容 | 默认启用 |
|------|----------|----------|
| 边界完备性 | 极限输入、并发场景、网络异常 | ✅ |
| 假设检验 | 隐式假设、假设不成立的后果 | ✅ |
| 完整性检查 | 接口契约完整、不变量真的不变 | ✅ |
| 过度设计检测 | 航母级设计、解决不存在问题的抽象 | ✅ |

**配置示例（governance.yaml）：**
```yaml
spec_critic:
  enabled: true
  dimensions:
    - boundary      # 边界完备性
    - assumptions   # 假设检验
    - completeness  # 完整性检查
    - overdesign    # 过度设计检测
```

## 5. Output Format

**Markdown 报告，追加到 Spec 文件末尾：**

```markdown
---
## Spec Critic Report

**审查时间**：{timestamp}
**审查维度**：{dimensions}

### 风险评级：低 / 中 / 高

### 找茬清单

| # | 类别 | 问题 | 严重度 | 建议 |
|---|------|------|--------|------|
| 1 | 边界 | 缺少空值处理 | 高 | 添加 null 检查 |
| 2 | 假设 | 假设网络永远稳定 | 中 | 添加重试机制 |

### 人类裁决

**结果**：approve / reject

**意见**：{人类输入}
```

## 6. Trigger Flow

```
Plan Gate 验证 Spec 完整性
    │
    ├── Spec 不完整 → 阻断
    │
    └── Spec 完整 → 触发 Spec Critic
          │
          ├── 生成 Critic Report
          │
          └── 追加到 Spec 文件末尾
                │
                └── 等待人类裁决
                      │
                      ├── approve → 进入 Execution Gate
                      └── reject → 返回修改 Spec
```

## 7. Implementation Approach

| 组件 | 职责 | 文件 |
|------|------|------|
| Skill | 审查逻辑 + 报告生成 | `skills/vibe-spec-critic/SKILL.md` |
| 配置 | 审查维度配置 | `.agent/governance.yaml` |

**调用关系：**
```
vibe-orchestrator (Plan Gate)
    │
    └── Spec 完整 → 调用 vibe-spec-critic
                        │
                        ├── 读取 Spec 内容
                        ├── 按配置维度审查
                        ├── 生成 Markdown 报告
                        └── 追加到 Spec 文件
```

## 8. Success Criteria

| 场景 | 预期行为 |
|------|----------|
| Spec 完整 | 触发 critic，生成报告，等待人类裁决 |
| 人类 approve | 进入 Execution Gate |
| 人类 reject | 返回修改 Spec，修改后需重新 critic |
| Spec 不完整 | Plan Gate 直接阻断，不触发 critic |

# PRD: Plan Gate Enhancement - 多源计划读取与验证

## 1. Overview

增强 Orchestrator 的 **Plan Gate**，使其能根据已选框架类型透明读取计划文件，并分层验证计划完整性。

## 2. Goals

- **透明读取**：根据 task.md 中的 framework 字段，自动定位并读取对应路径的计划文件
- **分层验证**：按 Gate 阶段验证对应层级的完整性
  - Scope Gate → PRD 层（目标、非目标）
  - Plan Gate → Spec 层（接口契约、不变量）
  - Execution Gate → Execution Plan 层（任务拆分、验收标准）
- **分级阻断**：核心项缺失阻断，次要项缺失警告

## 3. Non-Goals

- **不负责框架选择**：由 unified-dispatcher 处理
- **不负责计划创建**：由各框架的入口命令处理（`/opsx:new` 等）
- **不负责计划执行**：由 Execution Gate 处理

## 4. Scope

### 4.1 框架路径映射

Plan Gate 根据 task.md 中的 `framework` 字段，使用内置路径映射：

| framework | PRD 路径 | Spec 路径 | Execution Plan 路径 |
|-----------|----------|-----------|---------------------|
| `openspec` | `openspec/changes/<feature>/proposal.md` | `openspec/changes/<feature>/design.md` | `openspec/changes/<feature>/tasks.md` |
| `superpower` | `docs/prds/<feature>.md` | `docs/specs/<feature>-spec.md` | `docs/plans/<feature>.md` |

### 4.2 完整性检查项

**PRD 层（Scope Gate 用）：**

| 检查项 | 严重度 | 说明 |
|--------|--------|------|
| 目标 | 阻断 | 必须有明确的"我们要解决什么问题" |
| 非目标 | 警告 | 建议有"不做什么"防止发散 |
| 成功判据 | 警告 | 建议有验收标准 |

**Spec 层（Plan Gate 用）：**

| 检查项 | 严重度 | 说明 |
|--------|--------|------|
| 接口契约 | 阻断 | 必须有输入/输出定义 |
| 不变量 | 阻断 | 必须有核心业务规则 |
| 边界行为 | 警告 | 建议有异常处理说明 |

**Execution Plan 层（Execution Gate 用）：**

| 检查项 | 严重度 | 说明 |
|--------|--------|------|
| 任务拆分 | 阻断 | 必须有具体步骤 |
| 验收标准 | 阻断 | 必须有验证命令 |

## 5. Error Handling

### 5.1 验证失败处理流程

```
Plan Gate 读取计划
    │
    ├── 文件不存在
    │     └── 阻断 → "未找到计划文件，请先使用 /opsx:new 或创建 docs/prds/<feature>.md"
    │
    └── 文件存在 → 验证完整性
          │
          ├── 核心项缺失（阻断级）
          │     └── 阻断 → "计划缺少核心项：{缺失项}，请补充后再继续"
          │
          └── 次要项缺失（警告级）
                └── 警告 → "建议补充：{缺失项}" → 允许继续
```

### 5.2 错误消息模板

**阻断级：**
```
🚫 Plan Gate 阻断：计划文件缺少核心项

文件：{file_path}
缺失项：{missing_items}

请补充以上内容后再继续。如需帮助，可使用 /opsx:new 创建完整计划。
```

**警告级：**
```
⚠️ Plan Gate 警告：建议补充以下内容

文件：{file_path}
建议补充：{suggested_items}

已允许继续，但建议尽快补充以降低风险。
```

## 6. Success Criteria

| 场景 | 预期行为 |
|------|----------|
| OpenSpec 项目，计划完整 | 自动读取 `openspec/changes/<feature>/*`，验证通过 |
| Superpower 项目，计划完整 | 自动读取 `docs/prds/` + `docs/specs/` + `docs/plans/`，验证通过 |
| 计划缺少核心项 | 阻断，输出缺失项，引导补充 |
| 计划缺少次要项 | 警告，允许继续 |
| 计划文件不存在 | 阻断，引导用户使用对应框架创建 |

## 7. Implementation Approach

采用**混合方案**：

| 组件 | 职责 | 文件 |
|------|------|------|
| Shell 函数 | 路径映射 + 文件读取 | `.agent/lib/plan-gate.sh` |
| Skill 逻辑 | 完整性验证规则 | 增强 `skills/vibe-orchestrator/SKILL.md` |

**目录职责区分：**
- `lib/` — Vibe CLI 核心逻辑
- `.agent/lib/` — Agent/Skill 辅助逻辑

**调用关系：**
```
vibe-orchestrator (Plan Gate)
    │
    ├── 调用 .agent/lib/plan-gate.sh
    │     ├── plan_get_path() → 返回文件路径
    │     └── plan_read() → 返回文件内容
    │
    └── 执行验证逻辑（在 SKILL.md 中定义）
```

# Agent Rules 目录

本目录包含仓库长期生效的 Agent 规则、标准和实现指南。

## 目录职责

- `.claude/rules/`：仓库长期规则、硬约束、实现标准
- `.agent/policies/`：按 `plan/run/review` mode 注入的策略材料与共享工具约束

## 规则文件说明

### 核心规则

**coding-standards.md**
- 实现与交付细则
- 代码质量要求
- 测试标准
- Git 工作流

**python-standards.md**
- Python 实现标准（权威）
- 代码风格
- 类型注解
- 依赖管理（必须使用 uv）

**patterns.md**
- 执行模式（常规/快速）
- 报告模式
- 渐进披露原则
- Context First 原则

### 使用指南

**common.md**
- 常用命令
- 代码分析工具（inspect 系列）
- 代码搜索工具（auggie MCP vs Grep）
- 格式化输出选项

## 规则优先级

1. **HARD RULES** (CLAUDE.md) - 最小不可协商规则
2. **权威标准** (.claude/rules/*-standards.md) - 技术实现标准
3. **执行细则** (.claude/rules/*.md) - 具体操作指南

## 更新规则

当发现新的最佳实践或通用规则时：

1. 判断规则类型：
   - 核心原则 → 更新 CLAUDE.md HARD RULES
   - 技术标准 → 更新或创建 *-standards.md
   - 操作指南 → 更新或创建相应的 .md 文件

2. 遵循 Progressive Disclosure 原则：
   - CLAUDE.md 只保留最小硬规则
   - 详细内容下沉到 rules/ 目录

3. 引用规则文件：
   - 在 CLAUDE.md 中引用规则文件
   - 避免在多个地方重复相同内容

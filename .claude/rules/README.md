# Agent Rules 目录

本目录包含仓库长期生效的 Agent 规则、标准和实现指南。

## 目录职责

- `.claude/rules/`：仓库长期规则、项目特定约束、实现标准
- `.agent/policies/`：按 `plan/run/review` mode 注入的策略材料与共享工具约束

## 规则文件说明

### 核心规则

**coding-standards.md**
- 实现与交付细则
- 文件和函数大小限制（分层差异）
- Git 工作流和交付纪律
- Shell/Skill 边界和工具选择

**python-standards.md**
- Python 实现标准（权威）
- 分层架构和依赖管理（uv）
- 类型注解和测试规范

**patterns.md**
- 执行模式（常规/快速）
- 报告模式和渐进披露原则
- Context First 和 Fail Fast 模式

## 安全规范

项目特定安全要求已整合到 `CLAUDE.md` HARD RULES 第 17 条，通用 Python 安全规范见：
- `~/.claude/rules/common/python-security.md`

## 规则优先级

1. **HARD RULES** (CLAUDE.md) - 最小不可协商规则
2. **权威标准** (.claude/rules/*-standards.md) - 技术实现标准
3. **执行细则** (.claude/rules/*.md) - 具体操作指南
4. **全局规则** (~/.claude/rules/common/) - 通用最佳实践

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

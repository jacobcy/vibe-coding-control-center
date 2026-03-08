---
document_type: prd
author: Antigravity
created: 2026-03-08
status: draft
related_docs:
  - SOUL.md
  - CLAUDE.md
---

# PRD: CLI Roadmap Style Polish

## 1. 业务背景
`vibe roadmap` 是管理项目规划的核心命令，但其目前的输出风格（尤其是 `show` 子命令）过于简陋，且缺乏颜色高亮，与 `vibe check` 或 `vibe task show` 的整体风格不统一。

## 2. 核心目标
- 对齐 `vibe roadmap show` 的输出结构。
- 引入 ANSI 颜色支持，根据 Issue 状态（P0, current 等）显示不同颜色。
- 保持与现有 Vibe CLI 风格一致。

## 3. 功能需求
- **状态染色**：
  - `p0`: 红色加粗
  - `current`: 绿色
  - `next`: 蓝色
  - `deferred`: 黄色
  - `rejected`: 灰色
- **结构化输出**：使用分割线和清晰的字段标签。
- **命令行参数**：支持 `--color` (目前全局默认为 auto)。

## 4. 验收标准
- [ ] 运行 `vibe roadmap show <id>` 输出带有颜色。
- [ ] 字段排列整齐。
- [ ] 状态颜色符合预期。

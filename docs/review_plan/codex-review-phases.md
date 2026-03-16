---
document_type: plan
title: Codex Review 实施计划总览
status: active
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/references/codex-review.md
  - docs/references/codex-serena-intetration.md
  - docs/standards/serena-usage.md
---

# Codex Review 实施计划总览

> [!NOTE]
> 本文档已拆分为三个阶段性实施计划，详见下方链接。

---

## 实施阶段

### Phase 1 - 基础设施搭建
**详见**: [phase1-infrastructure.md](phase1-infrastructure.md)

**目标**:
- 创建 v3 配置管理系统
- 迁移现有工具到 v3 分层架构
- 实现符号分析、DAG、风险评分等核心服务

**关键组件**:
- Serena Service - 符号分析
- Metrics Service - 指标收集
- Structure Service - 结构分析
- DAG Service - 模块依赖图
- PR Scoring Service - 风险评分

---

### Phase 2 - 审核流程集成
**详见**: [phase2-integration.md](phase2-integration.md)

**目标**:
- 创建信息提供命令 (`vibe inspect`)
- 创建代码审核命令 (`vibe review`)
- 集成评分系统到审核流程
- 实现 GitHub API 集成

**关键组件**:
- Inspect 命令 (Python typer) - 信息提供
- Review 命令 (Python typer) - 代码审核
- GitHub Client
- Review 解析器

---

### Phase 3 - 自动化与 CI/CD 集成
**详见**: [phase3-automation.md](phase3-automation.md)

**目标**:
- Git Hook 自动化审核
- GitHub Workflow 集成
- Merge gate 实现

**关键组件**:
- Commit Analyzer Service
- Git Hooks (post-commit)
- GitHub Workflow
- Merge gate 逻辑

---

## 完整流程

```
git diff / PR diff
    ↓
vibe inspect pr 42 (信息提供)
    ↓
Structure Summary (代码结构)
    ↓
Serena Service (符号分析)
    ↓
DAG Service (影响范围)
    ↓
PR Scoring Service (风险评分)
    ↓
vibe review pr 42 (代码审核)
    ↓
Codex Review (代码审查)
    ↓
GitHub API (评论 & merge gate)
```

**命令职责分工**:
- **`vibe inspect`** - 信息提供（metrics、structure、symbols、改动分析）
- **`vibe review`** - 代码审核（发现 bug、安全、性能问题）

---

## 参考资料对齐

本实施计划基于以下参考资料的核心逻辑：

- [codex-review.md](../references/codex-review.md) - Codex Review 使用体系
- [codex-serena-intetration.md](../references/codex-serena-intetration.md) - Serena 与 Codex 集成架构

### 架构完全对齐

**参考资料架构**:
```
PR diff
  ↓
python_structure_summary.sh
  ↓
Serena adapter（抽取 changed symbols / references）
  ↓
Review DAG（只保留受影响模块）
  ↓
Risk scoring（给 PR 量化风险）
  ↓
Codex review（基于 policy + context）
  ↓
PR summary comment
```

**实施计划对应**:
| 参考资料组件 | 实施计划对应 | 阶段 |
|-------------|-------------|------|
| `python_structure_summary.sh` | Structure Service | Phase 1 |
| `Serena adapter` | Serena Service | Phase 1 |
| `Review DAG` | DAG Service | Phase 1 |
| `Risk scoring` | PR Scoring Service | Phase 1 |
| `render_prompt.py` | Context Builder | Phase 2 |
| `post_review.py` | GitHub Client | Phase 2 |
| `codex review` | Codex CLI | Phase 2 |
| 信息提供命令 | `vibe inspect` | Phase 2 |
| 审核命令 | `vibe review` | Phase 2 |
| Git hooks | Commit Analyzer + hooks | Phase 3 |
| GitHub Workflow | Workflow + merge gate | Phase 3 |

### 关键设计原则

**职责边界清晰**（来自参考资料）:
- **Serena 提供事实层**: 符号和引用关系，不是"让 Serena 替 Codex 审查"
- **DAG 缩小上下文**: 只看影响面，减少"全仓盲审"
- **Scoring 决定风险级别**: 量化风险，为 merge gate 提供依据
- **Codex 输出审查意见**: 基于结构化证据，不是盲审
- **GitHub API 落地到 PR**: 行级 review comments + 风险报告

**命令职责分离**（实施计划新增）:
- **`vibe inspect`**: 信息提供（提供 metrics/structure/symbols/改动分析）
- **`vibe review`**: 代码审核（发现 bug/安全/性能问题）
- **职责关系**: `inspect` 提供结构化信息 → `review` 消费信息进行审核

### 路径配置适配

**参考资料示例** → **vibe-center 实际结构**:

```yaml
# 参考资料示例
critical_paths:
  - "flow/"
  - "git/"
  - "github/"
  - "cli/"

# 适配到 vibe-center
critical_paths:
  - "bin/"
  - "lib/flow"
  - "lib/git"
  - "lib/github"
  - "scripts/python/vibe3/services/"
```

### 结构优化

实施计划在参考资料基础上做了架构优化：

| 方面 | 参考资料 | 实施计划 | 优势 |
|------|---------|---------|------|
| 目录结构 | `.ai-review/` | v3 分层架构 | 符合项目规范 |
| 配置文件 | `.ai-review/config.yaml` | `.vibe/config.yaml` | 统一配置体系 |
| 代码组织 | 单文件脚本 | Services + Commands | 职责分离清晰 |
| 测试标准 | 未明确 | v3 测试标准（≥80%） | 质量保证 |
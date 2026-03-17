---
document_type: specification
title: Codex 自动审核规划 (Codex Auto-Review Plan)
status: draft
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/references/codex-review.md
  - docs/references/codex-serena-intetration.md
  - docs/standards/serena-usage.md
  - docs/review_plan/codex-review-phases.md
---

# Codex 自动审核规划 (Codex Auto-Review Plan)

> [!IMPORTANT]
> **核心原则**: 组织现有工具到 v3 架构，添加日志和错误处理，不重新发明。
>
> **实施标准**: 所有实现必须遵守 **[v3 技术标准](../v3/implementation/03-coding-standards.md)**。

## 1. 设计理念

审核系统被定义为”组织现有工具，提供标准化服务”。

### 1.1 核心原则
- **复用现有组件**: Serena、Codex、Claude Code 都是已安装工具
- **职责清晰**: Serena（上下文）→ DAG（范围）→ Codex（审核）→ GitHub（定位）
- **标准化改造**: 添加日志（loguru）、错误处理、类型注解
- **v3 架构对齐**: Services / Commands / Clients 分层

## 2. 职责分工

### 2.1 组件职责

| 组件 | 职责 | 输入 | 输出 | 实现 |
|------|------|------|------|------|
| **Serena** | 提供代码上下文（符号分析） | git diff | `impact.json` | Python API |
| **DAG** | 确认代码影响范围 | `impact.json` | `dag.json` | Python AST |
| **PR Scoring** | 计算风险分数，判定风险等级 | impact + dag | `score.json` | 多维度评分 |
| **Codex** | 调用本地 CLI 审核 | context.md | 审核报告 | `codex review` |
| **Claude** | 备选审核后端 | context.md | 审核报告 | `claude -p` |
| **GitHub API** | 行级 review comments | file:line | Review comments | REST API |

### 2.2 审核流程

```
vibe review pr 42
    ↓
1. 内部调用 vibe inspect pr 42 → 获取改动分析（JSON）
    ↓
2. serena_service → impact.json (符号分析)
    ↓
3. dag_service → dag.json (影响范围)
    ↓
4. pr_scoring_service → score.json (风险评分)
    ↓
5. 构建上下文 (policy + impact + dag + score)
    ↓
6. codex review --base main - < context.md
    ↓
7. 解析 Codex 结果，更新风险分数
    ↓
8. GitHub API → 行级 review comments + 风险报告
```

**关键设计**：
- `vibe inspect` 提供结构化信息（metrics、structure、symbols、改动分析）
- `vibe review` 消费 `inspect` 提供的信息，进行代码审核
- 职责分离：信息提供 vs 问题发现

## 3. 架构设计

### 3.1 v3 架构（复用现有架构）

```
scripts/python/vibe3/
├── services/
│   ├── serena_service.py     # 迁移 serena_gate.py
│   ├── dag_service.py        # 新增：DAG 分析
│   ├── pr_scoring_service.py # 新增：PR 风险评分
│   ├── metrics_service.py    # 迁移 metrics.sh
│   └── structure_service.py  # 迁移 structure_summary.sh
│
├── commands/
│   └── review.py             # 审核命令入口（vibe review）
│
└── clients/
    └── github_client.py      # 扩展：review comments API
```

### 3.2 命令职责分工

系统提供两个新的命令，职责清晰分离：

#### `vibe inspect` - 信息提供
提供代码分析信息，为 `vibe review` 提供上下文数据
```bash
vibe inspect                  # 综合信息
vibe inspect metrics          # 代码量指标
vibe inspect structure        # 文件结构分析
vibe inspect symbols [file]   # 代码符号分析
  # 详见: phase2-integration.md Section 4.1
vibe inspect commands [cmd]   # 命令结构查看（静态分析）
  # 详见: references/symbol-vs-command-design.md
vibe inspect pr 42            # PR 改动分析（输出 JSON）
vibe inspect commit SHA       # Commit 改动分析（输出 JSON）
vibe inspect base main        # 相对分支的改动分析（输出 JSON）
```

**参数用法**: 所有子命令支持核心参数集（`--trace`, `-v/--verbose`, `--json`, `-y/--yes`），详见 [v3 命令参数标准](../v3/implementation/07-command-standards.md)

**架构对齐**:
- ✅ 符合 Tier 1 (Shell 能力层) 定位：确定性操作、结构化输出
- ✅ 复用现有 `bin/vibe` 入口
- ✅ Python services 作为底层能力
- ✅ 为 `vibe review` 提供结构化数据输入

#### `vibe review` - 代码审核
基于 `vibe inspect` 提供的上下文，进行代码审核（发现 bug、安全、性能问题）
```bash
vibe review pr 42             # 审核 PR（调用 inspect pr 42 获取上下文）
vibe review pr 42 --trace     # 审核 PR 并追踪执行过程（调试模式）
vibe review --uncommitted     # 审核未提交改动
vibe review base main         # 审核相对分支的改动
vibe review commit SHA        # 审核指定 commit
```

**参数用法**: 所有子命令支持核心参数集（`--trace`, `-v/--verbose`, `--json`, `-y/--yes`），详见 [v3 命令参数标准](../v3/implementation/07-command-standards.md)

### 3.3 技术栈（已安装）

| 组件 | 技术选择 | 用途 | 调用方式 |
|------|----------|------|----------|
| Serena | Python API | 符号分析 | `serena.agent.SerenaAgent` |
| Codex | CLI | 代码审核 | `codex review --base main -` |
| Claude | CLI | 备选审核 | `claude -p` |
| GitHub | REST API | 行级评论 | `requests.post()` |

## 4. 迁移计划

### 4.1 现有工具迁移

| 原工具 | 原位置 | 迁移目标 | v3 位置 | 改造内容 |
|--------|--------|----------|---------|----------|
| `serena_gate.py` | `scripts/review-tools/` | Service | `services/serena_service.py` | +日志/类型/错误处理 |
| `metrics.sh` | `scripts/review-tools/` | Service | `services/metrics_service.py` | Shell→Python |
| `structure_summary.sh` | `scripts/review-tools/` | Service | `services/structure_service.py` | Shell→Python |
| - | - | Service | `services/dag_service.py` | 新增：DAG 分析 |
| - | - | Service | `services/pr_scoring_service.py` | 新增：PR 风险评分 |

### 4.3 PR Scoring 系统

**目标**: 根据 PR 多维度指标计算风险分数，为 merge gate 提供决策依据

**评分维度**（基于参考资料）:

| 维度 | 权重配置 | 说明 |
|------|----------|------|
| **changed_lines** | 0-3 分 | 改动行数：small(0), medium(1), large(2), xlarge(3) |
| **changed_files** | 0-2 分 | 改动文件数：small(0), medium(1), large(2) |
| **impacted_modules** | 0-2 分 | 影响模块数：small(0), medium(1), large(2) |
| **critical_path_touch** | +2 分 | 触及关键路径（bin/, lib/flow, services/） |
| **public_api_touch** | +2 分 | 触及公开 API（CLI 命令、公开函数） |
| **cross_module_symbol_change** | +2 分 | 跨模块符号改动 |
| **codex_major** | +3 分 | Codex 发现 Major 问题 |
| **codex_critical** | +5 分 | Codex 发现 Critical 问题 |

**风险等级**:
- **LOW** (0-2 分): 小改动，单模块，非关键路径
- **MEDIUM** (3-5 分): 中等改动，多模块，触及关键路径
- **HIGH** (6-8 分): 大改动，跨模块，触及公开 API
- **CRITICAL** (≥9 分): 超大改动或 Codex 发现严重问题

**Merge Gate 决策**:
- **CRITICAL/HIGH** → 阻断合并，必须修复
- **MEDIUM** → 警告，建议修复
- **LOW** → 通过

### 4.4 GitHub Client 扩展

**现有**: `clients/github_client.py` (已存在)

**扩展**: 添加 review comments API

```python
def post_review_comment(
    self,
    pr_number: int,
    file: str,
    line: int,
    body: str
) -> None:
    “””发送行级 review comment”””
    url = f”{GITHUB_API}/repos/{self.repo}/pulls/{pr_number}/comments”
    ...
```

### 4.3 统一入口

**命令入口**: `bin/vibe review` (通过 `commands/review.py`)

**职责**: 调度 v3 services + 调用现有 CLI

## 5. 标准化改造

### 5.1 日志标准

```python
from loguru import logger

def analyze_symbols(files: list[str]) -> dict:
    “””分析符号引用关系”””
    logger.bind(domain=”review”, action=”serena_analysis”).info(
        “Analyzing symbols”, files_count=len(files)
    )
    try:
        agent = SerenaAgent(project=”.”)
        # 现有逻辑
        ...
    except Exception as e:
        logger.exception(“Serena analysis failed”)
        raise
```

### 5.2 错误处理

```python
from vibe3.models.exceptions import VibeError, UserError

class SerenaAnalysisError(VibeError):
    “””Serena 分析失败”””
    pass

def analyze_symbols(files: list[str]) -> dict:
    if not files:
        raise UserError(“No files to analyze”)
    try:
        ...
    except Exception as e:
        raise SerenaAnalysisError(f”Analysis failed: {e}”) from e
```

### 5.3 类型注解

```python
def analyze_symbols(files: list[str]) -> dict[str, Any]:
    “””分析符号引用关系

    Args:
        files: 文件列表

    Returns:
        符号引用关系字典
    “””
    ...
```

## 6. 质量标准

所有实现必须遵循 v3 标准，详见 **[phase1-infrastructure.md 验收标准](phase1-infrastructure.md#验收标准)**。

核心要求:
- 编码标准: [docs/v3/implementation/03-coding-standards.md](../v3/implementation/03-coding-standards.md)
- 测试标准: Services ≥ 80% 覆盖率
- 日志标准: 使用 loguru + context binding
- 错误处理: 统一异常层级

---

更多执行细节请参考 **[Codex Review 实施阶段计划](codex-review-phases.md)**。

---

## 设计参考文档

本实施计划涉及多个设计决策，详见 `references/` 目录：

- **[改动分析架构](references/change-analysis-architecture.md)** - 统一改动源抽象（PR/Commit/Branch/Uncommitted）
- **[Phase1/Phase2 衔接](references/phase1-phase2-integration.md)** - 能力层与编排层的关系
- **[调用追踪 vs DAG](references/call-tracing-vs-dag.md)** - 两个容易混淆的概念澄清
- **[命令调试设计](references/command-debug-design.md)** - 静态检查 vs 动态追踪
- **[符号 vs 命令设计](references/symbol-vs-command-design.md)** - 命令语义规范和子命令设计

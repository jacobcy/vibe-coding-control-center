# Phase 1 & Phase 2 架构衔接说明

> **核心思想**: Phase 1 提供"能力层"，Phase 2 提供"编排层"

---

## 1. 衔接架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Phase 2 (编排层)                      │
│  commands/inspect.py + commands/review.py              │
│  - 解析用户命令                                           │
│  - 编排调用顺序                                           │
│  - 格式化输出                                             │
└────────────────────┬────────────────────────────────────┘
                     │ 调用
                     ↓
┌─────────────────────────────────────────────────────────┐
│                    Phase 1 (能力层)                      │
│  Services + Clients + Models                            │
│  - 提供原子能力（获取改动、分析符号、计算评分）         │
│  - 输出结构化数据（JSON）                                │
│  - 不关心命令来源                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 具体对接示例

### 2.1 `vibe inspect pr 42` 调用链

**Phase 2 (编排)**:
```python
# commands/inspect.py
@app.command()
def pr(pr_number: int, json_output: bool = False):
    """PR 改动分析"""
    # 1. 创建改动源
    source = PRSource(pr_number=pr_number)  # Phase 1 提供的模型

    # 2. 调用 Service 层分析
    impact = serena.analyze_changes(source)  # Phase 1 提供的能力
    dag_result = dag.expand_impact(impact)
    score = scoring.calculate_score(impact, dag_result)

    # 3. 格式化输出
    result = {
        "source": source.model_dump(),
        "impact": impact,
        "dag": dag_result,
        "score": score
    }
    typer.echo(json.dumps(result, indent=2))
```

**Phase 1 (能力)**:
```python
# services/serena_service.py
def analyze_changes(self, source: ChangeSource) -> dict:
    """分析改动符号（统一接口）"""
    # 1. 获取改动文件（调用 Git Client）
    files = self.git.get_changed_files(source)

    # 2. 分析符号（调用 Serena Client）
    return self.analyze_files(files)

# clients/git_client.py
def get_changed_files(self, source: ChangeSource) -> list[str]:
    """获取改动文件列表（统一接口）"""
    if isinstance(source, PRSource):
        return self._get_pr_files(source.pr_number)
    # ... 其他类型
```

**关键点**:
- Phase 1 不关心"命令来源"，只关心"改动源类型"
- Phase 2 负责解析命令、创建改动源、编排调用

---

### 2.2 `vibe review pr 42` 调用链

**Phase 2 (编排)**:
```python
# commands/review.py
@app.command()
def pr(pr_number: int):
    """审核 PR"""
    # 1. 调用 inspect 命令获取上下文
    inspect_result = subprocess.run(
        ["vibe", "inspect", "pr", str(pr_number), "--json"],
        capture_output=True, text=True
    )
    context_data = json.loads(inspect_result.stdout)

    # 2. 构建 Codex 上下文
    context = context_builder.build_review_context(
        policy_path=".codex/review-policy.md",
        impact=context_data["impact"],
        dag=context_data["dag"],
        score=context_data["score"],
        base="main"
    )

    # 3. 调用 Codex
    result = subprocess.run(
        ["codex", "review", "--base", "main", "-"],
        input=context, text=True, capture_output=True
    )

    # 4. 解析结果并输出
    typer.echo(result.stdout)
```

**关键点**:
- `vibe review` 通过 subprocess 调用 `vibe inspect`（解耦）
- Phase 1 提供 `inspect` 的所有能力
- Phase 2 编排 `inspect → context → codex` 流程

---

## 3. Phase 1 提供的能力清单

| 能力 | 文件 | 方法 | 输出 |
|------|------|------|------|
| 改动源抽象 | `models/change_source.py` | `PRSource`, `CommitSource`, etc. | pydantic 模型 |
| 获取改动文件 | `clients/git_client.py` | `get_changed_files(source)` | `list[str]` |
| 获取 diff | `clients/git_client.py` | `get_diff(source)` | `str` |
| 符号分析 | `services/serena_service.py` | `analyze_changes(source)` | `dict` (impact.json) |
| DAG 分析 | `services/dag_service.py` | `expand_impact(impact)` | `dict` (dag.json) |
| 风险评分 | `services/pr_scoring_service.py` | `calculate_score(impact, dag)` | `dict` (score.json) |

---

## 4. Phase 2 的职责

| 职责 | 说明 |
|------|------|
| **命令解析** | 解析 `vibe inspect pr 42`，提取参数 |
| **改动源创建** | 创建 `PRSource(pr_number=42)` |
| **编排调用** | 决定调用顺序：serena → dag → scoring |
| **输出格式化** | 将 JSON 格式化为用户友好的输出 |
| **错误处理** | 捕获异常，显示友好错误信息 |
| **上下文构建** | 为 `vibe review` 构建完整上下文 |

---

## 5. 关键设计原则

### 5.1 单向依赖

```
Phase 2 (commands/)  →  Phase 1 (services/clients/models/)
```

- Phase 1 不知道 Phase 2 的存在
- Phase 2 通过导入 Phase 1 的模块使用能力
- **好处**: Phase 1 可以独立测试、独立演进

### 5.2 接口稳定

Phase 1 提供的接口稳定不变：
```python
# 稳定的接口签名
def analyze_changes(self, source: ChangeSource) -> dict:
def get_changed_files(self, source: ChangeSource) -> list[str]:
def get_diff(self, source: ChangeSource) -> str:
```

Phase 2 可以放心调用，不受内部实现变化影响。

### 5.3 数据标准化

所有输出都是结构化 JSON：
```json
{
  "source": {"type": "pr", "pr_number": 42},
  "impact": {...},
  "dag": {...},
  "score": {...}
}
```

Phase 2 的 `vibe review` 可以直接解析 JSON，无需了解内部细节。

---

## 6. 总结

| 维度 | Phase 1 | Phase 2 |
|------|---------|---------|
| **定位** | 能力层 | 编排层 |
| **职责** | 提供原子能力 | 编排命令流程 |
| **输入** | 改动源模型 | 用户命令 |
| **输出** | 结构化数据 | 用户友好的输出 |
| **独立性** | 可独立测试、演进 | 依赖 Phase 1 |
| **变化频率** | 低（接口稳定） | 高（命令可能变化） |

**衔接核心**: Phase 1 提供"稳定的能力接口"，Phase 2 负责"编排这些能力"。
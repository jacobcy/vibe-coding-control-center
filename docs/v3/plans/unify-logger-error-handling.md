---
document_type: implementation-plan
title: 统一 Logger 和 Error 处理规范
status: draft
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-17
related_docs:
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/05-logging.md
  - src/vibe3/observability/README.md
  - src/vibe3/exceptions/__init__.py
scope: src/vibe3/
priority: high
estimated_effort: 2-3 hours
---

# 统一 Logger 和 Error 处理规范

本计划旨在统一 Vibe 3.0 的日志记录和错误处理方式，消除冗余代码，提升代码可维护性和可追踪性。

---

## 📊 现状分析

### ✅ 已完成部分

#### Observability 模块
- ✅ 创建 `src/vibe3/observability/` 模块
- ✅ 实现 `setup_logging()` 支持 verbosity 控制
- ✅ 实现 Tracer API 用于调用链追踪
- ✅ 集成到 CLI 入口点（支持 `-v` 参数）

参考：[src/vibe3/observability/README.md](src/vibe3/observability/README.md)

#### 异常体系
- ✅ 统一异常继承 `VibeError`
- ✅ 区分 UserError（可恢复）和 SystemError（不可恢复）
- ✅ 业务异常（PRNotFoundError, FlowNotFoundError 等）
- ✅ CLI 层统一错误处理

参考：[src/vibe3/exceptions/__init__.py](src/vibe3/exceptions/__init__.py)

### ❌ 存在问题

#### 问题 1: Logger 使用不规范

**现象**：
```python
# services/pr_service.py:69
logger.info("Creating draft PR", title=title, base_branch=base_branch)
```

**问题**：
- ❌ 缺少 `logger.bind()` 结构化字段绑定
- ❌ 参数作为 kwargs 传递，不符合 loguru 标准用法
- ❌ 无法被 agent 有效追踪

**影响范围**：
- `services/pr_service.py` - 24 处 logger 调用
- `services/flow_service.py` - 5 处 logger 调用
- `services/task_service.py` - 5 处 logger 调用
- `services/review_service.py` - 2 处 logger 调用
- `services/serena_service.py` - 6 处 logger 调用

#### 问题 2: Commands 层冗余错误处理

**现象**：
```python
# commands/pr.py:23-26
def _handle_error(message: str, error: Exception) -> None:
    """Handle error and exit."""
    render_error(f"{message}: {error}")
    raise typer.Exit(1)
```

**问题**：
- ❌ 与 CLI 层统一错误处理职责重叠
- ❌ 捕获异常后未使用 `logger.exception()` 记录堆栈
- ❌ 不必要的 try-except 包裹所有命令

**影响范围**：
- `commands/pr.py` - 所有 6 个命令都使用 try-except
- `commands/flow.py` - 类似模式

#### 问题 3: Error 和 Logger 混淆

**现象**：
```python
# commands/pr.py
except Exception as e:
    _handle_error("Failed to create draft PR", e)  # UI 渲染

# services/pr_service.py
except GitHubError as e:
    logger.error("Failed to create PR", error=str(e))  # 日志记录
    raise
```

**问题**：
- ❌ UI 层 `render_error()` 与错误处理混淆
- ❌ Services 层错误日志未保留完整堆栈
- ❌ 职责不清晰

---

## 🎯 目标

### 核心目标

1. **统一 Logger 使用**：所有层级使用 `logger.bind()` 标准字段
2. **简化错误处理**：Commands 层移除冗余 try-except，统一到 CLI 层
3. **提升可追踪性**：所有操作可被 agent 追踪和调试

### 成功标准

**Logger**:
- ✅ Services 层所有 logger 调用都有 `bind()` 结构化字段
- ✅ 错误使用 `logger.exception()` 记录完整堆栈
- ✅ 成功操作使用 `logger.success()` 记录

**Error**:
- ✅ Commands 层无 `_handle_error()` 函数
- ✅ Services 层只抛异常不捕获（除非需要转换异常类型）
- ✅ CLI 层统一处理所有异常

**Import**:
- ✅ 所有文件 `from loguru import logger`
- ✅ CLI 入口 `from vibe3.observability import setup_logging`

---

## 🏗️ 架构设计

### 职责分离架构

```
┌─────────────────────────────────────────────────────────────┐
│ CLI Layer (cli.py)                                          │
│ - 调用 setup_logging()                                      │
│ - 捕获所有异常                                               │
│ - 统一错误处理 (UserError/SystemError)                       │
│ - 决定显示方式 (logger.error/exception)                      │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ raise
┌─────────────────────────────────────────────────────────────┐
│ Commands Layer (commands/*.py)                              │
│ - 参数验证 (Pydantic)                                        │
│ - logger.bind(command="pr draft")                           │
│ - 调用 Services                                              │
│ - 调用 UI 渲染                                               │
│ - 不捕获异常                                                 │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ raise
┌─────────────────────────────────────────────────────────────┐
│ Services Layer (services/*.py)                              │
│ - logger.bind(domain="pr", action="create_draft")           │
│ - 业务逻辑                                                   │
│ - 抛出特定异常 (UserError/SystemError)                       │
│ - logger.exception() 记录错误                                │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ raise
┌─────────────────────────────────────────────────────────────┐
│ Clients Layer (clients/*.py)                                │
│ - logger.bind(external="github")                            │
│ - 封装外部系统                                               │
│ - 抛出特定异常 (GitHubError/GitError)                        │
└─────────────────────────────────────────────────────────────┘
```

### 标准字段定义

根据 [docs/v3/infrastructure/05-logging.md](docs/v3/infrastructure/05-logging.md)：

**Commands 层**：
```python
logger.bind(
    command="pr draft",  # 用户输入的原始命令
).info("Starting command")
```

**Services 层**：
```python
logger.bind(
    domain="pr",             # 业务域 (pr/flow/task/handoff)
    action="create_draft",   # 当前执行的具体原子操作
    title=title,             # 关键业务参数
).info("Creating draft PR")
```

**Clients 层**：
```python
logger.bind(
    external="github",       # 外部系统标识
    operation="create_pr",   # 操作名称
).debug("Calling GitHub API")
```

---

## 📋 迁移计划

### Phase 1: Commands 层简化（优先级：高）

**目标**：移除冗余错误处理，让异常冒泡到 CLI 层

**任务清单**：

- [ ] **删除 `_handle_error()` 函数**
  - 文件：`commands/pr.py`
  - 影响：所有 6 个命令
  - 替代方案：直接让异常冒泡

- [ ] **移除所有 try-except 块**
  - 文件：`commands/pr.py`
  - 文件：`commands/flow.py`
  - 保留：Pydantic 参数验证错误可转换为 UserError

- [ ] **添加命令级日志**
  - 每个命令入口添加 `logger.bind(command="pr draft").info(...)`

**预计时间**：30 分钟

**验证**：
```bash
# 运行命令应该仍能正常显示错误
python -m vibe3.cli pr draft --title "test"
# 预期：异常被 CLI 层捕获并显示友好错误消息
```

---

### Phase 2: Services 屁 Logger 规范化（优先级：高）

**目标**：统一所有 logger 调用，使用 `bind()` 结构化字段

**任务清单**：

- [ ] **迁移 pr_service.py**
  - 文件：`services/pr_service.py`
  - 调用数：24 处
  - 模式：`logger.info(...)` → `logger.bind(...).info(...)`

- [ ] **迁移 flow_service.py**
  - 文件：`services/flow_service.py`
  - 调用数：5 处

- [ ] **迁移 task_service.py**
  - 文件：`services/task_service.py`
  - 调用数：5 处

- [ ] **迁移 review_service.py**
  - 文件：`services/review_service.py`
  - 调用数：2 处

- [ ] **迁移 serena_service.py**
  - 文件：`services/serena_service.py`
  - 调用数：6 处

**标准迁移模式**：

```python
# Before
logger.info("Creating draft PR", title=title, base_branch=base_branch)

# After
logger.bind(
    domain="pr",
    action="create_draft",
    title=title,
    base_branch=base_branch,
).info("Creating draft PR")
```

**错误处理迁移**：

```python
# Before
except GitHubError as e:
    logger.error("Failed to create PR", error=str(e))
    raise

# After
except GitHubError as e:
    logger.exception(f"Failed to create PR: {e}")
    raise
```

**预计时间**：1 小时

**验证**：
```bash
# 运行命令并检查日志输出
python -m vibe3.cli -vv pr draft --title "test"
# 预期：看到结构化的日志输出，包含 domain/action 字段
```

---

### Phase 3: Clients 层 Logger 规范化（优先级：中）

**目标**：为外部依赖调用添加追踪字段

**任务清单**：

- [ ] **迁移 github_client.py**
  - 文件：`clients/github_client.py`
  - 添加 `external="github"` 字段

- [ ] **迁移 sqlite_client.py**
  - 文件：`clients/sqlite_client.py`
  - 添加 `external="sqlite"` 字段

- [ ] **迁移 serena_client.py**
  - 文件：`clients/serena_client.py`
  - 添加 `external="serena"` 字段

**标准模式**：

```python
# clients/github_client.py
def create_pr(self, title: str, base: str) -> PR:
    logger.bind(
        external="github",
        operation="create_pr",
        repo=self.repo,
    ).debug("Calling GitHub API: create_pull_request")

    response = self._client.pulls.create(...)
    return PR.from_github(response)
```

**预计时间**：30 分钟

---

### Phase 4: 文档和测试（优先级：中）

**目标**：更新文档，补充测试，确保规范可执行

**任务清单**：

- [ ] **创建 Logger 使用指南**
  - 文件：`docs/v3/guides/logger-usage.md`
  - 内容：标准字段、使用示例、常见错误

- [ ] **更新代码审查清单**
  - 文件：`.agent/rules/coding-standards.md`
  - 添加：Logger 和 Error 处理检查项

- [ ] **补充单元测试**
  - 测试 Commands 层异常冒泡
  - 测试 Services 层 logger.bind() 输出
  - 测试 CLI 层错误处理

- [ ] **创建验证脚本**
  - 自动检查 logger 调用是否符合规范
  - 检查是否缺少 bind()

**预计时间**：1 小时

---

## 📐 示例对比

### Commands 层

#### Before (当前)
```python
# commands/pr.py
def _handle_error(message: str, error: Exception) -> None:
    render_error(f"{message}: {error}")
    raise typer.Exit(1)

@app.command()
def draft(title: str = typer.Option(...)) -> None:
    try:
        service = PRService()
        pr = service.create_draft_pr(title=title, ...)
        render_pr_created(pr)
    except Exception as e:
        _handle_error("Failed to create draft PR", e)
```

#### After (迁移后)
```python
# commands/pr.py
@app.command()
def draft(title: str = typer.Option(...)) -> None:
    # 记录命令上下文
    logger.bind(command="pr draft", title=title).info("Creating draft PR")

    service = PRService()
    pr = service.create_draft_pr(title=title, ...)
    render_pr_created(pr)
    # 无 try-except，让 CLI 统一处理异常
```

**改进点**：
- ✅ 删除冗余 `_handle_error()` 函数
- ✅ 删除不必要的 try-except 块
- ✅ 添加结构化日志记录
- ✅ 代码行数减少 30%

---

### Services 层

#### Before (当前)
```python
# services/pr_service.py
def create_draft_pr(self, title: str, base_branch: str) -> PR:
    logger.info("Creating draft PR", title=title, base_branch=base_branch)

    try:
        pr = self.client.create_pr(...)
        logger.info("Draft PR created", pr_number=pr.number)
        return pr
    except GitHubError as e:
        logger.error("Failed to create PR", error=str(e))
        raise
```

#### After (迁移后)
```python
# services/pr_service.py
def create_draft_pr(self, title: str, base_branch: str) -> PR:
    # 结构化日志，便于 agent 追踪
    logger.bind(
        domain="pr",
        action="create_draft",
        title=title,
        base_branch=base_branch,
    ).info("Creating draft PR")

    try:
        pr = self.client.create_pr(...)

        # 成功日志
        logger.bind(pr_number=pr.number).success("Draft PR created")
        return pr

    except GitHubError as e:
        # 记录完整堆栈，便于调试
        logger.exception(f"Failed to create PR: {e}")
        raise
```

**改进点**：
- ✅ 使用 `logger.bind()` 结构化字段
- ✅ 使用 `logger.success()` 记录成功
- ✅ 使用 `logger.exception()` 记录完整堆栈
- ✅ 符合 [05-logging.md](docs/v3/infrastructure/05-logging.md) 规范

---

### Clients 层

#### Before (当前)
```python
# clients/github_client.py
def create_pr(self, title: str, base: str) -> PR:
    logger.debug(f"Creating PR: {title}")
    response = self._client.pulls.create(...)
    logger.debug(f"PR created: {response.number}")
    return PR.from_github(response)
```

#### After (迁移后)
```python
# clients/github_client.py
def create_pr(self, title: str, base: str) -> PR:
    logger.bind(
        external="github",
        operation="create_pr",
        repo=self.repo,
        title=title,
    ).debug("Calling GitHub API: create_pull_request")

    response = self._client.pulls.create(...)

    logger.bind(
        external="github",
        pr_number=response.number,
    ).debug("GitHub API call succeeded")

    return PR.from_github(response)
```

**改进点**：
- ✅ 标识外部系统（external 字段）
- ✅ 记录操作类型（operation 字段）
- ✅ 便于追踪外部依赖调用

---

## 🔍 验证清单

### 代码审查检查项

**Logger 使用**：
- [ ] 所有 logger 调用都使用 `bind()` 绑定结构化字段
- [ ] Services 层包含 `domain` 和 `action` 字段
- [ ] Clients 层包含 `external` 和 `operation` 字段
- [ ] Commands 层包含 `command` 字段
- [ ] 错误使用 `logger.exception()` 而非 `logger.error()`
- [ ] 成功操作使用 `logger.success()`

**Error 处理**：
- [ ] Commands 层无 `_handle_error()` 函数
- [ ] Commands 层无 try-except 块（除参数验证）
- [ ] Services 层异常向上抛出（raise）
- [ ] Services 层错误使用 `logger.exception()` 记录
- [ ] CLI 层统一处理所有异常

**Import 规范**：
- [ ] 所有文件 `from loguru import logger`
- [ ] CLI 入口 `from vibe3.observability import setup_logging`
- [ ] 无其他日志库导入（logging, print）

---

### 功能验证

**测试命令**：

```bash
# 1. 正常操作 - 应看到结构化日志
python -m vibe3.cli -vv pr draft --title "Test PR"

# 2. 错误处理 - 应看到完整堆栈
python -m vibe3.cli -vv pr show --pr-number 99999

# 3. 不同 verbosity 级别
python -m vibe3.cli pr draft        # ERROR only
python -m vibe3.cli -v pr draft     # INFO level
python -m vibe3.cli -vv pr draft    # DEBUG with location
```

**预期结果**：
- ✅ ERROR 级别只显示错误消息
- ✅ INFO 级别显示操作进展
- ✅ DEBUG 级别显示文件:行号:函数信息
- ✅ 所有日志包含结构化字段（在 DEBUG 模式下可见）

---

## 📊 影响评估

### 受影响文件统计

| 类别 | 文件数 | Logger 调用数 | 预计修改时间 |
|------|--------|---------------|--------------|
| Commands | 2 | 0（新增约 10） | 30 分钟 |
| Services | 5 | 42 | 1 小时 |
| Clients | 3 | 约 15 | 30 分钟 |
| 文档/测试 | 3 | - | 1 小时 |
| **总计** | **13** | **约 67** | **3 小时** |

### 风险评估

**低风险**：
- ✅ Logger 迁移不影响业务逻辑
- ✅ Error 处理简化降低代码复杂度
- ✅ 可逐步迁移，无需一次性完成

**潜在问题**：
- ⚠️ 日志格式变化可能影响现有日志解析工具
- ⚠️ 需要更新文档，避免开发者继续使用旧模式

**缓解措施**：
- 提供详细的迁移指南和示例
- 使用 lint 规则检测不符合规范的 logger 调用
- 在代码审查清单中添加检查项

---

## 📚 参考资料

### 内部文档
- [docs/v3/infrastructure/02-architecture.md](docs/v3/infrastructure/02-architecture.md) - 架构设计
- [docs/v3/infrastructure/05-logging.md](docs/v3/infrastructure/05-logging.md) - 日志规范
- [src/vibe3/observability/README.md](src/vibe3/observability/README.md) - Observability 模块使用指南
- [src/vibe3/exceptions/__init__.py](src/vibe3/exceptions/__init__.py) - 异常定义

### 外部资源
- [Loguru Documentation](https://loguru.readthedocs.io/) - Loguru 官方文档
- [Structured Logging Best Practices](https://www.honeycomb.io/blog/structured-logging-best-practices/) - 结构化日志最佳实践

---

## 🚀 执行计划

### 建议执行顺序

1. **Phase 1** (Commands 层简化) - 立即执行
   - 影响小，收益明显
   - 为后续迁移扫清障碍

2. **Phase 2** (Services 层规范化) - Phase 1 完成后
   - 核心迁移工作
   - 影响面最大，需要仔细测试

3. **Phase 3** (Clients 层规范化) - Phase 2 完成后
   - 补充外部依赖追踪
   - 优先级相对较低

4. **Phase 4** (文档和测试) - 与 Phase 2-3 并行
   - 确保规范可执行
   - 防止回归

### 验收标准

**完成条件**：
- ✅ 所有 4 个 Phase 任务清单打勾完成
- ✅ 验证清单所有项通过
- ✅ 功能验证测试全部通过
- ✅ 代码审查通过
- ✅ 文档更新完成

---

**维护者**: Vibe Team
**最后更新**: 2026-03-17
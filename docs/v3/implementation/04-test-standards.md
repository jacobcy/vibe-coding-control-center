---
document_type: implementation-guide
title: Vibe 3.0 - Test Standards
status: active
author: Claude Sonnet 4.6
created: 2026-03-16
last_updated: 2026-03-16
related_docs:
  - docs/v3/implementation/03-coding-standards.md
  - docs/v3/implementation/02-architecture.md
---

# Vibe 3.0 - 测试标准

本文档定义 Vibe 3.0 的测试标准，包括测试分层、复杂度控制、覆盖率要求、Mock 规范等。

---

## 测试哲学

### 核心原则

1. **测试即文档**：测试代码是活文档，必须清晰、简洁、易读
2. **隔离为王**：每个测试必须独立，不依赖执行顺序
3. **快速反馈**：测试套件必须在 30 秒内完成
4. **最小化维护**：测试代码 < 生产代码的 50%

---

## 测试分层（强制）

### 分层原则

测试按架构分层组织，每层有明确的职责和限制：

| 测试层级 | 职责 | 文件最大行数 | 单个测试函数最大行数 | 强制程度 |
|---------|------|------------|-------------------|----------|
| Commands | 测试参数解析、UI 输出 | < 80 行 | < 30 行 | **必须** |
| Services | 测试业务逻辑、状态转换 | < 180 行 | < 50 行 | **必须** |
| Clients | 测试外部系统交互（Mock） | < 100 行 | < 40 行 | **必须** |

### 禁止事项

- ❌ **跨层测试**：Command 测试不应直接测试 Service 逻辑
- ❌ **集成测试混入单元测试**：单元测试文件中不应包含真实外部调用
- ❌ **测试业务逻辑在 Commands 层**：业务逻辑测试应在 Services 层

---

## 测试复杂度控制（强制）

### 文件规模限制

**测试代码应该简洁，不得超过以下限制：**

```
单个测试文件 < 180 行（Services 层）
单个测试文件 < 80 行（Commands 层）
单个测试文件 < 100 行（Clients 层）
```

### 测试函数规模限制

```
单个测试函数 < 50 行（Services 层）
单个测试函数 < 30 行（Commands 层）
单个测试函数 < 40 行（Clients 层）
```

### 复杂度限制

- **禁止**：单个测试文件超过 10 个测试函数（应拆分为多个测试类）
- **禁止**：嵌套超过 2 层（fixture 嵌套、条件嵌套）
- **禁止**：单个 fixture 超过 30 行

### 重构示例

```python
# ❌ 错误：测试文件太重（超过 180 行）
# tests/vibe3/services/test_flow_service.py (250+ lines)
class TestFlowService:
    def test_create_flow_1(self): ...
    def test_create_flow_2(self): ...
    # ... 12+ test functions in one class

# ✅ 正确：按场景拆分为多个文件
# tests/vibe3/services/test_flow_creation.py (90 lines)
class TestFlowCreation:
    def test_create_flow_success(self): ...
    def test_create_flow_duplicate_fails(self): ...

# tests/vibe3/services/test_flow_binding.py (85 lines)
class TestFlowBinding:
    def test_bind_task_success(self): ...
    def test_bind_task_already_bound(self): ...
```

---

## 测试覆盖率（强制）

### 覆盖率要求

| 层级 | 最低覆盖率 | 核心路径覆盖率 | 强制程度 |
|------|----------|--------------|----------|
| Services | >= 80% | 100% | **必须** |
| Clients | >= 70% | 100% | **必须** |
| Commands | >= 60% | 80% | **必须** |

### 核心路径定义

**核心路径包括：**
1. 正常流程（Happy Path）
2. 已知错误场景（Expected Errors）
3. 边界条件（Edge Cases）

**非核心路径包括：**
1. 防御性代码（Defensive Code）
2. 调试辅助代码（Debug Helpers）

### 覆盖率检查

```bash
# 运行测试并生成覆盖率报告
uv run pytest tests/ --cov=scripts/python/vibe3 --cov-report=term-missing

# 检查覆盖率阈值
uv run pytest tests/ --cov=scripts/python/vibe3 --cov-fail-under=80
```

---

## Mock 使用规范（强制）

### 必须使用 Mock 的场景

1. **GitHub API 调用**：禁止在测试中发起真实 API 请求
2. **Git 操作**：禁止在测试中执行真实 Git 命令
3. **文件系统操作**：使用 `tmp_path` fixture
4. **网络请求**：禁止在测试中发起真实网络请求

### Mock 模式

#### Protocol-Based Mock

```python
# ✅ 正确：使用 Protocol 定义接口
# scripts/python/vibe3/clients/github_client.py
from typing import Protocol

class GitHubClientProtocol(Protocol):
    def create_pr(self, title: str, body: str, draft: bool) -> dict:
        ...

# tests/vibe3/clients/test_github_client.py
class MockGitHubClient:
    def create_pr(self, title: str, body: str, draft: bool) -> dict:
        return {"number": 123, "html_url": "https://github.com/owner/repo/pull/123"}

def test_create_pr():
    client = MockGitHubClient()
    result = client.create_pr("Test PR", "Body", draft=True)
    assert result["number"] == 123
```

#### Fixture-Based Mock

```python
# ✅ 正确：使用 pytest fixture
# tests/conftest.py
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_git_client():
    client = Mock()
    client.get_current_branch.return_value = "feature/test"
    client.get_remote_url.return_value = "git@github.com:owner/repo.git"
    return client

# tests/vibe3/services/test_flow_service.py
def test_create_flow(mock_git_client):
    service = FlowService(git_client=mock_git_client)
    result = service.create_flow("test-flow")
    assert result.success
```

### 禁止事项

- ❌ **硬编码 Mock 数据**：应在 fixture 或测试数据文件中管理
- ❌ **过度 Mock**：不 Mock 简单的数据结构（如 dict、list）
- ❌ **Mock 私有方法**：只 Mock 公共接口

---

## 测试命名规范（强制）

### 测试文件命名

```
test_<module_name>.py
```

示例：
- `test_flow_service.py` - 测试 `flow_service.py`
- `test_git_client.py` - 测试 `git_client.py`

### 测试类命名

```python
class Test<FeatureName>:
    ...
```

示例：
- `class TestFlowCreation:` - 测试 Flow 创建功能
- `class TestPRBinding:` - 测试 PR 绑定功能

### 测试函数命名

```python
def test_<action>_<condition>():
    ...
```

示例：
- `def test_create_flow_success():` - 测试成功创建 Flow
- `def test_create_flow_duplicate_fails():` - 测试重复创建失败
- `def test_bind_task_when_flow_not_found():` - 测试 Flow 不存在时的行为

---

## 测试数据管理（强制）

### 测试数据位置

```
tests/
├── fixtures/                      # 共享测试数据
│   ├── github_responses/          # GitHub API 响应数据
│   │   ├── pr_created.json
│   │   └── pr_merged.json
│   └── git_states/                # Git 状态快照
│       ├── clean_state.json
│       └── dirty_state.json
└── conftest.py                    # 共享 fixtures
```

### 测试数据格式

**优先使用 JSON 格式存储测试数据：**

```json
// tests/fixtures/github_responses/pr_created.json
{
  "number": 123,
  "html_url": "https://github.com/owner/repo/pull/123",
  "state": "open",
  "draft": true,
  "title": "Test PR",
  "body": "Test body"
}
```

**在测试中使用：**

```python
# tests/conftest.py
import pytest
import json
from pathlib import Path

@pytest.fixture
def pr_created_response():
    data_path = Path(__file__).parent / "fixtures" / "github_responses" / "pr_created.json"
    return json.loads(data_path.read_text())
```

---

## 测试执行标准（强制）

### 测试速度要求

- **单元测试套件**：< 10 秒
- **完整测试套件**：< 30 秒
- **单个测试**：< 1 秒

### 测试标记

使用 pytest marker 标记测试类型：

```python
import pytest

@pytest.mark.unit
def test_create_flow_success():
    ...

@pytest.mark.integration
def test_real_github_api_call():
    """使用真实 GitHub API（仅用于集成测试）"""
    ...

@pytest.mark.slow
def test_large_dataset_processing():
    """处理大数据集（耗时 > 1 秒）"""
    ...
```

### 测试执行命令

```bash
# 运行所有单元测试
uv run pytest tests/ -m unit

# 运行集成测试（需要外部依赖）
uv run pytest tests/ -m integration

# 跳过慢速测试
uv run pytest tests/ -m "not slow"

# 运行指定文件的测试
uv run pytest tests/vibe3/services/test_flow_service.py -v
```

---

## 测试代码质量（强制）

### AAA 模式

**所有测试必须遵循 Arrange-Act-Assert 模式：**

```python
def test_create_flow_success(mock_git_client):
    # Arrange - 准备测试数据和环境
    service = FlowService(git_client=mock_git_client)
    flow_name = "test-flow"

    # Act - 执行被测试的操作
    result = service.create_flow(flow_name)

    # Assert - 验证结果
    assert result.success
    assert result.flow_slug == flow_name
```

### 单一职责

**每个测试只验证一个行为：**

```python
# ❌ 错误：一个测试验证多个行为
def test_flow_lifecycle():
    result1 = service.create_flow("test")
    assert result1.success

    result2 = service.bind_task("test", 123)
    assert result2.success

    result3 = service.close_flow("test")
    assert result3.success

# ✅ 正确：拆分为多个测试
def test_create_flow_success():
    result = service.create_flow("test")
    assert result.success

def test_bind_task_success():
    service.create_flow("test")
    result = service.bind_task("test", 123)
    assert result.success
```

### 避免魔法数字

```python
# ❌ 错误：使用魔法数字
def test_create_pr():
    result = service.create_pr(123, "title")
    assert result.number == 456

# ✅ 正确：使用常量
ISSUE_NUMBER = 123
EXPECTED_PR_NUMBER = 456

def test_create_pr():
    result = service.create_pr(ISSUE_NUMBER, "title")
    assert result.number == EXPECTED_PR_NUMBER
```

---

## 测试审查检查清单

### 代码规模

- [ ] 测试文件 < 最大行数限制（Services: 150 行，Commands: 80 行，Clients: 100 行）
- [ ] 单个测试函数 < 最大行数限制（Services: 50 行，Commands: 30 行，Clients: 40 行）
- [ ] 单个测试文件 < 10 个测试函数

### 测试质量

- [ ] 遵循 AAA 模式（Arrange-Act-Assert）
- [ ] 每个测试只验证一个行为
- [ ] 使用有意义的测试名称
- [ ] 不使用魔法数字

### Mock 使用

- [ ] 外部依赖已 Mock
- [ ] Mock 数据在 fixtures 中管理
- [ ] 使用 Protocol 定义接口

### 覆盖率

- [ ] 测试覆盖率 >= 最低要求
- [ ] 核心路径 100% 覆盖
- [ ] 边界条件有测试

### 测试速度

- [ ] 单元测试套件 < 10 秒
- [ ] 完整测试套件 < 30 秒
- [ ] 单个测试 < 1 秒

---

## 示例：标准测试文件

### Services 层示例

```python
# tests/vibe3/services/test_flow_service.py
"""FlowService 单元测试"""
import pytest
from unittest.mock import Mock
from vibe3.services.flow_service import FlowService
from vibe3.clients.git_client import GitClientProtocol

# 测试常量
FLOW_NAME = "test-flow"
BRANCH_NAME = "feature/test-flow"
TASK_ISSUE = 123


class TestFlowCreation:
    """Flow 创建功能测试"""

    @pytest.fixture
    def mock_git_client(self) -> GitClientProtocol:
        """Mock Git 客户端"""
        client = Mock(spec=GitClientProtocol)
        client.get_current_branch.return_value = BRANCH_NAME
        return client

    @pytest.fixture
    def mock_store(self):
        """Mock Vibe3Store"""
        store = Mock()
        store.get_flow_state.return_value = None
        return store

    def test_create_flow_success(self, mock_git_client, mock_store):
        """测试成功创建 Flow"""
        # Arrange
        service = FlowService(git_client=mock_git_client, store=mock_store)

        # Act
        result = service.create_flow(FLOW_NAME)

        # Assert
        assert result.success
        assert result.flow_slug == FLOW_NAME
        mock_store.update_flow_state.assert_called_once()

    def test_create_flow_duplicate_fails(self, mock_git_client, mock_store):
        """测试重复创建 Flow 失败"""
        # Arrange
        mock_store.get_flow_state.return_value = {"branch": BRANCH_NAME}
        service = FlowService(git_client=mock_git_client, store=mock_store)

        # Act & Assert
        with pytest.raises(ValueError, match="Flow already exists"):
            service.create_flow(FLOW_NAME)
```

### Commands 层示例

```python
# tests/vibe3/commands/test_flow.py
"""Flow 命令测试"""
import pytest
from typer.testing import CliRunner
from vibe3.commands.flow import app

runner = CliRunner()


class TestFlowNew:
    """flow new 命令测试"""

    def test_flow_new_success(self, mock_flow_service):
        """测试成功创建 Flow"""
        # Act
        result = runner.invoke(app, ["new", "test-flow"])

        # Assert
        assert result.exit_code == 0
        assert "Flow created" in result.stdout

    def test_flow_new_without_name_fails(self):
        """测试缺少 Flow 名称失败"""
        # Act
        result = runner.invoke(app, ["new"])

        # Assert
        assert result.exit_code != 0
```

---

## 参考文档

- **[03-coding-standards.md](03-coding-standards.md)** - 编码标准
- **[02-architecture.md](02-architecture.md)** - 架构设计
- **[pytest 文档](https://docs.pytest.org/)** - pytest 官方文档
- **[unittest.mock 文档](https://docs.python.org/3/library/unittest.mock.html)** - Mock 官方文档

---

**维护者**：Vibe Team
**最后更新**：2026-03-16
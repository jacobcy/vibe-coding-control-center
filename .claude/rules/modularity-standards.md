# Modularity Standards

本文件定义 Vibe 3.0 的模块化要求，覆盖公开 API 导出、导入路径和模块设计。

## 公开 API 原则（强制）

所有跨模块导入**必须**通过目标包的公开 API（`__init__` 导出），禁止深层导入。

```python
# ✅ 正确：从公开 API 导入
from vibe3.roles import MANAGER_ROLE, build_manager_request

# ❌ 错误：深层导入绕过 __init__
from vibe3.roles.manager import MANAGER_ROLE
from vibe3.roles.definitions import RoleDefinition
```

**理由**：
- 公开 API 是包的契约，深层路径是实现细节
- `__init__` 可以做 lazy import 避免循环依赖
- 重构子模块时只需更新 `__init__`，不影响消费者

## `__all__` 导出规范（强制）

每个包的 `__init__.py` 必须定义 `__all__`，且满足：

1. **完整性**：`__all__` 必须包含所有子模块的公共符号
2. **一致性**：添加新符号时必须同时更新 `__all__` 和 `_LAZY_IMPORTS`
3. **无遗漏**：`test_no_missing_exports` 测试会验证 `__all__` 与实际导入的一致性

## 允许的导出类型（强制）

`__all__` 中的符号必须是以下类型之一：

| 类型 | 示例 | 说明 |
|------|------|------|
| callable | `build_manager_request()` | 函数、类构造器 |
| dataclass 实例 | `MANAGER_ROLE` | 领域单例（RoleDefinition 等） |
| Pydantic model 实例 | `DEFAULT_COMMENT_POLICY` | 配置对象 |
| 模块 re-export | `vibe3.commands.flow` | barrel export |
| 基础类型 | `str`, `int`, `dict` | 配置值、常量 |
| 容器 | `set`, `frozenset` | 配置集合 |
| Path/Pattern | `PosixPath`, `re.Pattern` | 路径/正则实例 |
| 类型标注 | `UnionType` | 类型语法导出 |

**禁止导出**：裸实例（非 dataclass/Pydantic）、数据库连接、HTTP 客户端等有副作用的对象。

如果确实需要导出一个不匹配以上模式的对象，必须：
1. 优先考虑重构为 callable（工厂函数、classmethod）
2. 若无法重构，在 `_DOCUMENTED_EXCEPTIONS` 中注册并写明理由

## Lazy Import 模式（强制）

为了避免循环依赖，`__init__` 必须使用 lazy import：

```python
_LAZY_IMPORTS: dict[str, str] = {
    "MANAGER_ROLE": "vibe3.roles.manager",
    "build_manager_request": "vibe3.roles.manager",
}

def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value  # cache
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**关键要求**：
- `_LAZY_IMPORTS` 必须与 `__all__` 完全一致（`__init__` 末尾有 assert 校验）
- `TYPE_CHECKING` 块中导入所有符号供 mypy 使用
- 使用 `globals()[name] = value` 缓存避免重复导入（但注意不要影响 mock patching）

## Singleton 导出规范

预构建的领域对象（如 `MANAGER_ROLE`、`PLANNER_ROLE`）是合法的单例导出：

```python
# vibe3/roles/manager.py
MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager",
    trigger_name=TriggerName.ISSUE_ASSIGNED,
    trigger_state=FlowState.CLAIMED,
    ...
)
```

**要求**：
- 单例必须是 dataclass 或 Pydantic model 实例
- 不可变优先：使用 `frozen=True`（dataclass）或 Pydantic 的 `model_config = ConfigDict(frozen=True)`
- 单例不应持有外部资源（数据库连接、HTTP 会话）

## Barrel Export 模式

包的 `__init__` 可以重新导出子模块符号。当前项目有 14 个 module re-export：

- `vibe3.commands`：10 个子模块（ask, check, flow, handoff, inspect, plan, pr, review, run, snapshot）
- `vibe3.analysis`：4 个子模块（command_analyzer, dag_service, snapshot_service, structure_service）

**要求**：
- 只重新导出本包内的子模块
- 不跨包重新导出（如不在 `commands/__init__` 中导出 `services` 的符号）
- 子模块本身作为 module 类型通过 `_is_legitimate_export` 的 `ModuleType` 检查

## 模块化测试

运行 modularity 测试：

```bash
uv run pytest tests/vibe3/test_modularity/ -v
```

测试覆盖：
- `test_all_modules_have_all_defined` — 所有包都有 `__all__`
- `test_all_exports_are_importable` — 所有导出都可以正常 import
- `test_all_exports_are_callable_or_type` — 所有导出符合允许的类型模式
- `test_no_missing_exports` — `__all__` 与实际导入一致

## 参考

- PR #2503: 从硬编码 allowlist 迁移到语义模式检查
- PR #2482: 统一替换深层导入为顶层模块导入

# Exceptions

统一异常层级与错误追踪，所有 vibe3 异常从 VibeError 派生。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| error_codes.py | 37 | 错误码常量定义 |
| error_classification.py | 87 | classify_error 函数，错误分类 |
| __init__.py | 208 | 异常层级定义，基类和派生类 |
| error_tracking.py | 231 | ErrorTrackingService，错误持久化 |

截至 2026-05，总计约 563 行。

## 职责

- 定义异常基类 VibeError（含 recoverable 标志）
- 分类异常：UserError, ConfigError, GitError, GitHubError, SerenaError, SystemError
- 错误码常量定义和分类
- 错误追踪和持久化（SQLite）
- 支持 CLI 层统一错误展示

## 异常层级

```
VibeError (base, recoverable=True)
+-- UserError          用户操作不符
+-- ConfigError        配置错误
+-- GitError           Git 操作失败
+-- GitHubError        GitHub API 错误
+-- SerenaError        Serena 分析失败
+-- SystemError        系统故障(recoverable=False)
```

## 模块职责

### __init__.py
异常层级定义：
- **VibeError**: 基类，提供 recoverable 标志和 message
- **UserError**: 用户操作错误（如参数缺失、操作冲突）
- **ConfigError**: 配置错误（如文件缺失、格式错误）
- **GitError**: Git 操作错误（如分支不存在、冲突）
- **GitHubError**: GitHub API 错误（如认证失败、rate limit）
- **SerenaError**: Serena 分析错误
- **SystemError**: 系统级错误（不可恢复）

### error_codes.py
错误码常量：
- 定义 API 错误码（如 `E001`, `E002`）
- 定义模型错误码
- 提供 `is_api_error()`, `is_model_error()` 分类函数

### error_classification.py
错误分类函数：
- **classify_error()**: 将异常映射到错误码
- 支持自定义分类规则
- 提供错误严重级别判断

### error_tracking.py
错误追踪服务：
- **ErrorTrackingService**: 错误持久化和查询
- 使用 SQLite 存储错误记录
- 支持错误统计和分析
- 提供错误历史查询

核心方法：
- `track_error()`: 记录错误
- `get_error_history()`: 查询历史
- `get_error_stats()`: 统计分析

## 依赖关系

```
exceptions/
├── __init__.py → （无内部依赖）
├── error_codes.py → （无内部依赖）
├── error_classification.py → error_codes
└── error_tracking.py → clients/SQLiteClient, error_codes
```

**外部依赖**:
- loguru: 日志记录
- vibe3.clients.SQLiteClient: 错误持久化（**设计例外**）

**被依赖**:
- 所有模块（使用 VibeError 及其派生类）

## 架构问题说明

### exceptions → clients 依赖

**发现**: `error_tracking.py` 导入 `vibe3.clients.SQLiteClient`

**问题**: exceptions 作为基础层，理论上不应依赖 clients 模块，这违反了分层原则。clients 是更上层的实现层，负责外部服务访问。

**原因**: ErrorTrackingService 需要持久化错误记录，直接使用了 SQLiteClient。

**影响**: 
- exceptions 模块无法独立使用
- 测试时需要 mock clients 模块
- 循环依赖风险（如果 clients 也使用 exceptions）

**处理**: 标注为"设计例外"，暂不强制重构。后续架构治理时可评估：
1. 将错误追踪下沉到独立的 storage 模块
2. 或将 SQLiteClient 的基础功能提取到更底层

**记录**: 已通过 handoff 记录此发现。

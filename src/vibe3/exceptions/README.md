# Exceptions

统一异常层级与错误追踪，所有 vibe3 异常从 VibeError 派生。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 298 | 异常层级定义，基类和派生类 |
| error_classification.py | 470 | classify_error_hybrid，错误分类函数 |
| diagnostics.py | 31 | format_diagnostic_message，诊断消息格式化 |
| error_codes.py | 64 | 错误码常量定义 |
| error_severity.py | 71 | ErrorSeverity 枚举，ErrorHandlingContract |
| git_error_patterns.py | 36 | TRANSIENT_GIT_ERROR_PATTERNS，is_transient_git_error |
| runtime_errors.py | 67 | GitHubAPIError，运行时错误 |

截至 2026-06，总计约 1037 行。

## 职责

- 定义异常基类 VibeError（含 recoverable 标志）
- 分类异常：UserError, SystemError, BusinessError, OrchestrationError
- 错误码常量定义和分类（error_codes.py）
- 错误分类函数（error_classification.py）
- 错误严重级别和处置契约（error_severity.py）
- Git 错误模式识别（git_error_patterns.py）
- 诊断消息格式化（diagnostics.py）
- 支持 CLI 层统一错误展示

## 公开 API

`__init__.py` 导出以下 30 个符号：

### 异常基类

- **VibeError**: 所有 Vibe 异常的基类，提供 `recoverable` 标志和 `message` 属性
- **UserError**: 用户输入错误（可恢复），recoverable=True
- **SystemError**: 系统级错误（不可恢复），recoverable=False

### 用户异常

- **ConfigError**: 配置文件或设置错误
- **AgentPresetNotFoundError**: Agent preset 未在 config/v3/models.json 中找到
- **SkillNotAvailableError**: Skill 不可用 — 当前 profile 无 adapter 提供该 skill
- **MissingResourceError**: 缺失配置或运行时资源，带诊断上下文
- **DiagnosticContext**: MissingResourceError 的诊断上下文（dataclass）

### 系统异常

- **AgentExecutionError**: Agent 执行失败（wrapper/API/backend 错误）
- **ModelsJsonSyncError**: 无法同步 ~/.codeagent/models.json
- **GitError**: Git 操作失败
- **GitHubError**: GitHub API 错误
- **SerenaError**: Serena 代码分析错误

### 编排异常

- **InvalidTransitionError**: Orchestration 状态机无效状态转换
- **InvalidBranchLinkError**: Base branch 非法链接到 issue（数据完整性错误）
- **CapacityDeferredError**: 因容量限制延迟 dispatch（可恢复）

### 业务异常

- **PRNotFoundError**: PR 不存在

### 运行时错误

- **GitHubAPIError**: GitHub API 运行时错误

### 错误码

- **E_AUP_REJECTION**: AUP 拒绝错误码（内容策略违规）
- **E_EXEC_AUTO_SCENE_RESET**: 自动场景重置错误码
- **E_ISSUE_FAILED**: Issue 失败错误码

### 错误工具函数

- **classify_error_hybrid**: 混合错误分类函数，将异常映射到错误码
- **is_permanent_code_error**: 判断是否为永久性代码错误
- **get_error_handling_contract**: 获取错误处置契约
- **is_api_error**: 判断是否为 API 错误
- **is_model_error**: 判断是否为模型错误
- **is_transient_git_error**: 判断是否为瞬态 Git 错误

### 类型/枚举

- **ErrorHandlingContract**: 错误处置契约（Pydantic model）
- **ErrorSeverity**: 错误严重级别枚举

### 常量

- **TRANSIENT_GIT_ERROR_PATTERNS**: 瞬态 Git 错误模式列表

## 异常层级

```
VibeError (base)
+-- UserError (recoverable=True)
|   +-- ConfigError
|   +-- AgentPresetNotFoundError
|   +-- SkillNotAvailableError
|   +-- MissingResourceError
|   +-- InvalidTransitionError
+-- SystemError (recoverable=False)
|   +-- AgentExecutionError
|   +-- ModelsJsonSyncError
|   +-- GitError
|   +-- GitHubError
|   +-- SerenaError
|   +-- InvalidBranchLinkError
+-- VibeError (业务/编排错误)
    +-- PRNotFoundError (recoverable=False)
    +-- CapacityDeferredError (recoverable=True)
```

## 模块职责

### __init__.py

异常层级定义：
- **VibeError**: 基类，提供 `recoverable` 标志和 `message`
- **UserError**: 用户操作错误（可恢复）
- **SystemError**: 系统级错误（不可恢复）
- **DiagnosticContext**: MissingResourceError 的诊断上下文（dataclass）
- 业务异常和编排异常的定义

### error_codes.py

错误码常量：
- 定义配置错误码（`E_CONFIG_MISSING`）
- 定义模型错误码（`E_MODEL_NOT_FOUND`, `E_MODEL_PERMISSION`, `E_MODEL_CONFIG`）
- 定义 API 错误码（`E_API_RATE_LIMIT`, `E_API_TIMEOUT`, `E_API_UNAVAILABLE`, `E_API_NETWORK`, `E_API_UNKNOWN`）
- 定义执行错误码（`E_EXEC_NO_OUTPUT`, `E_EXEC_INVALID_HANDOFF`, `E_EXEC_AUTO_SCENE_RESET` 等）
- 定义业务错误码（`E_AUP_REJECTION`, `E_ISSUE_FAILED`, `E_TEST_ARTIFACT_LEAK` 等）
- 提供 `is_api_error()`, `is_model_error()`, `is_exec_error()` 分类函数

### error_classification.py

错误分类函数：
- **classify_error_hybrid()**: 将异常映射到错误码
- **is_permanent_code_error()**: 判断是否为永久性代码错误
- **get_error_handling_contract()**: 获取错误处置契约（基于错误码）
- 支持自定义分类规则

### error_severity.py

错误严重级别和处置契约：
- **ErrorSeverity**: 错误严重级别枚举（WARNING, ERROR, CRITICAL）
- **ErrorHandlingContract**: 错误处置契约（是否立即 failed gate、是否记录到 error_log 等）

### git_error_patterns.py

Git 错误模式识别：
- **TRANSIENT_GIT_ERROR_PATTERNS**: 瞬态 Git 错误模式列表
- **is_transient_git_error()**: 判断 Git 错误是否为瞬态（可重试）

### diagnostics.py

诊断消息格式化：
- **format_diagnostic_message()**: 格式化用户友好的诊断消息（用于 MissingResourceError）

### runtime_errors.py

运行时错误：
- **GitHubAPIError**: GitHub API 运行时错误

## 依赖关系

```
exceptions/
├── __init__.py → diagnostics.py (format_diagnostic_message)
├── error_classification.py → error_codes.py (错误码引用)
├── diagnostics.py → (无内部依赖)
├── error_codes.py → (无内部依赖)
├── error_severity.py → (无内部依赖)
├── git_error_patterns.py → (无内部依赖)
└── runtime_errors.py → (无内部依赖)
```

**外部依赖**:
- loguru: 日志记录（error_classification.py 使用）

**被依赖**:
- ~142 个文件引用，覆盖 agents/analysis/clients/commands/config/domain/environment/execution/models/prompts/roles/services/utils 等几乎所有模块

## 架构说明

### 分层设计

exceptions 作为基础层，不依赖其他 vibe3 业务模块：

1. **纯数据定义**: error_codes.py, error_severity.py, git_error_patterns.py
2. **工具函数**: error_classification.py, diagnostics.py
3. **异常类型**: __init__.py, runtime_errors.py

### 错误追踪迁移

**历史变更**：error_tracking.py 已迁移至 services/orchestra/error_recording.py 和 services/shared/errors.py

**原因**：错误追踪服务需要访问 SQLite 持久化层，放在 exceptions 模块违反分层原则

**影响**：exceptions 模块现在保持纯异常定义，不再依赖 clients 模块

## 设计原则

- **统一基类**: 所有异常继承 VibeError，支持 CLI 层统一处理
- **可恢复性**: 通过 `recoverable` 标志区分用户可修复错误和系统错误
- **分类清晰**: UserError（可恢复）、SystemError（不可恢复）、业务异常（按需）
- **诊断友好**: MissingResourceError 提供详细的搜索路径和修复建议
- **错误码系统**: 支持基于错误码的分类和处置策略

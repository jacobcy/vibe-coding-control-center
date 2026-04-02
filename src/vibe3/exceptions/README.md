# Exceptions

统一异常层级，所有 vibe3 异常从 VibeError 派生。

## 职责

- 定义异常基类 VibeError（含 recoverable 标志）
- 分类异常：UserError, ConfigError, GitError, GitHubError, SerenaError, SystemError
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

## 依赖关系

- 依赖: (无)
- 被依赖: 所有模块

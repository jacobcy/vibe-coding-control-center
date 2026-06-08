# Utils

通用工具函数，提供 Git 操作、路径解析、issue 引用解析等基础能力。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| codeagent_helpers.py | 226 | Codeagent 后端辅助（错误诊断、输出摘要、prompt 文件准备） |
| branch_utils.py | 109 | Branch 父分支查找算法 |
| git_helpers.py | 104 | Handoff 目录计算、commit message、current branch |
| constants.py | 105 | 常量定义（默认路径、后缀等） |
| issue_branch_resolver.py | 41 | Issue 到分支的解析和转换 |
| trace.py | 36 | Trace 工具函数 |
| issue_ref.py | 14 | Issue 引用解析（#123, owner/repo#123） |
| actor_utils.py | - | Actor 名称规范化 |
| time_format.py | - | 时间格式化 |
| error_message_cleaner.py | - | 错误消息清理 |

## 关键组件

### Git 操作
- **git_helpers.py**: Handoff 目录计算、commit message、current branch
- **branch_utils.py**: Branch 父分支查找

### 其他工具
- **codeagent_helpers.py**: Codeagent 后端辅助
- **constants.py**: 常量定义

## 依赖关系

```
utils/
├── 无外部依赖：branch_utils, git_helpers, constants, trace, issue_ref, actor_utils, time_format, error_message_cleaner
└── 独立配置：codeagent_helpers (依赖 VibeConfig)
```

**被依赖**:
- services/ (广泛使用 git_helpers)
- commands/ (使用 git_helpers, branch_utils)

## 已迁移模块

以下模块已迁移到 `services/` 目录：

| 模块 | 新位置 | 原因 |
|------|--------|------|
| git_path_client.py | services/ | 依赖 GitClient |
| path_helpers.py | services/ | 业务逻辑，依赖 git_path_client |
| handoff_resolution.py | services/ | 业务逻辑，依赖 git_path_client |
| branch_arg.py | services/ | 业务逻辑，依赖 GitClient, FlowService |
| pr_branch_resolver.py | services/ | 业务逻辑，依赖 GitHubClient, FlowService |
| label_utils.py | services/ | 业务逻辑 |

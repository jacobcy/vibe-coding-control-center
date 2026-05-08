# Utils

通用工具函数，提供 Git 操作、路径解析、issue 引用解析等基础能力。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| git_path_client.py | 60 | GitPathProtocol 和路径相关 Git wrapper 函数 |
| path_helpers.py | 433 | 路径解析、handoff 路径解析 |
| codeagent_helpers.py | 226 | Codeagent 后端辅助（错误诊断、输出摘要、prompt 文件准备） |
| branch_utils.py | 109 | Branch 父分支查找算法 |
| git_helpers.py | 104 | Handoff 目录计算、commit message、current branch |
| constants.py | 105 | 常量定义（默认路径、后缀等） |
| comment_utils.py | 80 | Comment 格式化工具 |
| label_utils.py | 85 | Label 操作工具 |
| issue_branch_resolver.py | 41 | Issue 到分支的解析和转换 |
| trace.py | 36 | Trace 工具函数 |
| issue_ref.py | 14 | Issue 引用解析（#123, owner/repo#123） |

## 关键组件

### Git 操作
- **git_path_client.py**: GitPathProtocol 和路径相关 Git wrapper 函数
- **git_helpers.py**: Handoff 目录计算、commit message、current branch
- **branch_utils.py**: Branch 父分支查找

### 路径解析
- **path_helpers.py**: 引用路径解析、handoff 路径解析

### 其他工具
- **codeagent_helpers.py**: Codeagent 后端辅助
- **constants.py**: 常量定义
- **comment_utils.py**: Comment 格式化
- **label_utils.py**: Label 操作

## 依赖关系

```
utils/
├── 无内部依赖：branch_utils, git_helpers, constants, comment_utils, label_utils, trace, issue_ref
├── 独立配置：codeagent_helpers (依赖 VibeConfig)
└── Git 相关：git_path_client (依赖 GitClient), path_helpers (依赖 git_path_client)
```

**被依赖**:
- services/ (广泛使用 path_helpers, git_helpers)
- commands/ (使用 path_helpers, git_helpers, branch_utils)
- ui/ (使用 path_helpers)

## 架构说明

### git_path_client.py 职责

该文件提供 Git 路径操作的 Protocol 和包装函数：

1. **GitPathProtocol**: 定义路径相关 Git 操作的 Protocol
2. **Git wrapper 函数**: get_git_common_dir, get_worktree_root, find_worktree_path_for_branch

### path_helpers.py 职责

该文件专注于路径解析功能：

1. **路径解析**: resolve_ref_path, check_ref_exists, resolve_handoff_target 等核心函数
2. **Handoff 路径处理**: is_shared_handoff_ref, to_display_target, ref_to_handoff_cmd

**注意**: GitClientProtocol 在 `git_client.py` 中也有定义（用于代码变更操作），两者方法不同但名称相同。为避免混淆，新的 GitPathProtocol 专门用于路径操作。

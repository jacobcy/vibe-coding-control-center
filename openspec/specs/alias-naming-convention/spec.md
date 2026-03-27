## ADDED Requirements

### Requirement: Prefix族定义
所有用户可见的 lib/alias/function 命令 SHALL 遵循 `<工具前缀><动作>` 的命名模式，前缀族与对应工具的映射关系 SHALL 在此 spec 中定义并强制执行。

已定义的前缀族：

| 前缀 | 工具/领域 | 示例 |
|------|----------|------|
| `vt` | tmux 会话管理 | `vt`, `vtls`, `vtup`, `vtdown`, `vtkill` |
| `wt` | git worktree | `wt`, `wtls`, `wtnew`, `wtrm`, `wtinit` |
| `cc` | Claude CLI | `ccy`, `ccp`, `ccs`, `ccwt`, `cccn`, `ccoff`, `ccep` |
| `oo` | OpenCode | `oo`, `ooa`, `oowt` |
| `os` | OpenSpec | `os`, `osi`, `osl`, `osv`, `osn`, `osval` |
| `v`  | Vibe 综合命令 | `vibe`, `vup`, `vnew`, `vc`, `vsign`, `vmain` |
| `lg` | lazygit（单独） | `lg` |

#### Scenario: 新命令名称合规
- **WHEN** 开发者向 `config/aliases/` 中添加新命令
- **THEN** 命令名 SHALL 以上表中已定义前缀之一开头，否则需先在此 spec 中登记新前缀

### Requirement: 无下划线分隔符
同一前缀族内的命令 SHALL 使用连写（无分隔符）风格，不得使用下划线连接前缀与动作部分。

**例外**：跨族组合词（如 `ccwt` = Claude + Worktree）视为单一连写命令，不受此限制。

#### Scenario: Claude 命令分隔符检查
- **WHEN** 执行 `grep -E "^(alias |function )cc_" config/aliases/claude.sh`
- **THEN** 输出 SHALL 为空（无以 `cc_` 开头的用户命令定义）

#### Scenario: OpenCode 命令分隔符检查
- **WHEN** 执行 `grep -E "^(alias |function )oo_" config/aliases/opencode.sh`
- **THEN** 输出 SHALL 为空（无以 `oo_` 开头的用户命令定义）

### Requirement: 动作后缀语义约定
动作后缀 SHALL 具有一致语义，相同后缀在不同前缀族中含义相同。

已定义的动作后缀：

| 后缀 | 语义 | 出现于 |
|------|------|--------|
| `ls` | 列出资源 | `vtls`, `wtls` |
| `new` | 创建资源 | `wtnew`, `vnew` |
| `rm` | 删除资源 | `wtrm` |
| `up` | 启动/附加 | `vtup`, `vup` |
| `down` | 分离/关闭 | `vtdown` |
| `kill` | 强制终止 | `vtkill` |
| `init` | 初始化状态 | `wtinit` |
| `wt` | 在 worktree 中执行 | `ccwt`, `oowt` |
| `ep` | endpoint 操作 | `ccep` |
| `s` | safe 安全模式 | `ccs` |

#### Scenario: 动作语义验证
- **WHEN** 新命令使用已有动作后缀（如 `ls`、`new`、`rm`）
- **THEN** 该命令的行为 SHALL 与现有同后缀命令语义一致（列出/创建/删除对应资源）

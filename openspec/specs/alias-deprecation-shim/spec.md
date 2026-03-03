## ADDED Requirements

### Requirement: Deprecated 命令保留 shim
被重命名的旧命令 SHALL 以 shim 函数形式保留，而非直接删除。shim 函数 SHALL 执行以下操作：
1. 向 stderr 打印迁移警告（包含旧名 → 新名）
2. 以原始参数调用新命令

#### Scenario: Shim 打印警告
- **WHEN** 用户调用已废弃的旧命令（如 `cwt wt-foo`）
- **THEN** stderr SHALL 输出包含旧名和新名的警告，格式为 `⚠️  '<old>' is deprecated, use '<new>'`
- **THEN** 命令 SHALL 正常执行（等价于调用新命令）

#### Scenario: Shim 参数透传
- **WHEN** 用户调用 `cwt wt-foo` （shim）
- **THEN** 等价于调用 `ccwt wt-foo`，参数完整透传

### Requirement: Shim 覆盖范围
以下旧命令 SHALL 有对应的 shim 函数：

| 旧命令 | 新命令 | 所在文件 |
|--------|--------|---------|
| `c_safe` | `ccs` | `config/aliases/claude.sh` |
| `cwt` | `ccwt` | `config/aliases/claude.sh` |
| `cc_cn` | `cccn` | `config/aliases/claude.sh` |
| `cc_off` | `ccoff` | `config/aliases/claude.sh` |
| `cc_endpoint` | `ccep` | `config/aliases/claude.sh` |
| `owt` | `oowt` | `config/aliases/opencode.sh` |

#### Scenario: Shim 完整性检查
- **WHEN** 执行 `grep -c "is deprecated" config/aliases/claude.sh`
- **THEN** 输出 SHALL 为 `5`（对应 5 个 deprecated Claude 命令）

#### Scenario: Shim 完整性检查（OpenCode）
- **WHEN** 执行 `grep -c "is deprecated" config/aliases/opencode.sh`
- **THEN** 输出 SHALL 为 `1`（对应 1 个 deprecated OpenCode 命令）

### Requirement: Shim 实现方式为函数
Shim SHALL 以 zsh 函数形式定义，不得使用 `alias`，原因是 alias 无法向 stderr 打印消息。

#### Scenario: Shim 类型验证
- **WHEN** 查看 `config/aliases/claude.sh` 中旧命令（如 `cwt`）的定义
- **THEN** 其定义形式 SHALL 为 `cwt() { ... }` 而非 `alias cwt=...`

### Requirement: 新命令实现先于 Shim
新命令（如 `ccwt`）SHALL 在其对应 shim（`cwt`）之前定义，确保 shim 调用新命令时已可解析。

#### Scenario: 定义顺序检查
- **WHEN** 查看 `config/aliases/claude.sh` 文件内容
- **THEN** `ccwt` 函数定义行号 SHALL 小于 `cwt` shim 函数定义行号

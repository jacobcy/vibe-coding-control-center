## Context

`config/aliases/` 下的 7 个子文件（`git.sh`、`tmux.sh`、`worktree.sh`、`claude.sh`、`opencode.sh`、`openspec.sh`、`vibe.sh`）定义了约 30 个用户可见命令。当前 Claude 系命令存在三种前缀风格（`cc*`、`c_*`、`cwt`）和两种分隔符风格（下划线 vs 连写），OpenCode 系命令同样有两种前缀（`oo*`、`owt`），与 `vt*`、`wt*`、`os*` 等已统一的前缀族形成割裂。

涉及文件：`config/aliases/claude.sh`（5 处）、`config/aliases/opencode.sh`（1 处）、`docs/references/alias-helper.md`（文档已先行对齐）。

## Goals / Non-Goals

**Goals:**
- 统一 Claude 系命令使用 `cc*` 前缀，去掉下划线分隔符
- 统一 OpenCode in-worktree 命令使用 `oo*` 前缀
- 通过 deprecation shim 保证向后兼容，旧命令仍可用但会打印迁移提示
- 更新 `alias-helper.md` 中命令名称与实际代码一致

**Non-Goals:**
- 不重命名 `ccy`、`ccp`、`oo`、`ooa`（已符合规范）
- 不重命名 `vt*`、`wt*`、`os*` 系列（已统一）
- 不引入新的 alias 功能，只做命名对齐
- 不修改 `bin/vibe`、`lib/` 下任何 shell 脚本

## Decisions

### D1：统一为 `cc*` 前缀，无下划线

| 旧名 | 新名 | 理由 |
|------|------|------|
| `c_safe` | `ccs` | cc + **s**afe，去掉 `_`，加入 `cc*` 族 |
| `cwt` | `ccwt` | cc + **wt**，与 `ccwt` 类比 `oowt` 对称 |
| `cc_cn` | `cccn` | cc + **cn**，去掉 `_` |
| `cc_off` | `ccoff` | cc + **off**，去掉 `_` |
| `cc_endpoint` | `ccep` | cc + **ep**（endpoint 缩写），去掉 `_` 且缩短 |

**备选方案**：保留下划线（`cc_safe`、`cc_wt`）  
**否决理由**：`ccy`、`ccp` 已无下划线，混用更糟；连写更接近 `vt*`、`wt*` 的短命令风格。

### D2：`owt` → `oowt`

与 `ccwt` 对称，保持各 agent 的 in-worktree 命令风格一致。

**备选方案**：保留 `owt` 不改  
**否决理由**：`oo` 是 opencode 的前缀，`owt` 会被误读为"某个 o 前缀族命令"而非 opencode 命令。

### D3：Deprecation Shim 实现方式

在旧名定义处改为函数（而非 alias），函数体打印警告后调用新名：

```zsh
# Deprecated: use ccwt
cwt() { echo "⚠️  'cwt' is deprecated, use 'ccwt'" >&2; ccwt "$@"; }
```

**备选方案**：直接删除旧名  
**否决理由**：用户 dotfiles / 肌肉记忆中可能已有旧命令，直接删除体验差。

**备选方案**：用 `alias cwt=ccwt` 不打印警告  
**否决理由**：无警告时用户不会主动迁移，deprecation 期会无限拖延。

### D4：变更顺序

先改代码（`claude.sh`、`opencode.sh`） → 再更新文档（`alias-helper.md` 已在上一次 session 部分对齐，需补全新命令名）。

## Risks / Trade-offs

- **[Risk] 用户已在 `.zshrc` 中 source 了旧命令名** → Mitigation：shim 提供缓冲，打印迁移路径
- **[Risk] `cccn` / `ccoff` 连写可读性下降** → Mitigation：文档中标注助记法（`cc` + `cn(China)` / `off(Official)`）；若用户反馈强烈，可在下一个 change 中放宽为保留单下划线
- **[Trade-off] shim 函数会增加 `claude.sh` 行数** → 增量约 +15 行，可接受

## Migration Plan

1. 在 `claude.sh` 中添加新函数（`ccs`、`ccwt`、`cccn`、`ccoff`、`ccep`），将原实现移入新名
2. 将旧名（`c_safe`、`cc_cn`、`cc_off`、`cc_endpoint`、`cwt`）改为 shim 函数
3. 在 `opencode.sh` 中添加 `oowt`，将 `owt` 改为 shim
4. 更新 `alias-helper.md` Endpoint 章节和 Agent 命令章节显示新命令名（旧名标注 deprecated）

**Rollback**：仅为 shell 函数定义，回滚只需 `git revert` 对应 commit，重新 source aliases 即可。

## Open Questions

- `ccep`（3+2=5 字符）vs `ccurl`（`cc` + `url`）哪个更直觉？当前选 `ccep` 因为 endpoint 缩写 `ep` 在 CLI 工具中常见
- shim 保留期多长？建议 1 个 minor 版本后删除，但项目无版本号约束，暂定"3 个月或用户无反馈后删"

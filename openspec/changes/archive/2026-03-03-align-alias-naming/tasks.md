## 1. claude.sh — 新命令实现

- [x] 1.1 在 `config/aliases/claude.sh` 中添加 `ccs` 函数（原 `c_safe` 逻辑移入）
- [x] 1.2 在 `config/aliases/claude.sh` 中添加 `ccwt` 函数（原 `cwt` 逻辑移入）
- [x] 1.3 在 `config/aliases/claude.sh` 中添加 `cccn` 函数（原 `cc_cn` 逻辑移入）
- [x] 1.4 在 `config/aliases/claude.sh` 中添加 `ccoff` 函数（原 `cc_off` 逻辑移入）
- [x] 1.5 在 `config/aliases/claude.sh` 中添加 `ccep` 函数（原 `cc_endpoint` 逻辑移入）

## 2. claude.sh — Deprecation Shim

- [x] 2.1 将 `c_safe` 改为 shim 函数：打印 `⚠️  'c_safe' is deprecated, use 'ccs'` 后调用 `ccs "$@"`
- [x] 2.2 将 `cwt` 改为 shim 函数：打印 `⚠️  'cwt' is deprecated, use 'ccwt'` 后调用 `ccwt "$@"`
- [x] 2.3 将 `cc_cn` 改为 shim 函数：打印 `⚠️  'cc_cn' is deprecated, use 'cccn'` 后调用 `cccn "$@"`
- [x] 2.4 将 `cc_off` 改为 shim 函数：打印 `⚠️  'cc_off' is deprecated, use 'ccoff'` 后调用 `ccoff "$@"`
- [x] 2.5 将 `cc_endpoint` 改为 shim 函数：打印 `⚠️  'cc_endpoint' is deprecated, use 'ccep'` 后调用 `ccep "$@"`

## 3. opencode.sh — 新命令实现 + Shim

- [x] 3.1 在 `config/aliases/opencode.sh` 中添加 `oowt` 函数（原 `owt` 逻辑移入）
- [x] 3.2 将 `owt` 改为 shim 函数：打印 `⚠️  'owt' is deprecated, use 'oowt'` 后调用 `oowt "$@"`

## 4. 文档更新

- [x] 4.1 更新 `docs/references/alias-helper.md` Claude 命令表格，将 `c_safe`→`ccs`、`cwt`→`ccwt` 替换为新名，旧名标注 `(deprecated)`
- [x] 4.2 更新 `docs/references/alias-helper.md` Endpoint 切换表格，将 `cc_cn`→`cccn`、`cc_off`→`ccoff`、`cc_endpoint`→`ccep` 替换为新名
- [x] 4.3 更新 `docs/references/alias-helper.md` OpenCode 命令表格，将 `owt`→`oowt` 替换为新名

## 5. 验证

- [x] 5.1 新命令冒烟测试：source aliases，确认 `ccs`、`ccwt`、`cccn`、`ccoff`、`ccep`、`oowt` 均可 `type` 到
- [x] 5.2 Shim 警告验证：调用 `cwt` 确认 stderr 打印 deprecation 警告，且命令正常执行
- [x] 5.3 无下划线验证：执行 `grep -E "^(alias |[a-z]+\(\))" config/aliases/claude.sh | grep -E "cc_|c_safe"` 输出仅含 shim（无实现代码）
- [x] 5.4 Shim 计数验证：`claude.sh` 中 deprecation 警告行数为 5，`opencode.sh` 为 1
- [x] 5.5 Git commit：单次提交包含 claude.sh + opencode.sh + alias-helper.md 三文件，commit message 格式 `refactor(aliases): unify cc*/oo* naming, add deprecation shims`

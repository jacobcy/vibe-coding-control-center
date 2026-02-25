# Coding Standards (Supplement)

本文件仅保留实现细节约定；治理级约束以 `SOUL.md` 和 `CLAUDE.md` 为准。

## Shell Implementation
- 使用 `#!/usr/bin/env zsh`。
- 可执行脚本使用 `set -e`。
- 变量与路径必须正确引用。
- 共用函数优先复用 `lib/utils.sh`。

## Function Style
- 函数命名使用 `snake_case`。
- 内部函数前缀 `_`。
- 公共输出统一走 `log_*` helper。

## Delivery Discipline
- 一次提交只做一个逻辑变更。
- 提交前提供可验证证据（测试输出或复现实验步骤）。

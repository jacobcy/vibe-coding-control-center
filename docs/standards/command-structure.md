# Vibe Coding Control Center - Command Structure (Implementation)

## Overview

本文档描述 V2 版本下命令体系的**技术实现与落地结构**，不再包含 V1 早期的零散脚本设计。所有命令行为以 `docs/standards/command-standard.md` 为规范性来源。

## Command Architecture (V2)

The system currently uses a single main executable dispatcher (`bin/vibe`), which acts as an entry point resolving arguments into corresponding libraries. The old `vibe-chat`, `vibe-init` and `vibecoding.sh` scripts from V1 have been retired or heavily refactored out.

### Main Dispatcher: `bin/vibe`

`bin/vibe` is a lean shell script (`~80 lines`) that:
1. Loads core configuration from `lib/config.sh`
2. Determines the sub-command requested (`tool`, `flow`, `task`, etc.)
3. `source`s the corresponding library script in `lib/`
4. Dispatches the function call (e.g., `vibe_flow "[args]"`)

### Available Subcommands (Implementation Mapping)

| Subcommand | Description | Library Script | Function Invoked |
|------------|-------------|----------------|------------------|
| `vibe check` | 检查开发环境是否安装所有必要的 CLI（Claude, 依赖树等） | `lib/check.sh` | `vibe_check "$@"` |
| `vibe tool`  | 安装或更新 AI 工具 | `lib/tool.sh`  | `vibe_tool "$@"` |
| `vibe keys`  | 管理存储的各端 API Keys | `lib/keys.sh`  | `vibe_keys "$@"` |
| `vibe flow`  | 功能开发流水线 (start, review, sync) | `lib/flow.sh`  | `vibe_flow "$@"` |
| `vibe task`  | 跨工作树任务及多环境执行注册表监察 | `lib/task.sh`  | `vibe_task "$@"` |
| `vibe clean` | 清理临时工件及无效缓存 | `lib/clean.sh` | `vibe_clean "$@"` |
| `vibe skills`| 检测及分发 Markdown 技能依赖 | `lib/skills.sh`| `vibe_skills "$@"` |
| `vibe alias` | 为 Shell 写入 aliases 热加载 | `config/aliases.sh` | - |

## Directory Structure (V2)

```
vibe-center/
├── bin/
│   └── vibe                 # V2 Single Entry Dispatcher
├── lib/                     # Lazy-loaded subcommand implementations
│   ├── check.sh
│   ├── clean.sh
│   ├── flow.sh
│   ├── keys.sh
│   ├── skills.sh
│   ├── task.sh
│   ├── tool.sh
│   └── config.sh            # Global config loader
├── scripts/                 # System automation integrations
│   ├── lint.sh
│   ├── metrics.sh
│   └── rotate.sh
├── skills/                  # Autonomous Agent subroutines
│   ├── vibe-task/
│   ├── vibe-save/
│   ├── vibe-continue/
│   ├── vibe-new/
│   ├── vibe-skills/
│   └── ...
└── docs/                    # Docs and registries
    ├── prds/
    ├── standards/
    └── tasks/
```

## Implementation Philosophy 

1. **Lightweight Dispatching**: `bin/vibe` never executes heavy logic. Logic lives exclusively in `lib/*.sh`.
2. **Lazy Sourcing**: Subcommand files are only loaded (`source`) when that command is specifically typed. This prevents cold start inflation.
3. **No Redundant Binaries**: All Vibe extensions use Vibe's unified `--help`, drastically minimizing `PATH` pollution.
4. **Shell Execution**: Relies purely on `/usr/bin/env zsh` combined with `jq` for config mapping, achieving complete parity across Macs with minimal dependencies.

## Migration Notice from V1
If you are interacting with old `vibe-*` aliases, ensure they evaluate to `vibe <subcommand>`. Independent executables like `bin/vibe-config`, `bin/vibe-env`, and `scripts/vibecoding.sh` have been superseded by `lib/` implementations.

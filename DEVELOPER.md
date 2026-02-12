# Vibe Coding Control Center 开发指南

本文档旨在帮助开发者理解 Vibe 的项目架构、搭建开发环境并参与核心功能的开发。

## 1. 开发环境搭建

### 1.1 前置要求
- macOS / Linux
- zsh (默认 Shell)
- git

### 1.2 本地开发安装
为了不影响你全局安装的 Vibe (`~/.vibe`)，我们推荐使用 **本地模式** 进行开发。本地模式会将配置和运行时环境限制在当前项目目录下。

```bash
# 在项目根目录执行
./scripts/install.sh --local
```

这将会：
1. 在当前项目下初始化 `.vibe` 目录（存放配置和临时文件）。
2. 将当前项目的 `bin` 目录添加到你的 Shell 配置文件中（通常需要你手动 `source` 或重新打开终端，请留意脚本输出）。
3. 确保 `vibe` 命令优先使用你当前修改的代码。

### 1.3 验证开发环境
```bash
# 重新加载配置
source ~/.zshrc  # 或你的 shell 配置文件

# 验证 vibe 命令路径
which vibe
# 输出应指向：.../vibe-center/main/bin/vibe （而不是 ~/.vibe/bin/vibe）

# 检查各项指标
vibe doctor
```

## 2. 项目架构详解

### 2.1 目录结构
*   `bin/`: **可执行入口脚本**。`vibe` 是主调度器，`vibe-chat`, `vibe-config` 等是子命令。
*   `lib/`: **核心逻辑库**。
    *   `config.sh`: 配置加载与路径探测（核心中的核心）。
    *   `utils.sh`: 通用工具函数（日志、UI、系统检查）。
    *   `agents.sh`: AI Agent 相关的抽象。
    *   `i18n.sh`: 国际化支持。
*   `scripts/`: **运维与安装脚本**。包含 `install.sh`, `test-all.sh`, `vibecoding.sh` (旧版入口) 等。
*   `config/`: **默认配置模板**。包含 `keys.template.env`, `aliases.sh`。
*   `tests/`: **测试套件**。

### 2.2 核心机制：Code vs Config
Vibe 严格区分 **代码根目录 (`VIBE_ROOT`)** 和 **配置根目录 (`VIBE_HOME`)**。

*   **VIBE_ROOT**: 代码（bin, lib）所在位置。
    *   Global 模式下：`~/.vibe`
    *   Local 模式下：Git 项目根目录
    *   探测逻辑：由 `lib/config.sh` 中的 `_find_vibe_root` 处理。

*   **VIBE_HOME**: 用户配置文件 (`keys.env`, `config.toml`) 所在位置。
    *   默认为 `VIBE_ROOT/.vibe`。
    *   探测逻辑：由 `lib/config.sh` 中的 `_find_vibe_home` 处理。
    *   **优先级**：
        1. Caller Override (调用者强制指定)
        2. Local Project `.vibe` (当前目录向上递归查找)
        3. Git Root `.vibe`
        4. Global Install `~/.vibe` (如果 `VIBE_ROOT` 指向这里)
        5. User Home `~/.vibe` (最终兜底)

这种设计使得你可以在不同项目中使用不同的 `.vibe` 配置（例如不同的 API Key），同时共用同一套 Vibe 代码；或者在开发 Vibe 本身时，完全隔离环境。

### 2.3 命令调度 (`bin/vibe`)
`vibe` 命令类似于 Git，它是一个调度器：
1. **Context Shim**: 它会检测当前目录下是否有 `.vibe`。如果有，且不是当前正在运行的这个 `vibe`，它会 `exec` 切换到那个局部的 `vibe`。这保证了项目内优先使用项目内锁定的 Vibe 版本（未来特性）。
2. **Subcommands**: `vibe foo` 会自动寻找并执行 `bin/vibe-foo`。

## 3. 测试指南

本项目包含完整的测试套件，确保重构和新功能不破坏现有逻辑。

### 3.1 运行所有测试
```bash
./scripts/test-all.sh
```

### 3.2 运行特定测试
```bash
# 例如，只运行配置隔离测试
./tests/test_config_isolation.sh
```

### 3.3 编写新测试
测试脚本位于 `tests/` 目录。我们使用轻量级的 Shell 脚本进行测试。
推荐参考 `tests/unit/simple_test.sh` 或 `tests/test_config_isolation.sh`。

关键测试工具 (`lib/testing.sh`)：
*   `assert_eq "expected" "actual"`
*   `assert_contains "haystack" "needle"`
*   `run_test "Test Name" function_name`

## 4. 常见开发任务

### 添加新命令
1. 在 `bin/` 下创建 `vibe-yourcmd`。
2. 赋予执行权限：`chmod +x bin/vibe-yourcmd`。
3. 引用标准库头文件：
   ```bash
   #!/usr/bin/env zsh
   SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
   VIBE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
   source "$VIBE_ROOT/lib/utils.sh"
   source "$VIBE_ROOT/lib/config.sh"
   
   # 你的逻辑...
   ```

### 修改配置逻辑
配置逻辑主要在 `lib/config.sh`。修改后请务必运行 `tests/test_config_isolation.sh` 确保没有破坏路径探测逻辑。

## 5. 发布流程
目前主要通过 git tag 和 release 分支管理。
（待完善）

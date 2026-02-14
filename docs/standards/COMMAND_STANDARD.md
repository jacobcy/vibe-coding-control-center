# Vibe CLI 命令规范 (Command Standard)

本文档作为 Vibe Coding Control Center 命令行工具的工程化规范标准。所有新增命令及重构工作必须严格遵循本规范。

## 1. 设计原则 (Design Principles)

*   **Git 风格子命令**: 采用 `vibe <subcommand> [action]` 的结构。
*   **单一职责**: 子命令专注于单一领域。
*   **层级清晰**: 区分 配置(Config)、环境(Env)、检测(Check)、业务(Flow/Chat)。
*   **本地优先**: 默认优先使用项目级配置，支持全局回退。

## 1.1. 统一交互规范 (Interaction Standards)

**帮助规范**:
*   所有子命令必须支持 `help` / `-h` / `--help` 三种帮助入口。
*   帮助输出结构必须包含：命令简述 → 子命令/动作列表 → 示例。

**参数风格**:
*   子命令与 action 使用小写短单词（如 `vibe flow start`）。
*   长参数使用 `--kebab-case`（如 `--base=main`），短参数使用单字母（如 `-g`）。
*   参数顺序：`vibe <subcommand> <action> [options] [args]`。

**退出码与错误分级**:
*   `0`: 成功执行。
*   `1`: 通用错误（未知子命令、执行失败）。
*   `2`: 用户输入错误（参数缺失、非法值）。
*   `3`: 环境/依赖错误（缺少依赖、配置缺失）。

**输出格式**:
*   默认输出面向人类阅读。
*   若支持机器可读输出，统一使用 `--json` 标志并输出稳定字段结构。

## 2. 核心命令体系 (Core Command Hierarchy)

### 2.1. 诊断与检测: `vibe check`
*统一的系统状态验证入口*

*   `vibe check` (或 `all`): 执行所有核心检查。
*   `vibe check system`: 检查系统依赖、环境路径、工具版本（原 `doctor status`）。
*   `vibe check api`: 检查 API 连接性及 Key 有效性。
*   `vibe check mcp`: 检查 MCP 服务器配置及状态。

### 2.2. 配置管理: `vibe config`
*管理持久化配置文件 (Static Configuration)*

*   `vibe config`: 列出所有配置文件的路径及存在状态。
*   `vibe config list`: 列出所有读取到的配置值（脱敏）。
*   `vibe config <target>`: 显示指定目标的配置详情。
*   `vibe config edit <target>`: 调用编辑器修改指定配置。
    *   `keys`: 修改当前项目的 `keys.env`。
    *   `claude`: 修改 `~/.claude.json`。
    *   `opencode`: 修改 `opencode.json`。
    *   `alias`: 修改 `aliases.sh` (或通过 `vibe alias` 管理)。

### 2.3. 运行时环境: `vibe env`
*管理当前 Shell 会话及环境变量 (Runtime Environment)*

**关于 keys.env 与 ~/.zshrc 的区别**:
*   `keys.env`: **项目级/本地环境**。只在该项目目录下生效，不会污染全局环境，适合存放项目专用的 API Key 或 Toggle。
*   `~/.zshrc`: **用户级/全局环境**。所有终端生效。

命令行为：
*   `vibe env`: 列出当前**生效中**的环境变量 (Resolved Variables)。包含来源标注 (`[Local]` / `[Global]`)。
*   `vibe env edit`: **快捷指令**，等同于 `vibe config edit keys`。
*   `vibe env inject`: 将当前项目的 `keys.env` 注入到当前 Shell Session (export)。
*   ~~`vibe env switch`~~: (已移除，避免过度设计，请直接编辑 keys.env)。

### 2.4. 快捷指令: `vibe alias`
*管理用户定义的快捷命令*

*   `vibe alias` (或 `list`): 列出所有可用别名及其对应命令。
*   `vibe alias edit`: 调用编辑器打开 `~/.vibe/custom_aliases.sh` (或其他别名文件) 进行手动编辑。
*   `vibe alias inject`: 将别名配置注入当前 Shell Session (source)。

### 2.5. 全局操作

*   **全局标志 `-g` / `--global`**:
    *   `vibe -g <command>`: 强制使用全局安装的 Vibe (`~/.vibe/bin/vibe`) 执行命令。

## 3. 业务功能命令说明 (Business Logic)

### 3.1 `vibe flow` (工作流)
*   核心功能：规范化 Git 操作与研发流程。
*   **Action**:
    *   `start <feature>`: 创建分支，创建 worktree，初始化 PRD 模板。
    *   `spec`: 打开/创建技术规格文档。
    *   `test`: 初始化或运行测试 (TDD)。
    *   `review`: 启动 Lazygit 进行代码审查。
    *   `pr`: 调用 gh cli 创建 Pull Request。
    *   `done`: 清理工作区，归档分支。

### 3.2 `vibe chat` (AI 对话)
*   核心功能：快速启动 AI 交互工具。
*   **Action**:
    *   `vibe chat`: 启动配置的默认 AI 工具 (Claude/OpenCode)。
    *   `vibe chat "message"`: 单次提问模式。

### 3.3 `vibe equip` (工具链)
*   核心功能：安装与升级依赖工具。
*   **Action**:
    *   `vibe equip`: 显示交互式菜单，选择安装 Claude, OpenCode, Gum 等工具。
    *   `vibe equip install <tool>`: 直接安装指定工具。
    *   `vibe equip update`: 更新所有已安装工具。

### 3.4 `vibe init` (初始化)
*   核心功能：项目脚手架与环境初始化。
*   **行为**:
    *   在当前目录生成标准目录结构 (.vibe, docs, scripts 等)。
    *   创建 `vibe.toml` 或 `keys.env` 模板。
    *   检查并提示安装 git hooks。

## 4. 废弃与兼容 (Deprecation)

*   `vibe doctor` -> `vibe check`
*   `vibe keys` -> `vibe config` / `vibe env`
*   `vibe env verify` -> `vibe check api`

# Vibe Alias 测试方案

## 概述

本文档描述了 Vibe Coding Control Center 的 alias 测试方案，确保所有内置 alias 正常工作。

## 测试文件位置

- 测试脚本: `tests/test-aliases.sh`
- Alias 配置: `config/aliases.sh` 和 `config/aliases/*.sh`

## 使用方法

### 运行所有测试
```bash
zsh tests/test-aliases.sh
```

### 详细输出模式
```bash
zsh tests/test-aliases.sh --verbose
```

### 静默模式（仅显示结果）
```bash
zsh tests/test-aliases.sh --quiet
```

## 测试类别

### 1. 语法检查测试 (Syntax Tests)
- 检查所有 alias 文件的 zsh 语法
- 验证没有语法错误
- 测试文件:
  - `config/aliases.sh`
  - `config/aliases/claude.sh`
  - `config/aliases/opencode.sh`
  - `config/aliases/openspec.sh`
  - `config/aliases/vibe.sh`
  - `config/aliases/git.sh`
  - `config/aliases/tmux.sh`
  - `config/aliases/worktree.sh`

### 2. 加载测试 (Load Tests)
- 验证 aliases.sh 能够成功加载
- 检查环境变量是否正确设置（VIBE_ROOT, VIBE_REPO, VIBE_MAIN）

### 3. Alias 定义测试 (Definition Tests)
- 验证所有 alias 都已正确定义
- 检查关键 alias:
  - Claude: `ccy`, `ccp`
  - Vibe: `lg`, `vc`, `vsign`
  - Git 函数: `vibe_git_root`, `vibe_main_guard`

### 4. 函数执行测试 (Function Tests)
- 测试核心函数:
  - `vibe_has()` - 命令存在检查
  - `vibe_now()` - 时间获取
  - `vibe_git_root()` - Git 根目录获取（如果在 git 仓库中）
  - `vibe_branch()` - 当前分支获取（如果在 git 仓库中）

### 5. 依赖检查测试 (Dependency Tests)
- 检查核心依赖:
  - `git` - 版本控制
  - `zsh` - Shell
- 检查可选依赖:
  - `tmux` - 终端复用器
  - `lazygit` - TUI Git 客户端
  - `claude` - Claude CLI
  - `opencode` - OpenCode CLI

### 6. 集成测试 (Integration Tests)
- 验证完整加载流程
- 检查 `vibe` 函数定义

## 预期输出示例

```
╔════════════════════════════════════════════════════════════╗
║          Vibe Alias 测试套件 (Test Suite)                  ║
╚════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════╗
║              语法检查测试 (Syntax Tests)                     ║
╚════════════════════════════════════════════════════════════╝

[TEST] 语法检查: aliases.sh
[PASS] 语法检查: aliases.sh
[TEST] 语法检查: claude.sh
[PASS] 语法检查: claude.sh
...

╔════════════════════════════════════════════════════════════╗
║                    测试总结 (Test Summary)                 ║
╚════════════════════════════════════════════════════════════╝

  总测试数: 35
  通过: 35
  失败: 0
  跳过: 0

✓ 所有测试通过!
```

## 故障排除

### 测试卡住或超时
- 使用 `--quiet` 模式减少输出
- 检查是否有交互式命令阻塞

### 语法检查失败
- 运行 `zsh -n config/aliases.sh` 查看具体错误
- 检查是否使用了 zsh 不支持的语法

### 函数测试失败
- 确保在正确的目录运行测试
- 检查依赖命令是否已安装

## 持续集成建议

建议将此测试添加到 CI/CD 流程中:

```yaml
# .github/workflows/test-aliases.yml
name: Test Aliases
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install zsh
        run: sudo apt-get install -y zsh
      - name: Run alias tests
        run: zsh tests/test-aliases.sh --quiet
```

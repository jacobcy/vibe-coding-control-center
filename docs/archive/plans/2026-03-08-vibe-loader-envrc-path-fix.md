# Vibe Loader And Envrc Path Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 shell 启动时的 `vibe: error: alias/loader.sh not found`，并把仓库 `.envrc` 从失效的临时虚拟环境路径收敛到稳定可复用的路径写法。

**Architecture:** 本次只处理两处路径契约失配，不重做 alias 架构。`config/aliases.sh` 保留兼容壳职责，但要同时兼容源码树布局和全局安装布局；`scripts/install.sh` 与仓库根 `.envrc` 统一使用稳定的 `~/.venvs/vibe-center` 约定，避免安装时把临时 `HOME` 展开成一次性绝对路径。

**Tech Stack:** Zsh CLI (`bin/vibe`, `config/*.sh`, `scripts/install.sh`)、direnv、uv virtualenv、Bats。

---

## Goal

- 消除登录 shell 启动时的 alias loader 报错。
- 修复当前 worktree 的 `.envrc` 失效路径。
- 让后续 `scripts/install.sh` 生成的 `.envrc` 不再固化临时目录。

## Non-goals

- 不重构 `alias/` 与 `config/aliases/` 的整体目录设计。
- 不改 `~/.zshrc` 集成方式。
- 不引入新的虚拟环境管理策略。

## 已确认事实

- 仓库内 `alias/loader.sh` 存在，当前报错不是源码缺文件。
- 全局安装产物 `~/.vibe/config/aliases.sh` 仍按 `../alias/loader.sh` 查找 loader，但 `~/.vibe` 下并没有 `alias/loader.sh`。
- 当前仓库 `.envrc` 写死到了 `/var/folders/.../tmp.../home/.venvs/vibe-center/bin/activate`，该路径已失效。
- 真实可用的全局虚拟环境位于 `~/.venvs/vibe-center/bin/activate`。

## Step Tasks

### Task 1: 收敛 alias 兼容加载逻辑

**Files to modify:**
- `config/aliases.sh`

**Step 1: 写一个最小失败场景**

明确两个兼容场景：

- 源码树：`config/aliases.sh` 应继续转发到 `alias/loader.sh`
- 全局安装：`~/.vibe/config/aliases.sh` 应能直接加载 `config/aliases/*.sh`

**Step 2: 修改兼容壳**

在 `config/aliases.sh` 中按顺序解析：

1. 若同级上层存在 `../alias/loader.sh`，source 它
2. 否则若存在 `aliases/` 目录，逐个 source `git.sh`、`tmux.sh`、`worktree.sh`、`claude.sh`、`opencode.sh`、`openspec.sh`、`vibe.sh`
3. 两种布局都不存在时再报错

**Step 3: 控制输出行为**

保持交互 shell 下的成功提示，但失败信息要明确指出“当前安装布局缺失可加载的 alias 入口”。

**Step 4: 运行最小验证**

Run: `zsh -lic 'true'`

Expected: 不再输出 `vibe: error: alias/loader.sh not found`

### Task 2: 修复 `.envrc` 的稳定路径写法

**Files to modify:**
- `.envrc`
- `scripts/install.sh`

**Step 1: 先写出目标写法**

仓库根 `.envrc` 改成稳定表达，不引用一次性临时目录。优先使用：

```sh
source "$HOME/.venvs/vibe-center/bin/activate"
```

**Step 2: 修正 installer 生成逻辑**

把 `scripts/install.sh` 中写 `.envrc` 的逻辑改成写入上述稳定写法，而不是把安装时的 `venv_path` 绝对展开到文件内容中。

**Step 3: 保持现有行为边界**

- 仍然只在 `.envrc` 不存在时自动创建
- 不改 direnv hook 注入策略
- 不改 venv 创建位置，仍为 `"$HOME/.venvs/vibe-center"`

**Step 4: 运行最小验证**

Run: `direnv status`

Expected: 指向仓库 `.envrc`，且 `.envrc` 文件内容不再含 `/var/folders/` 或其它临时路径

### Task 3: 为 installer 和 alias 兼容增加回归测试

**Files to modify:**
- `tests/test_install_gh_noninteractive.bats`
- `tests/test_vibe.bats`

**Step 1: 补 installer 测试**

在 `tests/test_install_gh_noninteractive.bats` 增加断言：

- 安装完成后生成的 `.envrc` 存在
- `.envrc` 内容使用 `source "$HOME/.venvs/vibe-center/bin/activate"` 形式
- 不包含 fixture 临时目录前缀

**Step 2: 补 alias 兼容测试**

在 `tests/test_vibe.bats` 或同文件新增场景，模拟：

- `HOME=<fixture>` 下的 `~/.vibe/config/aliases.sh`
- 仅存在 `config/aliases/*.sh`，不存在 `alias/loader.sh`

执行：

```sh
zsh -lc 'source "$HOME/.vibe/config/aliases.sh"'
```

Expected: 成功退出，不输出 `alias/loader.sh not found`

**Step 3: 运行针对性测试**

Run:

```bash
bats tests/test_install_gh_noninteractive.bats
bats tests/test_vibe.bats
```

Expected: 两个测试文件均通过

### Task 4: 做命令级回归验证

**Files to inspect during execution:**
- `~/.vibe/config/aliases.sh`
- `~/.vibe/loader.sh`

**Step 1: 验证 CLI 入口未回归**

Run:

```bash
bin/vibe alias --load
bin/vibe help
```

Expected:

- `vibe alias --load` 仍返回仓库内 `alias/loader.sh`
- `vibe help` 正常输出帮助文本

**Step 2: 验证登录 shell 报错消失**

Run: `zsh -lic 'true'`

Expected: 退出码 `0`，无 `alias/loader.sh not found`

**Step 3: 验证 direnv 路径恢复**

Run:

```bash
cat .envrc
test -f "$HOME/.venvs/vibe-center/bin/activate"
```

Expected:

- `.envrc` 内容为稳定路径写法
- `activate` 文件存在

## Files To Modify

- `config/aliases.sh`
- `.envrc`
- `scripts/install.sh`
- `tests/test_install_gh_noninteractive.bats`
- `tests/test_vibe.bats`

## Test Command

```bash
bats tests/test_install_gh_noninteractive.bats
bats tests/test_vibe.bats
zsh -lic 'true'
direnv status
cat .envrc
test -f "$HOME/.venvs/vibe-center/bin/activate"
bin/vibe alias --load
bin/vibe help
```

## Expected Result

- 新开登录 shell 时不再打印 `vibe: error: alias/loader.sh not found`
- 当前仓库 `.envrc` 不再引用 `/var/folders/.../tmp...` 临时路径
- `scripts/install.sh` 以后生成的 `.envrc` 使用稳定 `"$HOME/.venvs/vibe-center/bin/activate"` 写法
- Bats 回归测试覆盖安装与 alias 兼容两条路径

## Change Summary

- Files affected: `5`
- Expected added lines: `50-90`
- Expected removed lines: `5-20`
- Expected modified lines: `20-40`

## Execution Notes

- 本计划刚好触及 `5` 个文件，不需要额外的 `>5 files` 确认。
- 执行阶段若发现全局安装产物与仓库源码还有第三种布局差异，应记录到 `artifacts/` 后暂停，不顺手扩展更多兼容分支。

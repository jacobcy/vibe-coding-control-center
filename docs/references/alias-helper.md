# Vibe Coding Alias Helper（Level 2）

这套 alias 的目标只有一句话：

> **Agent（Claude / OpenCode / Codex）全自动干活，你只负责最后检查和提交。**

你不需要在中间盯着、不需要反复确认、不需要担心误伤主分支。

---

## 一、整体理念（先对齐心智模型）

- **worktree = 安全沙盒**
- **tmux = 持久会话容器**
- **agent = 自动执行（--yes）**
- **lazygit = 人类最终审查点**

你的角色不是"一起敲代码"，而是 **reviewer / approver**。

---

## 二、基础结构假设

你的仓库结构类似：

```
repo/
├── main/            # 主分支 worktree（只做人类操作）
├── wt-xxx/          # 各种实验 / 功能 worktree
└── config/
    └── aliases.sh
└── docs/
    └── alias-helper.md
```

---

## 三、tmux 会话命令 (vt*)

### 基础命令

```bash
vt     # 进入（或创建）tmux 会话
vtup   # 创建或附加到指定 session
vtdown # 分离当前 session
vtswitch <session>  # 切换到指定 session
vtls   # 列出所有 session
vtkill <session>   # 删除指定 session
vtkill             # 删除当前 session
```

用途：
- 所有 agent 常驻在 tmux 中
- SSH 断线 / 关 Terminal 都不会中断任务

---

## 四、Worktree 管理命令

### `wtls`

列出所有 worktree（等同于 git worktree list）。

```bash
wtls
```

---

### `wt <wt-dir>`

跳转到某个 worktree 目录。

如果在 tmux 内：
- 会自动把当前 window 重命名为 worktree 名

示例：

```bash
wt wt-login-fix
```

---

### `wtnew <branch> [agent=claude|opencode|codex] [base=main]`

创建一个新的 worktree，并切换进去。

默认行为：
- 从 base 分支创建新分支（默认 main）
- worktree 目录名为 wt-<agent>-<branch>
- 设置 git identity 为 Agent-<agent>

示例：

```bash
wtnew login-fix claude
wtnew feature-branch opencode develop
```

结果：
- 创建 wt-claude-login-fix/ 目录
- 分支名：login-fix（从 main 分支）
- Git identity：Agent-Claude <agent-claude@vibecoding.ai>

---

### `wtrm <wt-dir>`

删除某个 worktree，并清理 git 引用。

```bash
wtrm wt-login-fix
wtrm all   # 删除所有 wt-* worktree
```

⚠️ 这是强制删除，只用于实验分支。

---

### `wtinit [agent]`

重新同步 Git identity（使用指定的 agent，默认 claude）。

```bash
wtinit        # 使用 claude identity
wtinit opencode
```

---

### `wtrenew`

刷新当前 worktree（重新初始化 Git identity）。

```bash
wtrenew
```

---

## 五、Agent（Claude / OpenCode / Codex）命令

### Claude 命令 (cc*)

```bash
ccy   # claude --dangerously-skip-permissions --continue
ccp   # claude --permission-mode plan
```

---

### OpenCode 命令 (oo*)

```bash
oo    # opencode
ooa   # opencode --continue
```

---

### OpenSpec 命令 (os*)

```bash
os    # openspec
osi   # openspec init
osl   # openspec list
osv   # openspec view
osn   # openspec new
osval # openspec validate
```

---

### 安全模式（保护 main 分支）

```bash
c_safe  # 在当前目录启动 Claude（保护 main 分支）
```

---

### 在指定 worktree 启动 agent

```bash
cwt <wt-dir>  # Claude in worktree
owt <wt-dir>  # OpenCode in worktree
```

示例：

```bash
cwt wt-login-fix
```

等价于：
1. cd wt-login-fix
2. claude --dangerously-skip-permissions --continue

---

### Endpoint 切换

```bash
cc_cn   # 切换到自定义 endpoint（中国）
cc_off  # 切换到官方 endpoint
```

---

## 六、一键「全套工作台」（核心功能）

### `vup <wt-dir> [agent=claude|opencode|codex] [editor_cmd]`

为一个 worktree 自动创建 完整 tmux 工作区。

会创建以下 tmux windows：

| Window 名称 | 用途 |
|-----------|------|
| <wt>-edit | 编辑器（vim / code / 你自定义） |
| <wt>-agent | Claude / Codex（自动执行） |
| <wt>-tests | 跑测试 |
| <wt>-logs | 看日志 |
| <wt>-git | lazygit（最终审查点） |

示例：

```bash
vup wt-login-fix claude
```

你需要做的事：
- 什么都不用管
- 等 agent 干完
- 去 <wt>-git 窗口检查并提交

---

## 七、一键从零开始（最推荐）

### `vnew <branch> [agent=claude|opencode|codex] [base=main]`

这是你最常用的命令。

它会一次性完成：
1. 创建新分支
2. 创建 worktree（wt-<branch>）
3. 启动 tmux 全套窗口
4. 启动 agent（--yes）
5. 打开 lazygit

示例：

```bash
vnew login-fix claude
```

你接下来只需要：
- 去 wt-login-fix-git
- Review → Commit

---

## 八、lazygit & Git 快捷命令

### `lg`

启动 lazygit。

---

## 九、推荐练习路线（最省脑）

### Day 1：只用 vnew

```bash
vt
vnew test-1 claude
```

等 agent 完成 → lazygit 审查 → commit。

---

### Day 2：区分创建和启动

```bash
wtnew test-2
vup wt-test-2 opencode
```

---

## 十、安全底线（非常重要）

- ❌ 不要在 main/master 用 ccy / ooa
- ✅ 所有 agent 操作都在 worktree
- ✅ 你永远保留最终审查权

---

## 十一、一句话总结

你不是在"和 AI 一起写代码"，
你是在"调度多个 agent 干活"。

这套 alias 的意义就在这里。

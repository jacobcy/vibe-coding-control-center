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
├── main/                  # 主分支 worktree（只做人类操作）
├── wt-xxx/                # 各种实验 / 功能 worktree
└── config/
    ├── aliases.sh         # Alias 加载器（入口）
    └── aliases/           # Alias 子文件（按类别拆分）
        ├── git.sh         # Git 辅助函数
        ├── tmux.sh        # Tmux 会话管理
        ├── worktree.sh    # Worktree + 工作区命令
        ├── claude.sh      # Claude CLI 命令
        ├── opencode.sh    # OpenCode 命令
        ├── openspec.sh    # OpenSpec 命令
        └── vibe.sh        # Vibe 综合命令
```

---

## 三、助记规则

所有命令遵循 **`<工具前缀><动作>`** 的命名模式：

| 前缀 | 含义 | 记忆口诀 |
|------|------|---------|
| `vt` | tmux 会话 | **V**ibe **T**mux |
| `wt` | git worktree | **W**ork**T**ree |
| `cc` | Claude CLI | **C**laude **C**LI |
| `oo` | OpenCode | **O**pen**C**ode（两个 O） |
| `os` | OpenSpec | **O**pen**S**pec |
| `v`  | Vibe 综合 | **V**ibe |

常用动作后缀：

| 后缀 | 含义 | 出现在 |
|------|------|--------|
| `ls` | 列表 | `vtls`, `wtls` |
| `new` | 创建 | `wtnew`, `vnew` |
| `rm` | 删除 | `wtrm` |
| `up` / `down` | 启动 / 分离 | `vtup`, `vtdown`, `vup` |
| `kill` | 强制终止 | `vtkill` |
| `init` | 初始化 | `wtinit` |
| `wt` | 在 worktree 中运行 | `cwt`, `owt` |

> 💡 用 `vibe alias` 命令可以随时查看所有可用的 alias 列表。

---

## 四、tmux 会话命令 (vt*)

| 命令 | 功能 | 示例 |
|------|------|------|
| `vt` | 附加到默认 Vibe tmux 会话 | `vt` |
| `vtup [session]` | 创建或附加到指定 session | `vtup my-work` |
| `vtdown` | 分离当前 session | `vtdown` |
| `vtswitch <session>` | 切换到指定 session | `vtswitch dev` |
| `vtls` | 列出所有 session | `vtls` |
| `vtkill [session]` | 删除指定/当前 session | `vtkill old-session` |

用途：
- 所有 agent 常驻在 tmux 中
- SSH 断线 / 关 Terminal 都不会中断任务

---

## 五、Worktree 管理命令 (wt*)

| 命令 | 功能 | 示例 |
|------|------|------|
| `wtls` | 列出所有 worktree | `wtls` |
| `wt <wt-dir>` | 跳转到某个 worktree（tmux 内自动重命名窗口） | `wt wt-login-fix` |
| `wtnew <branch> [agent] [base]` | 创建新 worktree + 设置 agent identity | `wtnew login-fix claude` |
| `wtrm <wt-dir\|all>` | 删除 worktree 并清理 git 引用 | `wtrm wt-login-fix` |
| `wtinit [agent]` | 重新设置当前 worktree 的 git identity | `wtinit opencode` |
| `wtrenew` | 刷新当前 worktree identity 和状态 | `wtrenew` |

### `wtnew` 详解

```bash
wtnew login-fix claude        # 从 main 创建
wtnew feature-branch opencode develop  # 从 develop 创建
```

结果：
- 创建 `wt-claude-login-fix/` 目录
- 分支名：`login-fix`（从 main 分支）
- Git identity：`Agent-Claude <agent-claude@vibecoding.ai>`

### `wtrm` 详解

```bash
wtrm wt-login-fix    # 删除单个 worktree
wtrm all             # 删除所有 wt-* worktree
```

⚠️ 这是强制删除。会提示是否同时删除远程分支。

---

## 六、Agent 命令

### Claude 命令 (cc*)

| 命令 | 功能 | 助记 |
|------|------|------|
| `ccy` | `claude --dangerously-skip-permissions --continue` | **CC** + **Y**es |
| `ccp` | `claude --permission-mode plan` | **CC** + **P**lan |
| `ccs` | Claude（保护 main 分支） | **CC** + **S**afe |
| `ccwt <wt-dir>` | 跳转到 worktree 并启动 Claude | **CC** + **W**ork**T**ree |
| ~~`c_safe`~~ | (deprecated → `ccs`) | — |
| ~~`cwt`~~ | (deprecated → `ccwt`) | — |

### OpenCode 命令 (oo*)

| 命令 | 功能 | 助记 |
|------|------|------|
| `oo` | `opencode`（启动） | **O**pen**C**ode |
| `ooa` | `opencode --continue`（继续上次会话） | **OO** + **A**gain |
| `oowt <wt-dir>` | 跳转到 worktree 并启动 OpenCode | **OO** + **W**ork**T**ree |
| ~~`owt`~~ | (deprecated → `oowt`) | — |

### OpenSpec 命令 (os*)

| 命令 | 功能 | 助记 |
|------|------|------|
| `os` | `openspec`（启动） | **O**pen**S**pec |
| `osi` | `openspec init` | **OS** + **I**nit |
| `osl` | `openspec list` | **OS** + **L**ist |
| `osv` | `openspec view` | **OS** + **V**iew |
| `osn` | `openspec new` | **OS** + **N**ew |
| `osval` | `openspec validate` | **OS** + **Val**idate |

### Endpoint 切换（Claude）

| 命令 | 功能 |
|------|------|
| `cccn` | 切换到自定义 endpoint（中国） |
| `ccoff` | 切换到官方 endpoint |
| `ccep` | 显示当前 Claude endpoint |
| ~~`cc_cn`~~ | (deprecated → `cccn`) |
| ~~`cc_off`~~ | (deprecated → `ccoff`) |
| ~~`cc_endpoint`~~ | (deprecated → `ccep`) |

---

## 七、一键「全套工作台」（核心功能）

### `vup [wt-dir] [agent] [editor]`

为一个 worktree 自动创建完整 tmux 工作区。

会创建以下 tmux windows：

| Window 名称 | 用途 |
|-----------|------|
| `<wt>-edit` | 编辑器（vim / code / 你自定义） |
| `<wt>-agent` | Claude / OpenCode / Codex（自动执行） |
| `<wt>-tests` | 跑测试 |
| `<wt>-logs` | 看日志 |
| `<wt>-git` | lazygit（最终审查点） |

```bash
vup wt-login-fix claude
```

你需要做的事：
- 什么都不用管
- 等 agent 干完
- 去 `<wt>-git` 窗口检查并提交

---

## 八、一键从零开始（最推荐）

### `vnew <branch> [agent] [base]`

这是你最常用的命令。

它会一次性完成：
1. 创建新分支
2. 创建 worktree（`wt-<agent>-<branch>`）
3. 启动 tmux 全套窗口
4. 启动 agent（--yes）
5. 打开 lazygit

```bash
vnew login-fix claude
```

你接下来只需要：
- 去 `wt-claude-login-fix-git` 窗口
- Review → Commit

---

## 九、Vibe 综合命令

| 命令 | 功能 |
|------|------|
| `vibe <subcommand>` | 动态 Vibe 执行器（自动检测 local → git root → 全局） |
| `vibe -g <subcommand>` | 强制使用全局 vibe |
| `vc` | `vibe chat` — 打开 Vibe Chat |
| `vsign` | `vibe sign` — 签名任务或文档 |
| `vmain` | 跳转到 Vibe 主仓库根目录 |
| `lg` | `lazygit` — Git TUI 界面 |

---

## 十、推荐练习路线（最省脑）

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

## 十一、安全底线（非常重要）

- ❌ 不要在 main/master 用 `ccy` / `ooa`
- ✅ 所有 agent 操作都在 worktree
- ✅ 你永远保留最终审查权
- ✅ 用 `c_safe` 运行 Claude 会自动检测并拒绝在 main 分支执行

---

## 十二、一句话总结

你不是在"和 AI 一起写代码"，
你是在"调度多个 agent 干活"。

这套 alias 的意义就在这里。

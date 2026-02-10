# Vibe Coding 工具链速查表 (Cheatsheet)

本手册涵盖了重构后的所有核心命令、别名及使用场景，方便开发者进行人工审核与功能测试。

## 1. 核心控制台 (Main CLI)
| 命令 | 用途 | 备注 |
| :--- | :--- | :--- |
| `vibe` | 启动交互式控制面板 | 包含 Ignition, Equip, Keys, Sync, Diagnostics |
| `vibe init --ai` | AI 初始化项目 | 默认模式，使用已安装工具生成文档 |
| `vibe init --local` | 本地模板初始化项目 | 无 AI 工具时可用 |
| `vibe chat` / `vc` | 快速进入对话 | 使用默认工具 |
| `vibe keys` | 初始化 API 密钥（可选） | 仅在需要时使用 `config/keys.env` |
| `vibe sync` | 同步当前工作区的 Git 身份 | 自动识别 Agent 类型并配置 user.name/email |
| `vibe tdd new <name>` | **初始化 TDD 开发循环** | 自动创建分支及失败的测试模板 |

## 2. 工具链别名 (Agent Tools: P1 > P2 > P3)
| 工具 | 基础命令 | 自动模式 | 计划/审查模式 |
| :--- | :--- | :--- | :--- |
| **Claude (P1)** | `c` | `claude -p "问题"` | - |
| **OpenCode (P2)** | `o` | `opencode run "问题" -m opencode/kimi-k2.5-free` | - |
| **Codex (P3)** | `x` | `codex exec "问题"` | - |

## 3. 环境切换 (Endpoint Switching)
| 命令 | 效果 | 验证方式 |
| :--- | :--- | :--- |
| `c_cn` | 切换到 **中国中转站** (`api.bghunt.cn`) | `vibe_endpoint` |
| `c_off` | 切换到 **官方原生端点** (`api.anthropic.com`) | `vibe_endpoint` |
| `vibe_endpoint` | 查看当前正在使用的 Claude 端点 | 输出当前配置的 URL |

## 4. 工作区与身份管理 (Worktree & Identity)
| 命令 | 用途 | 示例 |
| :--- | :--- | :--- |
| `wtls` | 列出当前所有工作区 (Worktree) | `git worktree list` 的包装 |
| `wtnew <br> [agt]` | 创建新工作区并**自动配置 Git 身份** | `wtnew feat-ui opencode` |
| `wt <name>` | 快速跳转到指定工作区目录 | `wt wt-claude-feat-ui` |
| `wtinit [agt]` | 手动修复/同步当前目录的 Git 身份 | `wtinit claude` |
| `wtrm <dir>` | 强行删除指定工作区 | 包含目录删除与 git prune |

## 5. 编排与自动化 (Orchestration)
| 命令 | 用途 | 备注 |
| :--- | :--- | :--- |
| `vnew <br> [agt]` | **一键全自动**：创建 WT + 配置身份 + 启动 tmux 矩阵 | **最推荐的开发起点** |
| `vup <dir> [agt]` | 为现有工作区启动 tmux 矩阵界面 | 包含 edit, agent, tests, logs, git 窗口 |
| `vt` | 重新连接 (Attach) 到 vibe tmux 会话 | 解决 SSH 断线或窗口丢失 |

## 6. Git & 辅助工具
| 命令 | 用途 | 备注 |
| :--- | :--- | :--- |
| `lg` | 启动 `lazygit` 审查改动 | 高效的代码审查入口 |
| `gs` / `gd` / `gl` | 极简版 `git status` / `diff` / `log` | 适配高频 CLI 操作 |
| `vmain` | 快速回到项目主分支 (`main`) 目录 | - |

---

## 测试建议 (Audit Checklist)
1. **测试 Keys**: 运行 `vibe keys`（可选），检查 `config/keys.env` 是否正确生成。
2. **测试 Proxy**: 运行 `c_cn` 后执行 `vibe_endpoint`，确认输出为 `https://api.bghunt.cn`。
3. **测试 Identity**: 执行 `vnew audit-test opencode`，进入新生成的 WT 目录运行 `git config user.name`，应显示 `Agent-Opencode`。
4. **测试 TDD**: 执行 `vibe tdd new manual-audit`，检查 `tests/test_manual-audit.sh` 是否生成并具备可执行权限。

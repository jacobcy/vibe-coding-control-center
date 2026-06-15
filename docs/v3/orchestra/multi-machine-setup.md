# 多机部署指南

本文档说明如何在多台机器上部署 Vibe Center orchestra，实现「同一个人在不同机器之间切换工作」的场景。

## 适用场景

### 适合

- 同一个人在多台机器之间**切换**工作（非并发）
- 例如：白天在 Mac 上开发，晚上在 Linux 服务器上继续同一个 issue
- 每台机器有独立的 manager bot 账号，issue 通过 assignee 路由到对应机器

### 不适合

- **真正的并发多机协作**：同一 issue 在多台机器上同时执行
- 需要「双跑保护」「host lease」等机制的场景（本期不做）
- 多人协作场景（每人有自己的 manager bot）

## 配置覆盖路径

Vibe Center 使用 4 级配置覆盖机制（优先级从高到低）：

```
env override
→ .vibe/settings.yaml （项目级，gitignored）
→ ~/.vibe/settings.yaml （全局，每机一份）  ← 推荐做法
→ config/v3/settings.yaml （repo 默认 fallback）
```

**推荐做法**：在每台机器的 `~/.vibe/settings.yaml` 中覆盖 orchestra 配置，而非修改项目级或 repo 默认配置。

配置加载代码参考：`src/vibe3/config/loader.py:179-216`

## 准备步骤

### 1. 为每台机器创建独立 GitHub bot 账号

例如：
- `vibe-manager-mac01` — Mac 上的 manager bot
- `vibe-manager-linux01` — Linux 服务器上的 manager bot

每个 bot 账号需要：
- 独立的 GitHub Personal Access Token（`repo` scope）
- 在 `~/.vibe/keys` 中配置对应的 token 环境变量

### 2. 每台机器覆盖 `~/.vibe/settings.yaml`

在每台机器上创建或编辑 `~/.vibe/settings.yaml`：

```yaml
orchestra:
  manager_usernames: ["vibe-manager-mac01"]  # 本机 bot 用户名
  bot_username: "vibe-manager-mac01"         # 用于过滤自身评论
```

**注意**：
- `manager_usernames` 决定了哪些 GitHub 用户被识别为 manager
- `bot_username` 用于过滤 manager 自身的评论，避免将状态通报误读为人类指令

### 3. Issue assignee 路由到对应机器 bot

当创建或分配 issue 时，显式选择对应机器的 bot 作为 assignee：

```bash
# 分配给 Mac 上的 manager
gh issue edit <issue-number> --add-assignee vibe-manager-mac01

# 分配给 Linux 上的 manager
gh issue edit <issue-number> --add-assignee vibe-manager-linux01
```

Orchestra 会根据 assignee 匹配 `manager_usernames`，触发对应机器上的 manager 执行。

## 已知限制

### 1. Roadmap-intake / Vibe-roadmap 配置

**问题**：`roadmap-intake` 和 `vibe-roadmap` 命令默认使用 `vibe-manager-agent` 作为 assignee，但在多机部署中应匹配 `manager_usernames`。

**影响**：如果未正确配置，governance 自动创建的 issue 可能会落在默认 bot 上，无法路由到多机配置的其他 bot。

**状态**：已支持通过 `manager_usernames` 配置，详见 #1117。

### 2. 跨机看不见现场

**问题**：A 机正在执行的 issue，B 机的 `task status` 无法看到实时状态。

**影响**：切换机器时，需要手动检查 issue 评论区或 flow 状态。

**跟踪**：见 #1113

### 3. 跨机接管

**问题**：A 机开始执行的 issue，无法在 B 机上直接 `task resume` 接管。

**影响**：需要等待 A 机完成或手动干预后，B 机才能接手。

**跟踪**：见 #1114

### 4. 不做双跑保护

**问题**：系统不会阻止同一 issue 在多台机器上同时执行。

**影响**：完全依赖人工判断，避免重复分配。

**建议**：在 issue 评论区明确标注「正在 X 机执行」，切换机器前先确认另一台机器已完成。

## 单机用户

对于单机部署用户：

- **默认行为不变**，无需任何配置
- `config/v3/settings.yaml` 中 `manager_usernames` 默认为 `["vibe-manager-agent"]`
- 单机部署即开即用

相关配置参考：`config/v3/settings.yaml:252`

## 相关文档

- [README.md](README.md) — Orchestra 概述与快速开始
- [runtime-modes.md](runtime-modes.md) — 运行模式说明
- [prd-orchestra-integration.md](prd-orchestra-integration.md) — PRD 与边界说明

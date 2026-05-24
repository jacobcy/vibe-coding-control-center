# Deprecated Directory: vibe3-user-guide

状态：Deprecated

本文件仅保留为旧路径目录页，不再承载现行用户指南正文。

## 📖 现行真源 (Current Truth)

**所有 Vibe 3.0 操作指南与命令规范请以此文档为准：**

👉 **[docs/standards/v3/command-standard.md](v3/command-standard.md)**

**项目全局导航与 Agent 协作入口请参考：**

👉 **[AGENTS.md](../../AGENTS.md)**

---

原因：

- 旧版指南混入了多组历史命令示例
- 包含 `flow create/switch/done/aborted/list` 等已退场入口
- 已不适合作为当前操作指引

其他参考入口：

1. [README.md](../README.md)
2. [docs/standards/v3/handoff-store-standard.md](v3/handoff-store-standard.md)
3. [docs/standards/issue-standard.md](issue-standard.md)
4. [docs/standards/roadmap-label-management.md](roadmap-label-management.md)

当前推荐操作模型：

- branch 生命周期管理：直接使用 `git`
- issue / PR / project 远端操作：直接使用 `gh`
- 本地 flow 注册与绑定：使用 `vibe3 flow update`、`vibe3 flow bind`
- 本地现场与任务状态读取：使用 `vibe3 task status`、`vibe3 flow show`
- 本地协作与交接增强：使用 `vibe3 handoff`

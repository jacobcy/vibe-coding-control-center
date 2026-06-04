# Deprecated Directory: vibe3-command-standard

状态：Deprecated

本文件仅保留为旧路径目录页，不再承载现行命令规范正文。

## 📖 现行真源 (Current Truth)

**所有 Vibe 3.0 命令规范请以此文档为准：**

👉 **[docs/standards/v3/command-standard.md](v3/command-standard.md)**

**项目全局导航与 Agent 协作入口请参考：**

👉 **[AGENTS.md](../../AGENTS.md)**

---

原因：

- 旧版正文混合了历史命令面与现行语义
- 曾同时描述 `flow add/create/new/switch/done/aborted/list` 等已退场入口
- 容易与现行 shared-state 标准形成双真源

其他参考入口：

1. [docs/standards/v3/handoff-store-standard.md](v3/handoff-store-standard.md)
2. [docs/standards/issue-standard.md](issue-standard.md)
3. [docs/standards/roadmap-label-management.md](roadmap-label-management.md)

语义收敛说明：

- branch 生命周期管理：直接使用 `git`
- issue / PR / project 远端操作：直接使用 `gh`
- `vibe3` 负责本地 flow scene、issue 绑定、events 与 handoff 增强
- `task` 保留为 execution bridge 语义，通过 `vibe3 task status` 统一呈现

# Deprecated Directory: vibe3-command-standard

状态：Deprecated

本文件仅保留为旧路径目录页，不再承载现行命令规范正文。

原因：

- 旧版正文混合了历史命令面与现行语义
- 曾同时描述 `flow add/create/new/switch/done/aborted/list` 等已退场入口
- 容易与现行 shared-state 标准形成双真源

现行阅读入口：

1. [docs/standards/v3/command-standard.md](v3/command-standard.md)
2. [docs/standards/v3/handoff-store-standard.md](v3/handoff-store-standard.md)
3. [docs/standards/issue-standard.md](issue-standard.md)
4. [docs/standards/roadmap-label-management.md](roadmap-label-management.md)

语义收敛说明：

- branch 生命周期优先直接使用 `git`
- issue / PR / project 的远端读取与写入优先直接使用 `gh`
- `vibe3` 负责本地 flow scene、issue 绑定、events 与 handoff 增强
- `task` 保留为 execution bridge 语义，不再对应独立公共顶层 CLI

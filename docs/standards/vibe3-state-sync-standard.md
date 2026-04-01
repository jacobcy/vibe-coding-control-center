# Deprecated Directory: vibe3-state-sync-standard

状态：Deprecated

本文件仅保留为旧路径目录页，不再承载现行状态联动规则正文。

原因：

- 旧版正文继续使用历史命令面描述状态机
- 曾把 `flow add/create/done` 等退场命令写成现行判定表
- 已不适合作为共享状态域的现行真源

现行阅读入口：

1. [docs/standards/v3/command-standard.md](v3/command-standard.md)
2. [docs/standards/v3/handoff-store-standard.md](v3/handoff-store-standard.md)
3. [docs/standards/issue-standard.md](issue-standard.md)
4. [docs/standards/roadmap-label-management.md](roadmap-label-management.md)

状态同步语义以现行标准为准：

- 先确认 `git` / `gh` 现场事实
- 只在本地维护最小运行时绑定事实
- 不把远端字段长期落地为本地真源
- 不为 `git` / `gh` 已稳定覆盖的动作再新增平行包装命令

# Deprecated Directory: vibe3-user-guide

状态：Deprecated

本文件仅保留为旧路径目录页，不再承载现行用户指南正文。

原因：

- 旧版指南混入了多组历史命令示例
- 包含 `flow create/switch/done/aborted/list` 等已退场入口
- 已不适合作为当前操作指引

现行阅读入口：

1. [README.md](../README.md)
2. [AGENTS.md](../../AGENTS.md)
3. [docs/standards/v3/command-standard.md](v3/command-standard.md)
4. [docs/standards/v3/handoff-store-standard.md](v3/handoff-store-standard.md)
5. [docs/standards/issue-standard.md](issue-standard.md)
6. [docs/standards/roadmap-label-management.md](roadmap-label-management.md)

当前推荐操作模型：

- branch 创建、切换、merge、删除：直接使用 `git`
- issue / PR / project 的远端读取与写入：直接使用 `gh`
- 本地 flow 注册与绑定：使用 `vibe3 flow update`、`vibe3 flow bind`
- 本地现场读取：使用 `vibe3 flow show`、`vibe3 flow status`、`vibe3 status`
- 本地协作增强：使用 `vibe3 handoff`
